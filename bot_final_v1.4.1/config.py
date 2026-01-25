"""
🚀 UltraBTC HYBRID v1.4 FIXED - ENHANCED EDITION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✨ НОВОЕ В v1.3:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔧 КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ:
   - ✅ ИСПРАВЛЕН DCA для SHORT (теперь размещается ВЫШЕ входа)
   - ✅ Динамический TP от ATR в реальном времени
   - ✅ PnL Audit (детектор ошибок расчётов)
   - ✅ Blackbox JSON логирование (детальная история)
   - ✅ Future Spy (анализ упущенной прибыли)

🎯 ИЗ v1.1:
   - AI чат в Telegram
   - 7 многослойных фильтров
   - Confluence scoring (0-7)
   - Умная DCA сетка из ultrabtc7

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os

# 🔑 API KEYS
AI_GEMINI_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyDHrTaNZo8pR55GNmYLASC3yKtx-Y1HRcU")
AI_MODEL_NAME = "gemini-1.5-flash"  # Стабильная модель для вашего API ключа
TG_BOT_TOKEN = ""

HAS_AI = True

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '1m'

FUNDING_RATE_8H = 0.0001 

# 💰 УПРАВЛЕНИЕ КАПИТАЛОМ
LEVERAGE = 20                
ALLOWED_CAPITAL_PCT = 0.5

# 🔥 ГИБРИДНЫЙ ВХОД (3 стадии)
# Stage 1: Слабый сигнал (confluence 0-2)
STAGE1_MIN_ENTRY = 0.008
STAGE1_BASE_ENTRY = 0.012
STAGE1_MAX_ENTRY = 0.016

# Stage 2: Средний сигнал (confluence 3-4)
STAGE2_MIN_ENTRY = 0.013
STAGE2_BASE_ENTRY = 0.018
STAGE2_MAX_ENTRY = 0.023

# Stage 3: Сильный сигнал (confluence 5+)
STAGE3_MIN_ENTRY = 0.018
STAGE3_BASE_ENTRY = 0.025
STAGE3_MAX_ENTRY = 0.030

# 🔨 СЕТКА (из ultrabtc7 - БЕЗ ИЗМЕНЕНИЙ!)
SAFETY_ORDERS_COUNT = 5      
MIN_EXCHANGE_ORDER_USD = 5.1 

# Дистанции (из ultrabtc7)
HAMMER_DISTANCES_TREND = [0.006, 0.012, 0.020, 0.030, 0.045]
HAMMER_DISTANCES_RANGE = [0.010, 0.018, 0.030, 0.045, 0.065]

# Веса (из ultrabtc7)
HAMMER_WEIGHTS_TREND = [1.4, 2.0, 2.8, 3.5, 4.5]
HAMMER_WEIGHTS_RANGE = [1.6, 2.2, 3.0, 4.0, 5.0]

# 🎯 ВЫХОД (из ultrabtc7 - БЕЗ ИЗМЕНЕНИЙ!)
TP_STEPS_HIGH_VOL = [0.0070, 0.0060, 0.0050, 0.0040, 0.0030]  
TP_STEPS_MED_VOL = [0.0060, 0.0050, 0.0040, 0.0035, 0.0030]   
TP_STEPS_LOW_VOL = [0.0050, 0.0040, 0.0035, 0.0030, 0.0025]   

# 🔄 TRAILING STOP (из ultrabtc7)
TRAILING_ENABLED = True           
TRAILING_ACTIVATION_PCT = 0.0080   
TRAILING_CALLBACK_PCT = 0.0035     
TRAILING_UPDATE_INTERVAL = 3       

# 🛡️ ЗАЩИТА
MAX_ACCOUNT_LOSS_PCT = 0.30    

# 📊 ГИБРИДНЫЕ ФИЛЬТРЫ
QUALITY_FILTER_ENABLED = True
MIN_VOLATILITY_PCT = 0.0003
MIN_VOLUME_RATIO = 1.0
RSI_SAFE_MIN = 30
RSI_SAFE_MAX = 70
KNIFE_PROTECTION_PCT = 0.015
MIN_MICROTREND_CANDLES = 1

# 🎯 CONFLUENCE СИСТЕМА
MIN_CONFLUENCE_SCORE = 1
CONFLUENCE_STAGE1_MAX = 2
CONFLUENCE_STAGE2_MAX = 4

# ⏳ ТАЙМЕР ОХЛАЖДЕНИЯ
MIN_TIME_BETWEEN_TRADES = 3600
DAILY_TRADE_LIMIT = 150

# 💸 КОМИССИИ
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005

# ФАЙЛЫ
LOG_FILE = "bot_hybrid.log"
CSV_FILE = "trades_hybrid.csv"
MARKET_LOG_FILE = "market_hybrid.csv"
SECRETS_FILE = "encrypted_config.bin"
KEY_FILE = "secret.key"

class Col:
    WHITE = '\033[97m'    # ← ДОБАВЛЕНО!
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[95m'
    GRAY = '\033[90m'
