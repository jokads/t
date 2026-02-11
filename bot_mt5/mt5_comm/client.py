"""
MT5 Communication Client - Socket with reconnection

Robust TCP socket client for MT5 EA communication with:
- Automatic reconnection with exponential backoff
- Heartbeat to detect dead connections
- Message validation with pydantic
- ACK/confirm pattern
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Optional, Dict, Any

from bot_mt5.schemas.messages import (
    SignalCreate,
    OrderExecute,
    Heartbeat,
    ErrorMessage,
    AuthRequest,
    AuthResponse,
)
from bot_mt5.utils.config import MT5Config, get_config

logger = logging.getLogger(__name__)


class MT5Client:
    """
    MT5 Socket Client with reconnection.
    
    Features:
    - TCP socket connection to MT5 EA
    - Exponential backoff reconnection
    - Heartbeat ping/pong
    - Message validation with pydantic
    - ACK/confirm for order execution
    """
    
    def __init__(self, config: Optional[MT5Config] = None):
        self.config = config or get_config().mt5
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.running = False
        self.reconnect_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.last_heartbeat_time = 0.0
        self.reconnect_attempts = 0
        
    async def start(self):
        """Start the MT5 client"""
        if self.running:
            logger.warning("MT5Client already running")
            return
        
        logger.info(f"Starting MT5Client (server mode: {self.config.host}:{self.config.port})")
        self.running = True
        
        # Start reconnection loop
        self.reconnect_task = asyncio.create_task(self._reconnect_loop())
        
        # Start heartbeat
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        
        logger.info("MT5Client started")
    
    async def stop(self):
        """Stop the MT5 client"""
        if not self.running:
            return
        
        logger.info("Stopping MT5Client")
        self.running = False
        
        # Cancel tasks
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close connection
        await self._disconnect()
        
        logger.info("MT5Client stopped")
    
    async def send_message(self, message: Dict[str, Any], timeout: float = 5.0) -> bool:
        """
        Send message to MT5 EA.
        
        Args:
            message: Message dict to send
            timeout: Send timeout in seconds
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.connected or not self.writer:
            logger.warning("Cannot send message: not connected")
            return False
        
        try:
            # Serialize message
            if hasattr(message, 'model_dump_json'):
                # Pydantic model
                data = message.model_dump_json()
            else:
                # Dict
                data = json.dumps(message)
            
            # Send with newline delimiter
            self.writer.write(data.encode('utf-8') + b'\n')
            await asyncio.wait_for(self.writer.drain(), timeout=timeout)
            
            logger.debug(f"Sent message: {message.get('type', 'unknown')}")
            return True
            
        except asyncio.TimeoutError:
            logger.error(f"Send timeout after {timeout}s")
            await self._disconnect()
            return False
        except Exception as e:
            logger.exception(f"Error sending message: {e}")
            await self._disconnect()
            return False
    
    async def receive_message(self, timeout: float = 5.0) -> Optional[Dict[str, Any]]:
        """
        Receive message from MT5 EA.
        
        Args:
            timeout: Receive timeout in seconds
            
        Returns:
            Message dict if received, None otherwise
        """
        if not self.connected or not self.reader:
            logger.warning("Cannot receive message: not connected")
            return None
        
        try:
            # Read until newline
            data = await asyncio.wait_for(
                self.reader.readuntil(b'\n'),
                timeout=timeout
            )
            
            # Parse JSON
            message = json.loads(data.decode('utf-8').strip())
            
            logger.debug(f"Received message: {message.get('type', 'unknown')}")
            return message
            
        except asyncio.TimeoutError:
            logger.debug(f"Receive timeout after {timeout}s")
            return None
        except asyncio.IncompleteReadError:
            logger.warning("Connection closed by peer")
            await self._disconnect()
            return None
        except Exception as e:
            logger.exception(f"Error receiving message: {e}")
            await self._disconnect()
            return None
    
    async def execute_order(
        self,
        signal: SignalCreate,
        timeout: float = 5.0
    ) -> Dict[str, Any]:
        """
        Execute order and wait for confirmation.
        
        Args:
            signal: Signal to execute
            timeout: Execution timeout in seconds
            
        Returns:
            Dict with success, order_id, error
        """
        if not self.connected:
            return {
                "success": False,
                "error": "Not connected to MT5",
            }
        
        try:
            # Send order
            if not await self.send_message(signal, timeout=timeout):
                return {
                    "success": False,
                    "error": "Failed to send order",
                }
            
            # Wait for response
            response = await self.receive_message(timeout=timeout)
            if not response:
                return {
                    "success": False,
                    "error": "No response from MT5",
                }
            
            # Validate response
            try:
                if response.get("type") == "order.execute":
                    order_exec = OrderExecute(**response)
                    return {
                        "success": order_exec.success,
                        "order_id": order_exec.order_id,
                        "error": order_exec.error,
                    }
                elif response.get("type") == "error":
                    error_msg = ErrorMessage(**response)
                    return {
                        "success": False,
                        "error": error_msg.error_message,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Unexpected response type: {response.get('type')}",
                    }
            except Exception as e:
                logger.exception(f"Error validating response: {e}")
                return {
                    "success": False,
                    "error": f"Invalid response: {e}",
                }
                
        except Exception as e:
            logger.exception(f"Error executing order: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    async def _connect(self) -> bool:
        """
        Connect to MT5 EA (or wait for EA to connect if server mode).
        
        For now, implements server mode (Python listens, EA connects).
        """
        try:
            logger.info(f"Waiting for MT5 EA connection on {self.config.host}:{self.config.port}")
            
            # Start server
            server = await asyncio.start_server(
                self._handle_client,
                self.config.host,
                self.config.port,
            )
            
            logger.info(f"Server listening on {self.config.host}:{self.config.port}")
            
            # Wait for first connection (this is simplified - in production,
            # we'd handle multiple connections differently)
            # For now, the _handle_client callback will set self.reader/writer
            
            return True
            
        except Exception as e:
            logger.exception(f"Error connecting: {e}")
            return False
    
    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle incoming client connection (EA)"""
        addr = writer.get_extra_info('peername')
        logger.info(f"MT5 EA connected from {addr}")
        
        self.reader = reader
        self.writer = writer
        self.connected = True
        self.last_heartbeat_time = time.time()
        self.reconnect_attempts = 0
        
        # Keep connection alive until closed
        try:
            while self.running and self.connected:
                await asyncio.sleep(1.0)
        except Exception as e:
            logger.exception(f"Error in client handler: {e}")
        finally:
            await self._disconnect()
    
    async def _disconnect(self):
        """Disconnect from MT5 EA"""
        if not self.connected:
            return
        
        logger.info("Disconnecting from MT5 EA")
        self.connected = False
        
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                logger.debug(f"Error closing writer: {e}")
        
        self.reader = None
        self.writer = None
    
    async def _reconnect_loop(self):
        """Reconnection loop with exponential backoff"""
        logger.info("Reconnection loop started")
        
        while self.running:
            try:
                if not self.connected:
                    # Calculate backoff delay
                    if self.reconnect_attempts > 0:
                        delay = min(
                            self.config.reconnect_backoff_base ** self.reconnect_attempts,
                            self.config.reconnect_backoff_max
                        )
                        logger.info(f"Reconnecting in {delay:.1f}s (attempt {self.reconnect_attempts + 1})")
                        await asyncio.sleep(delay)
                    
                    # Try to connect
                    if self.reconnect_attempts < self.config.reconnect_max_attempts:
                        success = await self._connect()
                        if success:
                            logger.info("Connected to MT5 EA")
                            self.reconnect_attempts = 0
                        else:
                            self.reconnect_attempts += 1
                    else:
                        logger.error(f"Max reconnect attempts ({self.config.reconnect_max_attempts}) reached")
                        await asyncio.sleep(60.0)  # Wait before resetting counter
                        self.reconnect_attempts = 0
                
                await asyncio.sleep(1.0)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in reconnection loop: {e}")
                await asyncio.sleep(5.0)
        
        logger.info("Reconnection loop stopped")
    
    async def _heartbeat_loop(self):
        """Heartbeat loop to detect dead connections"""
        logger.info("Heartbeat loop started")
        
        while self.running:
            try:
                if self.connected:
                    # Check if we've received heartbeat recently
                    now = time.time()
                    if now - self.last_heartbeat_time > self.config.heartbeat_timeout:
                        logger.warning(
                            f"No heartbeat for {now - self.last_heartbeat_time:.1f}s, "
                            "disconnecting"
                        )
                        await self._disconnect()
                    else:
                        # Send ping
                        heartbeat = Heartbeat(
                            type="heartbeat.ping",
                            sender="python"
                        )
                        await self.send_message(heartbeat, timeout=1.0)
                
                await asyncio.sleep(self.config.heartbeat_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(5.0)
        
        logger.info("Heartbeat loop stopped")
