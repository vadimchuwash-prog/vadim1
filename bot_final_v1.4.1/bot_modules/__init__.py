"""
🤖 BOT MODULES PACKAGE v1.4.5
Модульная структура торгового бота

Модули:
- bot_core: Базовый класс с инициализацией и логированием
- bot_positions: Управление позициями (открытие, закрытие, синхронизация)
- bot_orders: Управление ордерами (TP, DCA, Stop Loss)
- bot_indicators: Индикаторы и технический анализ
- bot_trailing: Трейлинг стопы (Trend + Range)
- bot_protection: Умная защита DCA v1.4.3
- bot_main: Главный класс (объединяет все миксины)

Утилиты:
- constants: Константы, перечисления, emoji
- utils: Форматирование и расчеты
- analytics: Black Box логирование, PnL Audit
"""

from .bot_core import HybridTradingBot
from .bot_positions import BotPositionsMixin
from .bot_orders import BotOrdersMixin
from .bot_indicators import BotIndicatorsMixin
from .bot_trailing import BotTrailingMixin
from .bot_protection import BotProtectionMixin

# Главный класс с модульной архитектурой
from .bot_main import HybridTradingBotModular, TradingBot

__version__ = "1.4.5"
__all__ = [
    'HybridTradingBot',
    'BotPositionsMixin',
    'BotOrdersMixin',
    'BotIndicatorsMixin',
    'BotTrailingMixin',
    'BotProtectionMixin',
    'HybridTradingBotModular',
    'TradingBot'
]
