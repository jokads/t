"""
AI Model Worker Process

Isolated process that loads and runs a single AI model.
Communicates via multiprocessing.Queue for async-safe operation.
"""
from __future__ import annotations

import json
import logging
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging for worker process
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | Worker-%(process)d | %(message)s"
)
logger = logging.getLogger(__name__)


class ModelWorker:
    """
    Worker process that loads and runs a single AI model.
    
    Runs in a dedicated process to:
    - Avoid GIL contention
    - Isolate memory (prevent leaks)
    - Enable timeout/kill without affecting main process
    """
    
    def __init__(
        self,
        model_path: str,
        worker_id: int,
        request_queue: mp.Queue,
        response_queue: mp.Queue,
        n_ctx: int = 2048,
        n_gpu_layers: int = 0,
    ):
        self.model_path = model_path
        self.worker_id = worker_id
        self.request_queue = request_queue
        self.response_queue = response_queue
        self.n_ctx = n_ctx
        self.n_gpu_layers = n_gpu_layers
        self.model = None
        self.running = True
        
    def load_model(self) -> bool:
        """Load the AI model (llama.cpp or gpt4all)"""
        try:
            logger.info(f"Worker {self.worker_id}: Loading model from {self.model_path}")
            
            # Try llama-cpp-python first
            try:
                from llama_cpp import Llama
                self.model = Llama(
                    model_path=self.model_path,
                    n_ctx=self.n_ctx,
                    n_gpu_layers=self.n_gpu_layers,
                    verbose=False,
                )
                self.model_type = "llama_cpp"
                logger.info(f"Worker {self.worker_id}: Loaded with llama-cpp-python")
                return True
            except ImportError:
                logger.warning("llama-cpp-python not available, trying gpt4all")
            except Exception as e:
                logger.warning(f"llama-cpp-python failed: {e}, trying gpt4all")
            
            # Fallback to gpt4all
            try:
                from gpt4all import GPT4All
                self.model = GPT4All(
                    model_name=Path(self.model_path).name,
                    model_path=str(Path(self.model_path).parent),
                    allow_download=False,
                )
                self.model_type = "gpt4all"
                logger.info(f"Worker {self.worker_id}: Loaded with gpt4all")
                return True
            except ImportError:
                logger.error("gpt4all not available")
            except Exception as e:
                logger.error(f"gpt4all failed: {e}")
            
            logger.error(f"Worker {self.worker_id}: Failed to load model")
            return False
            
        except Exception as e:
            logger.exception(f"Worker {self.worker_id}: Error loading model: {e}")
            return False
    
    def generate(self, prompt: str, max_tokens: int = 128, temperature: float = 0.7) -> Dict[str, Any]:
        """Generate response from model"""
        if self.model is None:
            return {
                "success": False,
                "error": "Model not loaded",
                "text": "",
            }
        
        try:
            start_time = time.time()
            
            if self.model_type == "llama_cpp":
                # Use JSON schema mode for structured output
                response = self.model.create_chat_completion(
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a trading signal generator. Always respond with valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    response_format={
                        "type": "json_object",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                "lot": {"type": "number", "minimum": 0.01},
                                "stop_loss": {"type": ["number", "null"]},
                                "take_profit": {"type": ["number", "null"]},
                                "reason": {"type": "string"}
                            },
                            "required": ["action", "confidence"]
                        }
                    },
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                text = response["choices"][0]["message"]["content"]
                
            elif self.model_type == "gpt4all":
                # GPT4All simple generation
                text = self.model.generate(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temp=temperature,
                )
            else:
                return {
                    "success": False,
                    "error": "Unknown model type",
                    "text": "",
                }
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Try to parse as JSON
            try:
                parsed = json.loads(text)
                return {
                    "success": True,
                    "text": text,
                    "parsed": parsed,
                    "latency_ms": latency_ms,
                    "model_type": self.model_type,
                }
            except json.JSONDecodeError:
                # Return raw text if not JSON
                return {
                    "success": True,
                    "text": text,
                    "parsed": None,
                    "latency_ms": latency_ms,
                    "model_type": self.model_type,
                }
                
        except Exception as e:
            logger.exception(f"Worker {self.worker_id}: Generation error")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "traceback": traceback.format_exc(),
            }
    
    def run(self):
        """Main worker loop"""
        logger.info(f"Worker {self.worker_id}: Starting")
        
        # Load model
        if not self.load_model():
            logger.error(f"Worker {self.worker_id}: Failed to load model, exiting")
            self.response_queue.put({
                "type": "error",
                "worker_id": self.worker_id,
                "error": "Failed to load model",
            })
            return
        
        # Send ready signal
        self.response_queue.put({
            "type": "ready",
            "worker_id": self.worker_id,
            "model_path": self.model_path,
        })
        
        logger.info(f"Worker {self.worker_id}: Ready and waiting for requests")
        
        # Process requests
        while self.running:
            try:
                # Wait for request with timeout
                try:
                    request = self.request_queue.get(timeout=1.0)
                except:
                    continue
                
                if request is None or request.get("type") == "shutdown":
                    logger.info(f"Worker {self.worker_id}: Shutdown requested")
                    break
                
                # Process request
                request_id = request.get("request_id")
                prompt = request.get("prompt", "")
                max_tokens = request.get("max_tokens", 128)
                temperature = request.get("temperature", 0.7)
                
                logger.debug(f"Worker {self.worker_id}: Processing request {request_id}")
                
                result = self.generate(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                
                # Send response
                self.response_queue.put({
                    "type": "response",
                    "request_id": request_id,
                    "worker_id": self.worker_id,
                    "result": result,
                })
                
            except KeyboardInterrupt:
                logger.info(f"Worker {self.worker_id}: Interrupted")
                break
            except Exception as e:
                logger.exception(f"Worker {self.worker_id}: Error in main loop")
                # Try to send error response
                try:
                    self.response_queue.put({
                        "type": "error",
                        "worker_id": self.worker_id,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    })
                except:
                    pass
        
        logger.info(f"Worker {self.worker_id}: Exiting")


def worker_process(
    model_path: str,
    worker_id: int,
    request_queue: mp.Queue,
    response_queue: mp.Queue,
    n_ctx: int = 2048,
    n_gpu_layers: int = 0,
):
    """
    Worker process entry point.
    
    This function is called by multiprocessing.Process.
    """
    try:
        worker = ModelWorker(
            model_path=model_path,
            worker_id=worker_id,
            request_queue=request_queue,
            response_queue=response_queue,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,
        )
        worker.run()
    except Exception as e:
        logger.exception(f"Worker {worker_id}: Fatal error")
        sys.exit(1)
