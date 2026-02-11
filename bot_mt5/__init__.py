"""
bot_mt5 - High-Frequency Trading Bot for MetaTrader 5

Modular, asynchronous, low-latency trading system with AI integration.

Architecture:
- ai_manager: AI model worker pool with async interface
- core: Trading orchestrator and risk management
- mt5_comm: MT5 socket communication with reconnection
- schemas: Pydantic models for validation
- utils: Config, logging, rate limiting

Version: 2.0.0-refactor
Author: Manus AI + User Collaboration
Date: 2026-02-11
"""

__version__ = "2.0.0-refactor"
__author__ = "Manus AI + User"

# Public API exports will be added as modules are implemented
__all__ = []
