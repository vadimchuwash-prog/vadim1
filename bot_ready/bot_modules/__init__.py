"""
🤖 BOT MODULES PACKAGE v1.5.0
Модульная структура торгового бота

🆕 v1.5.0: SMART DCA + FLIP SYSTEM
- 🔨 DCA: 1 уровень, вес 5x (отскок 0.17% = профит)
- 🛡️ Динамический SL: 3% → 2% (сужается после DCA)
- 🔄 Smart Flip: при SL + сильном ADX → разворот позиции
- 🔧 SL обновляется после каждого DCA (критический баг-фикс!)
- ⚡ Max loss ограничен ~$130 вместо $516

Модули:
- bot_core: Базовый класс с инициализацией и логированием
- bot_positions: Управление позициями (открытие, закрытие, синхронизация)
- bot_orders: Управление ордерами (TP, DCA, Stop Loss)
- bot_indicators: Индикаторы и технический анализ
- bot_trailing: Трейлинг стопы (Trend + Range)
- bot_protection: Умная защита DCA
- bot_flip: 🆕 Smart Flip (разворот при движении против)
- bot_monitoring: Мониторинг, Telegram, AI чат
- bot_main: Главный класс (объединяет все миксины)
- analytics: Black Box логирование, PnL Audit, Future Spy
"""

from .bot_core import HybridTradingBot
from .bot_positions import BotPositionsMixin
from .bot_orders import BotOrdersMixin
from .bot_indicators import BotIndicatorsMixin
from .bot_trailing import BotTrailingMixin
from .bot_protection import BotProtectionMixin
from .bot_monitoring import BotMonitoringMixin
from .bot_flip import BotFlipMixin  # 🆕 v1.5.0
from .analytics import AnalyticsMixin

# Главный класс с модульной архитектурой
from .bot_main import HybridTradingBotModular, TradingBot

__version__ = "1.5.0"
__all__ = [
    'HybridTradingBot',
    'BotPositionsMixin',
    'BotOrdersMixin',
    'BotIndicatorsMixin',
    'BotTrailingMixin',
    'BotProtectionMixin',
    'BotMonitoringMixin',
    'BotFlipMixin',  # 🆕 v1.5.0
    'AnalyticsMixin',
    'HybridTradingBotModular',
    'TradingBot'
]
