# 🚀 QUICK REFERENCE - Быстрая шпаргалка

## 📍 Расположение
```
/home/user/vadim1/bot_final_v1.4.1/bot_modules/
```

## 🎯 Начать здесь
```bash
# Смотрите быстрый навигатор
cat /home/user/vadim1/bot_final_v1.4.1/bot_modules/INDEX.md

# Смотрите основную документацию
cat /home/user/vadim1/bot_final_v1.4.1/bot_modules/README.md
```

## ⚡ Самые используемые функции

### Форматирование
```python
from bot_modules.utils import format_usd, format_percent, format_price

format_usd(123.45)               # "$123.45"
format_percent(5.5)              # "5.50%"
format_price(43250.12, "BTCUSDT") # "43250.12"
```

### Расчёты
```python
from bot_modules.utils import calculate_pnl, calculate_fee, round_price

calculate_pnl(100, 110, 1.0, "Buy")  # 10.0
calculate_fee(1000, 0.0004)          # 0.4
round_price(99.876, 0.01)            # 99.88
```

### Валидация
```python
from bot_modules.utils import is_valid_price, is_valid_size

is_valid_price(100.0)            # True
is_valid_size(0.001, 0.001)      # True
```

### Константы
```python
from bot_modules.constants import EventType, PositionSide, Emoji

EventType.ENTRY                  # "ENTRY"
PositionSide.BUY                 # "Buy"
Emoji.PROFIT                     # "💰"
```

### Emoji функции
```python
from bot_modules.constants import get_position_emoji, get_pnl_emoji

get_position_emoji("Buy")        # "📈"
get_pnl_emoji(123.45)           # "💰"
```

### Логирование
```python
from bot_modules.analytics import AnalyticsMixin
from bot_modules.constants import EventType

bot.log_blackbox(EventType.ENTRY, {"price": 100, "size": 1})
bot.check_pnl_audit()
```

## 📂 Структура файлов

```
bot_modules/
├── __init__.py           # Инициализация
├── bot_core.py          # Базовый класс
├── analytics.py         # Аналитика
├── constants.py         # Константы
├── utils.py             # Утилиты
├── test_imports.py      # Тесты
├── INDEX.md             # ⭐ Навигатор
├── README.md            # Документация
├── INTEGRATION.md       # Интеграция
├── MODULE_SUMMARY.md    # Детали
└── QUICK_REFERENCE.md   # Этот файл
```

## 🎓 3 способа использования

### 1. Утилиты (Самый простой)
```python
from bot_modules.utils import format_usd
from bot_modules.constants import Emoji

message = f"{Emoji.PROFIT} {format_usd(pnl)}"
```

### 2. Базовый класс
```python
from bot_modules import HybridTradingBot

bot = HybridTradingBot(exchange, telegram_bot)
bot.log("Message", Col.GREEN)
```

### 3. Миксины
```python
from bot_modules.bot_core import HybridTradingBot
from bot_modules.analytics import AnalyticsMixin

class MyBot(HybridTradingBot, AnalyticsMixin):
    pass
```

## 🔍 Быстрый поиск функций

| Нужно | Модуль | Функция |
|-------|--------|---------|
| Отформатировать USD | utils | `format_usd()` |
| Отформатировать % | utils | `format_percent()` |
| Рассчитать PnL | utils | `calculate_pnl()` |
| Округлить цену | utils | `round_price()` |
| Проверить цену | utils | `is_valid_price()` |
| Получить emoji | constants | `get_position_emoji()` |
| Залогировать событие | analytics | `log_blackbox()` |
| Проверить PnL | analytics | `check_pnl_audit()` |

## 📊 Статистика

```
Файлов:  10
Строк:   1925
Размер:  ~74 KB
```

## 🆘 Помощь

**Не знаете с чего начать?**
→ Читайте `INDEX.md`

**Нужны примеры?**
→ Читайте `INTEGRATION.md`

**Нужны детали?**
→ Читайте `MODULE_SUMMARY.md`

**Нужна функция?**
→ Смотрите таблицу выше

## ⚡ Команды

```bash
# Список всех файлов
ls -lh /home/user/vadim1/bot_final_v1.4.1/bot_modules/

# Смотреть документацию
cat bot_modules/INDEX.md
cat bot_modules/README.md
cat bot_modules/INTEGRATION.md

# Запустить тесты (требуются зависимости)
python bot_modules/test_imports.py
```

---

**Версия**: 1.4.5  
**Дата**: 2026-01-27  
**Статус**: ✅ Готово
