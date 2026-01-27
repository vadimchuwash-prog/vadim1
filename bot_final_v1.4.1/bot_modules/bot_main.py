"""
🤖 HYBRID TRADING BOT v1.4.5 - MAIN CLASS
Главный класс бота с модульной архитектурой

КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.5:
- 🛡️ Защита от бесконечного цикла закрытия позиции
- 🔧 Все модули разбиты на логические компоненты
- ✅ Сохранен весь функционал из v1.4.4
"""

from bot_modules.bot_core import HybridTradingBot
from bot_modules.bot_indicators import BotIndicatorsMixin
from bot_modules.bot_positions import BotPositionsMixin
from bot_modules.bot_trailing import BotTrailingMixin
from bot_modules.bot_protection import BotProtectionMixin

try:
    from bot_modules.bot_orders import BotOrdersMixin
except ImportError:
    print("⚠️ bot_orders.py не найден, используем заглушку")
    class BotOrdersMixin: pass

try:
    from bot_modules.bot_monitoring import BotMonitoringMixin
except ImportError:
    print("⚠️ bot_monitoring.py не найден, методы мониторинга будут из bot_core")
    class BotMonitoringMixin: pass


class HybridTradingBotModular(
    BotIndicatorsMixin,
    BotPositionsMixin,
    BotTrailingMixin,
    BotOrdersMixin,
    BotProtectionMixin,
    BotMonitoringMixin,
    HybridTradingBot
):
    """
    🤖 Модульный торговый бот v1.4.5
    
    Наследует миксины в порядке приоритета:
    1. BotIndicatorsMixin - индикаторы и анализ
    2. BotPositionsMixin - управление позициями  
    3. BotTrailingMixin - трейлинг стопы
    4. BotOrdersMixin - управление ордерами
    5. BotProtectionMixin - умная защита DCA
    6. BotMonitoringMixin - мониторинг и телеграм
    7. HybridTradingBot - базовый класс
    """
    pass

# Для обратной совместимости
TradingBot = HybridTradingBotModular
