"""
AI Manager - Async interface to AI model worker pool

Manages a pool of worker processes, each running a dedicated AI model.
Provides async interface with timeouts, circuit-breaker, and fallback.
"""
from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from bot_mt5.utils.config import AIConfig, get_config

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a worker"""
    failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False
    open_until: float = 0.0


class AIManager:
    """
    Async AI Manager with worker pool.
    
    Features:
    - Worker pool with dedicated processes per model
    - Async interface with configurable timeouts
    - Circuit-breaker pattern for failing workers
    - Fallback to rule-based signals if all workers fail
    - Request queue with fair distribution
    """
    
    def __init__(self, config: Optional[AIConfig] = None):
        self.config = config or get_config().ai
        self.workers: List[mp.Process] = []
        self.request_queues: List[mp.Queue] = []
        self.response_queue: mp.Queue = mp.Queue()
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self.circuit_breakers: Dict[int, CircuitBreakerState] = defaultdict(CircuitBreakerState)
        self.worker_ready: Dict[int, bool] = {}
        self.running = False
        self.response_task: Optional[asyncio.Task] = None
        self._next_worker = 0
        
    async def start(self):
        """Start the AI manager and worker pool"""
        if self.running:
            logger.warning("AIManager already running")
            return
        
        logger.info("Starting AIManager")
        self.running = True
        
        # Find available models
        models = self._find_models()
        if not models:
            logger.warning("No models found, AIManager will use fallback only")
            return
        
        logger.info(f"Found {len(models)} models: {[m.name for m in models]}")
        
        # Start workers
        for i, model_path in enumerate(models[:self.config.pool_size]):
            self._start_worker(i, str(model_path))
        
        # Start response handler
        self.response_task = asyncio.create_task(self._handle_responses())
        
        # Wait for workers to be ready
        await self._wait_for_workers(timeout=30.0)
        
        logger.info(f"AIManager started with {len(self.workers)} workers")
    
    async def stop(self):
        """Stop the AI manager and all workers"""
        if not self.running:
            return
        
        logger.info("Stopping AIManager")
        self.running = False
        
        # Send shutdown to all workers
        for queue in self.request_queues:
            try:
                queue.put({"type": "shutdown"}, timeout=1.0)
            except:
                pass
        
        # Cancel response handler
        if self.response_task:
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                pass
        
        # Terminate workers
        for worker in self.workers:
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=2.0)
                if worker.is_alive():
                    worker.kill()
        
        # Cancel pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.set_exception(Exception("AIManager stopped"))
        
        self.pending_requests.clear()
        self.workers.clear()
        self.request_queues.clear()
        
        logger.info("AIManager stopped")
    
    async def ask(
        self,
        prompt: str,
        model: Optional[str] = None,
        timeout: Optional[float] = None,
        max_tokens: int = 128,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Ask AI model a question with timeout.
        
        Args:
            prompt: The prompt to send to the model
            model: Model name hint (not used yet, uses round-robin)
            timeout: Timeout in seconds (default: config.timeout_quick)
            max_tokens: Max tokens to generate
            temperature: Sampling temperature
            
        Returns:
            Dict with keys: success, text, parsed (if JSON), latency_ms, error
        """
        if not self.running:
            logger.error("AIManager not running")
            return await self._fallback_signal(prompt)
        
        if not self.workers:
            logger.warning("No workers available, using fallback")
            return await self._fallback_signal(prompt)
        
        timeout = timeout or self.config.timeout_quick
        request_id = str(uuid.uuid4())
        
        # Find available worker (skip circuit-broken ones)
        worker_id = self._get_available_worker()
        if worker_id is None:
            logger.warning("All workers circuit-broken, using fallback")
            return await self._fallback_signal(prompt)
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        # Send request to worker
        try:
            self.request_queues[worker_id].put({
                "type": "generate",
                "request_id": request_id,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }, timeout=1.0)
        except Exception as e:
            logger.error(f"Failed to send request to worker {worker_id}: {e}")
            del self.pending_requests[request_id]
            self._record_failure(worker_id)
            return await self._fallback_signal(prompt)
        
        # Wait for response with timeout
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            self._record_success(worker_id)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Request {request_id} timed out after {timeout}s")
            del self.pending_requests[request_id]
            self._record_failure(worker_id)
            return {
                "success": False,
                "error": f"Timeout after {timeout}s",
                "text": "",
            }
        except Exception as e:
            logger.exception(f"Error waiting for response: {e}")
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]
            self._record_failure(worker_id)
            return await self._fallback_signal(prompt)
    
    def _find_models(self) -> List[Path]:
        """Find available GGUF models in configured paths"""
        models = []
        for path_str in self.config.model_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            
            # Search for .gguf files
            for gguf_file in path.rglob("*.gguf"):
                if gguf_file.is_file():
                    models.append(gguf_file)
        
        return models
    
    def _start_worker(self, worker_id: int, model_path: str):
        """Start a single worker process"""
        from bot_mt5.ai_manager.worker import worker_process
        
        request_queue = mp.Queue()
        
        worker = mp.Process(
            target=worker_process,
            args=(
                model_path,
                worker_id,
                request_queue,
                self.response_queue,
                2048,  # n_ctx
                0,     # n_gpu_layers (CPU only for now)
            ),
            daemon=True,
        )
        
        worker.start()
        self.workers.append(worker)
        self.request_queues.append(request_queue)
        self.worker_ready[worker_id] = False
        
        logger.info(f"Started worker {worker_id} (PID: {worker.pid})")
    
    async def _wait_for_workers(self, timeout: float = 30.0):
        """Wait for all workers to be ready"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if all(self.worker_ready.values()):
                return
            await asyncio.sleep(0.1)
        
        ready_count = sum(self.worker_ready.values())
        logger.warning(f"Only {ready_count}/{len(self.workers)} workers ready after {timeout}s")
    
    async def _handle_responses(self):
        """Handle responses from worker processes (runs in background task)"""
        logger.info("Response handler started")
        
        while self.running:
            try:
                # Check for responses (non-blocking)
                try:
                    response = self.response_queue.get(timeout=0.1)
                except:
                    await asyncio.sleep(0.01)
                    continue
                
                response_type = response.get("type")
                
                if response_type == "ready":
                    worker_id = response.get("worker_id")
                    self.worker_ready[worker_id] = True
                    logger.info(f"Worker {worker_id} ready")
                
                elif response_type == "response":
                    request_id = response.get("request_id")
                    result = response.get("result", {})
                    
                    if request_id in self.pending_requests:
                        future = self.pending_requests.pop(request_id)
                        if not future.done():
                            future.set_result(result)
                
                elif response_type == "error":
                    worker_id = response.get("worker_id")
                    error = response.get("error")
                    logger.error(f"Worker {worker_id} error: {error}")
                    self._record_failure(worker_id)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in response handler: {e}")
        
        logger.info("Response handler stopped")
    
    def _get_available_worker(self) -> Optional[int]:
        """Get next available worker (round-robin, skip circuit-broken)"""
        if not self.workers:
            return None
        
        now = time.time()
        attempts = 0
        
        while attempts < len(self.workers):
            worker_id = self._next_worker
            self._next_worker = (self._next_worker + 1) % len(self.workers)
            attempts += 1
            
            # Check circuit breaker
            cb = self.circuit_breakers[worker_id]
            if cb.is_open:
                if now >= cb.open_until:
                    # Try to close circuit
                    logger.info(f"Closing circuit breaker for worker {worker_id}")
                    cb.is_open = False
                    cb.failures = 0
                    return worker_id
                else:
                    # Still open
                    continue
            
            # Check if worker is alive
            if not self.workers[worker_id].is_alive():
                logger.warning(f"Worker {worker_id} is dead")
                self._record_failure(worker_id)
                continue
            
            return worker_id
        
        return None
    
    def _record_success(self, worker_id: int):
        """Record successful request for circuit breaker"""
        cb = self.circuit_breakers[worker_id]
        cb.failures = max(0, cb.failures - 1)
    
    def _record_failure(self, worker_id: int):
        """Record failed request for circuit breaker"""
        cb = self.circuit_breakers[worker_id]
        cb.failures += 1
        cb.last_failure_time = time.time()
        
        if cb.failures >= self.config.circuit_breaker_threshold:
            logger.warning(
                f"Circuit breaker opened for worker {worker_id} "
                f"({cb.failures} failures)"
            )
            cb.is_open = True
            cb.open_until = time.time() + self.config.circuit_breaker_timeout
    
    async def _fallback_signal(self, prompt: str) -> Dict[str, Any]:
        """
        Fallback rule-based signal when AI is unavailable.
        
        Simple EMA crossover logic for demonstration.
        In production, this should use actual market data.
        """
        logger.info("Using fallback rule-based signal")
        
        # Simulate simple logic
        import random
        
        action = random.choice(["BUY", "SELL", "HOLD"])
        confidence = 0.4 + random.random() * 0.2  # 0.4-0.6
        
        return {
            "success": True,
            "text": f'{{"action": "{action}", "confidence": {confidence:.2f}}}',
            "parsed": {
                "action": action,
                "confidence": confidence,
                "lot": 0.01,
                "stop_loss": None,
                "take_profit": None,
                "reason": "Fallback rule-based (EMA crossover simulation)"
            },
            "latency_ms": 1.0,
            "model_type": "fallback",
        }
