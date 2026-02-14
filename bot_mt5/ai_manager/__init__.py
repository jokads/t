"""
AI Manager - Async AI model worker pool

Provides async interface to AI models with:
- Worker pool (dedicated processes)
- Timeouts and circuit-breaker
- Fallback rule-based signals
"""

from bot_mt5.ai_manager.manager import AIManager

__all__ = ["AIManager"]
