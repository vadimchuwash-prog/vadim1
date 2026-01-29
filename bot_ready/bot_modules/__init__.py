"""
🤖 BOT MODULES PACKAGE v1.4.8
Модульная структура торгового бота

ИСПРАВЛЕНИЯ v1.4.8:
- 🔥 Range Trailing активируется ТОЛЬКО при +0.15% прибыли (не сразу!)
- 🔥 Трейлинг срабатывает ТОЛЬКО когда позиция в прибыли
- 🔥 Закрытие ЛИМИТНЫМ ордером с перевыставлением каждые 5 сек
- 📋 Новые настройки: RANGE_TRAILING_ACTIVATION_PROFIT, TRAILING_CLOSE_USE_LIMIT

ИСПРАВЛЕНИЯ v1.4.7:
- 🔥 Добавлен мониторинг SL ордера в run() (КРИТИЧЕСКИЙ БАГ!)
- 🔧 Убран дублирующий answer_callback в Telegram
- 🔒 Убран захардкоженный API ключ из config.py
- 📦 Добавлен экспорт AnalyticsMixin

Модули:
- bot_core: Базовый класс с инициализацией и логированием
- bot_positions: Управление позициями (открытие, закрытие, синхронизация)
- bot_orders: Управление ордерами (TP, DCA, Stop Loss)
- bot_indicators: Индикаторы и технический анализ
- bot_trailing: Трейлинг стопы (Trend + Range)
- bot_protection: Умная защита DCA v1.4.3
- bot_monitoring: Мониторинг, Telegram, AI чат
- bot_main: Главный класс (объединяет все миксины)
- analytics: Black Box логирование, PnL Audit, Future Spy

Утилиты:
- constants: Константы, перечисления, emoji
- utils: Форматирование и расчеты
"""

from .bot_core import HybridTradingBot
from .bot_positions import BotPositionsMixin
from .bot_orders import BotOrdersMixin
from .bot_indicators import BotIndicatorsMixin
from .bot_trailing import BotTrailingMixin
from .bot_protection import BotProtectionMixin
from .bot_monitoring import BotMonitoringMixin
from .analytics import AnalyticsMixin  # 🆕 v1.4.7: Добавлен экспорт

# Главный класс с модульной архитектурой
from .bot_main import HybridTradingBotModular, TradingBot

__version__ = "1.4.8"
__all__ = [
    'HybridTradingBot',
    'BotPositionsMixin',
    'BotOrdersMixin',
    'BotIndicatorsMixin',
    'BotTrailingMixin',
    'BotProtectionMixin',
    'BotMonitoringMixin',
    'AnalyticsMixin',  # 🆕 v1.4.7
    'HybridTradingBotModular',
    'TradingBot'
]
