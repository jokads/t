"""
Trading Orchestrator - Main signal generation and validation pipeline

Coordinates:
1. Market data enrichment
2. AI signal generation
3. Risk validation
4. MT5 order execution
5. Event publishing
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Dict, Any, Optional

from bot_mt5.ai_manager import AIManager
from bot_mt5.schemas.messages import SignalCreate, OrderExecute, ErrorMessage
from bot_mt5.utils.config import get_config

logger = logging.getLogger(__name__)


class TradingOrchestrator:
    """
    Main trading orchestrator.
    
    Implements the generate_and_validate_signals() pipeline:
    - Receive signal request from MT5 EA
    - Enrich with market data
    - Call AI for decision
    - Validate with risk manager
    - Execute via MT5 communication
    - Publish events
    """
    
    def __init__(
        self,
        ai_manager: Optional[AIManager] = None,
        mt5_client: Optional[Any] = None,
        risk_manager: Optional[Any] = None,
    ):
        self.config = get_config()
        self.ai_manager = ai_manager
        self.mt5_client = mt5_client
        self.risk_manager = risk_manager
        self.running = False
        
    async def start(self):
        """Start the orchestrator and dependencies"""
        if self.running:
            logger.warning("Orchestrator already running")
            return
        
        logger.info("Starting TradingOrchestrator")
        self.running = True
        
        # Start AI manager if provided
        if self.ai_manager:
            await self.ai_manager.start()
        
        # Start MT5 client if provided
        if self.mt5_client and hasattr(self.mt5_client, 'start'):
            await self.mt5_client.start()
        
        logger.info("TradingOrchestrator started")
    
    async def stop(self):
        """Stop the orchestrator and dependencies"""
        if not self.running:
            return
        
        logger.info("Stopping TradingOrchestrator")
        self.running = False
        
        # Stop AI manager
        if self.ai_manager:
            await self.ai_manager.stop()
        
        # Stop MT5 client
        if self.mt5_client and hasattr(self.mt5_client, 'stop'):
            await self.mt5_client.stop()
        
        logger.info("TradingOrchestrator stopped")
    
    async def generate_and_validate_signals(
        self,
        signal_request: SignalCreate,
        timeout: float = 15.0,
    ) -> OrderExecute | ErrorMessage:
        """
        Main signal generation and validation pipeline.
        
        Args:
            signal_request: Signal request from MT5 EA
            timeout: Total timeout for entire pipeline (seconds)
            
        Returns:
            OrderExecute if successful, ErrorMessage if failed
        """
        trace_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            logger.info(
                f"[{trace_id}] Processing signal request: "
                f"{signal_request.payload.symbol} {signal_request.payload.action}"
            )
            
            # Step 1: Enrich market data
            enriched_data = await asyncio.wait_for(
                self._enrich_market_data(signal_request),
                timeout=2.0
            )
            
            # Step 2: Call AI for decision
            ai_timeout = min(timeout - (time.time() - start_time) - 5.0, self.config.ai.timeout_quick)
            ai_result = await asyncio.wait_for(
                self._get_ai_decision(enriched_data, signal_request),
                timeout=ai_timeout
            )
            
            if not ai_result["success"]:
                logger.warning(f"[{trace_id}] AI failed: {ai_result.get('error')}")
                return ErrorMessage(
                    error_code="AI_FAILED",
                    error_message=ai_result.get("error", "Unknown AI error"),
                    trace_id=trace_id,
                )
            
            # Parse AI decision
            ai_signal = ai_result.get("parsed")
            if not ai_signal:
                logger.warning(f"[{trace_id}] AI returned invalid signal")
                return ErrorMessage(
                    error_code="INVALID_AI_RESPONSE",
                    error_message="AI did not return valid JSON signal",
                    trace_id=trace_id,
                    details={"ai_text": ai_result.get("text", "")[:200]}
                )
            
            # Step 3: Validate with risk manager
            risk_ok, risk_reason = await asyncio.wait_for(
                self._validate_risk(signal_request, ai_signal),
                timeout=1.0
            )
            
            if not risk_ok:
                logger.warning(f"[{trace_id}] Risk validation failed: {risk_reason}")
                return ErrorMessage(
                    error_code="RISK_REJECTED",
                    error_message=f"Risk manager rejected: {risk_reason}",
                    trace_id=trace_id,
                )
            
            # Step 4: Execute order via MT5
            exec_timeout = min(timeout - (time.time() - start_time) - 1.0, self.config.mt5.exec_timeout)
            order_result = await asyncio.wait_for(
                self._execute_order(signal_request, ai_signal),
                timeout=exec_timeout
            )
            
            if not order_result["success"]:
                logger.error(f"[{trace_id}] Order execution failed: {order_result.get('error')}")
                return ErrorMessage(
                    error_code="EXECUTION_FAILED",
                    error_message=order_result.get("error", "Unknown execution error"),
                    trace_id=trace_id,
                )
            
            # Step 5: Publish event (fire-and-forget)
            asyncio.create_task(self._publish_event("order.executed", order_result))
            
            # Calculate total latency
            latency_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"[{trace_id}] Signal processed successfully in {latency_ms:.1f}ms: "
                f"{ai_signal.get('action')} {signal_request.payload.symbol}"
            )
            
            # Return success response
            return OrderExecute(
                success=True,
                order_id=order_result.get("order_id"),
                payload=signal_request.payload,
                latency_ms=latency_ms,
            )
            
        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"[{trace_id}] Pipeline timeout after {latency_ms:.1f}ms")
            return ErrorMessage(
                error_code="PIPELINE_TIMEOUT",
                error_message=f"Pipeline exceeded {timeout}s timeout",
                trace_id=trace_id,
                details={"latency_ms": latency_ms}
            )
        
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.exception(f"[{trace_id}] Unexpected error in pipeline")
            return ErrorMessage(
                error_code="INTERNAL_ERROR",
                error_message=str(e),
                trace_id=trace_id,
                details={"latency_ms": latency_ms}
            )
    
    async def _enrich_market_data(self, signal_request: SignalCreate) -> Dict[str, Any]:
        """
        Enrich signal request with market data.
        
        In production, this should fetch:
        - Recent price history
        - Technical indicators
        - Account balance/equity
        - Open positions
        """
        # TODO: Implement actual market data fetching
        # For now, return basic enrichment
        return {
            "symbol": signal_request.payload.symbol,
            "current_price": signal_request.payload.price or 1.0,
            "account_id": signal_request.payload.account_id,
            "strategy": signal_request.payload.strategy,
            # Placeholder for real data
            "sma_20": 1.0,
            "sma_50": 1.0,
            "rsi_14": 50.0,
            "atr_14": 0.001,
        }
    
    async def _get_ai_decision(
        self,
        enriched_data: Dict[str, Any],
        signal_request: SignalCreate,
    ) -> Dict[str, Any]:
        """
        Get AI decision for the signal.
        
        Builds prompt from enriched data and calls AI manager.
        """
        if not self.ai_manager:
            logger.warning("No AI manager, using fallback")
            return {
                "success": True,
                "parsed": {
                    "action": signal_request.payload.action,
                    "confidence": 0.5,
                    "lot": signal_request.payload.lot,
                    "stop_loss": signal_request.payload.stop_loss,
                    "take_profit": signal_request.payload.take_profit,
                    "reason": "No AI manager available"
                },
                "model_type": "passthrough",
            }
        
        # Build prompt
        prompt = self._build_prompt(enriched_data, signal_request)
        
        # Call AI
        result = await self.ai_manager.ask(
            prompt=prompt,
            timeout=self.config.ai.timeout_quick,
            max_tokens=128,
            temperature=0.7,
        )
        
        return result
    
    def _build_prompt(
        self,
        enriched_data: Dict[str, Any],
        signal_request: SignalCreate,
    ) -> str:
        """
        Build AI prompt from enriched data.
        
        TODO: Use prompt templates from prompts/ directory
        """
        return f"""Analyze this trading signal and decide action:

Symbol: {enriched_data['symbol']}
Current Price: {enriched_data['current_price']}
Strategy: {enriched_data['strategy']}
Suggested Action: {signal_request.payload.action}

Technical Indicators:
- SMA 20: {enriched_data['sma_20']}
- SMA 50: {enriched_data['sma_50']}
- RSI 14: {enriched_data['rsi_14']}
- ATR 14: {enriched_data['atr_14']}

Return JSON with:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0-1.0,
  "lot": float,
  "stop_loss": float | null,
  "take_profit": float | null,
  "reason": "brief explanation"
}}
"""
    
    async def _validate_risk(
        self,
        signal_request: SignalCreate,
        ai_signal: Dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Validate signal with risk manager.
        
        TODO: Implement actual risk checks:
        - Max lot size
        - Max exposure per symbol
        - Max drawdown
        - Correlation limits
        """
        # Basic validation
        action = ai_signal.get("action", "HOLD")
        confidence = ai_signal.get("confidence", 0.0)
        lot = ai_signal.get("lot", 0.01)
        
        # Don't trade HOLD signals
        if action == "HOLD":
            return False, "Action is HOLD"
        
        # Minimum confidence threshold
        if confidence < 0.5:
            return False, f"Confidence too low: {confidence:.2f}"
        
        # Max lot size
        if lot > 1.0:
            return False, f"Lot size too large: {lot}"
        
        # All checks passed
        return True, "OK"
    
    async def _execute_order(
        self,
        signal_request: SignalCreate,
        ai_signal: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute order via MT5 communication.
        
        TODO: Implement actual MT5 order execution
        """
        if not self.mt5_client:
            logger.warning("No MT5 client, simulating execution")
            return {
                "success": True,
                "order_id": f"SIM_{uuid.uuid4().hex[:8]}",
                "action": ai_signal.get("action"),
                "lot": ai_signal.get("lot"),
            }
        
        # TODO: Call MT5 client
        # result = await self.mt5_client.execute_order(...)
        
        return {
            "success": True,
            "order_id": f"MT5_{uuid.uuid4().hex[:8]}",
            "action": ai_signal.get("action"),
            "lot": ai_signal.get("lot"),
        }
    
    async def _publish_event(self, event_type: str, data: Dict[str, Any]):
        """
        Publish event to Redis pub/sub or event bus.
        
        TODO: Implement actual event publishing
        """
        logger.debug(f"Event published: {event_type}")
        # TODO: Redis pub/sub or other event bus
        pass
