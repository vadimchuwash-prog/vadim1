# 📑 INDEX - Быстрый навигатор по модулям

## 🎯 Быстрый старт

**Хотите начать использовать модули?**
1. Читайте → `README.md`
2. Интегрируйте → `INTEGRATION.md`  
3. Изучайте итоги → `MODULE_SUMMARY.md`

**Нужна конкретная функция?**
- Форматирование → `utils.py`
- Константы → `constants.py`
- Аналитика → `analytics.py`
- Базовый класс → `bot_core.py`

---

## 📂 Все файлы модулей

### 🐍 Python модули (исполняемые)

| Файл | Строк | Размер | Назначение |
|------|-------|--------|------------|
| `__init__.py` | 17 | 542 B | Инициализация пакета, экспорт HybridTradingBot |
| `bot_core.py` | 251 | 9.7 KB | Базовый класс с инициализацией и утилитами |
| `analytics.py` | 160 | 6.1 KB | Black Box логирование, PnL Audit, Future Spy |
| `constants.py` | 199 | 7.8 KB | Константы, перечисления, emoji |
| `utils.py` | 340 | 11 KB | Форматирование, расчёты, валидация, время |
| `test_imports.py` | 100+ | 3.8 KB | Тесты импорта и базовых функций |

### 📄 Документация (читаемые)

| Файл | Строк | Размер | Назначение |
|------|-------|--------|------------|
| `README.md` | 107 | 3.9 KB | Основная документация модулей |
| `INTEGRATION.md` | 200+ | 7.1 KB | Руководство по интеграции с примерами |
| `MODULE_SUMMARY.md` | 250+ | ~10 KB | Детальная информация о всех модулях |
| `INDEX.md` | - | - | Этот файл - быстрый навигатор |

---

## 🗺️ Карта функционала

### bot_core.py - Ядро бота
```python
from bot_modules import HybridTradingBot

# Методы:
bot.log(msg, color)              # Цветное логирование
bot.log_debug(msg)               # Отладка
bot.get_effective_balance()      # Доступный баланс
bot.get_current_pnl()            # PnL с биржи
bot.refresh_wallet_status()      # Обновление баланса
```

### analytics.py - Аналитика
```python
from bot_modules.analytics import AnalyticsMixin

# Методы:
bot.log_blackbox(event, data)    # JSON логирование
bot.check_pnl_audit()            # Проверка PnL
bot.start_future_spy(...)        # Мониторинг "что если"
```

### constants.py - Константы
```python
from bot_modules.constants import EventType, PositionSide, Emoji

EventType.ENTRY                  # "ENTRY"
PositionSide.BUY                 # "Buy"
Emoji.PROFIT                     # "💰"

# Функции:
get_position_emoji(side)         # 📈 или 📉
get_pnl_emoji(pnl)              # 💰 или 💔
get_danger_emoji(level)         # 🔥 / ⚠️ / ✅
```

### utils.py - Утилиты
```python
from bot_modules.utils import *

# Форматирование:
format_usd(123.45)               # "$123.45"
format_percent(5.5)              # "5.50%"
format_price(43250.12, "BTCUSDT") # "43250.12"

# Расчёты:
calculate_pnl(entry, exit, size, side)  # PnL в USD
calculate_pnl_percent(entry, exit, side) # PnL в %
calculate_fee(amount, rate)      # Комиссия

# Округление:
round_price(99.876, 0.01)        # 99.88
round_size(0.0123, 0.001)        # 0.012

# Валидация:
is_valid_price(price)            # True/False
is_valid_size(size, min_size)    # True/False
is_valid_balance(balance, req)   # True/False

# Расстояния:
percent_diff(price1, price2)     # Разница в %
calculate_distance_percent(...)  # Расстояние до цели

# Время:
get_seconds_since(dt)            # Секунды с момента
get_minutes_since(dt)            # Минуты с момента
get_hours_since(dt)              # Часы с момента
```

---

## 🔍 Поиск по функционалу

**Нужно отформатировать число?**
→ `utils.py` → `format_usd()`, `format_percent()`, `format_price()`

**Нужно рассчитать PnL?**
→ `utils.py` → `calculate_pnl()`, `calculate_pnl_percent()`

**Нужно округлить цену?**
→ `utils.py` → `round_price()`, `round_size()`

**Нужно проверить данные?**
→ `utils.py` → `is_valid_price()`, `is_valid_size()`, `is_valid_balance()`

**Нужны константы?**
→ `constants.py` → `EventType`, `PositionSide`, `OrderType`, `Emoji`

**Нужно логировать событие?**
→ `analytics.py` → `log_blackbox()`, `check_pnl_audit()`

**Нужен базовый класс?**
→ `bot_core.py` → `HybridTradingBot`

---

## 🎓 Примеры использования

### Пример 1: Форматирование сообщения
```python
from bot_modules.utils import format_usd, format_percent
from bot_modules.constants import Emoji, PositionSide

pnl = 123.45
roi = 5.5
side = PositionSide.BUY

message = f"{Emoji.PROFIT} PnL: {format_usd(pnl)} ({format_percent(roi)})"
# Result: "💰 PnL: $123.45 (5.50%)"
```

### Пример 2: Валидация перед входом
```python
from bot_modules.utils import is_valid_price, is_valid_size, is_valid_balance

if not is_valid_price(entry_price):
    return "Invalid price!"

if not is_valid_size(position_size, min_size=0.001):
    return "Size too small!"

if not is_valid_balance(balance, required_amount):
    return "Insufficient balance!"

# Все проверки прошли, можно входить
```

### Пример 3: Логирование события
```python
from bot_modules.analytics import AnalyticsMixin
from bot_modules.constants import EventType, PositionSide

bot.log_blackbox(EventType.ENTRY, {
    "price": 43250.0,
    "size": 0.1,
    "side": PositionSide.BUY,
    "confluence": 85,
    "volatility": 1.2
})
```

---

## 📊 Статистика проекта

```
📦 Всего файлов: 10
📝 Строк кода: 1067 (Python)
📄 Строк документации: 557+
💾 Общий размер: ~60 KB

Распределение:
Python: 60% (6 файлов)
Docs:   40% (4 файла)
```

---

## 🛠️ Поддержка и развитие

### Текущая версия: 1.4.5

**Реализовано:**
- ✅ Базовый класс с полной инициализацией
- ✅ Утилиты для работы с данными
- ✅ Константы и перечисления
- ✅ Аналитика и логирование
- ✅ Документация и примеры

**Планируется:**
- ⏳ market_analysis.py
- ⏳ position_manager.py
- ⏳ order_manager.py
- ⏳ risk_manager.py
- ⏳ telegram_handler.py
- ⏳ ai_integration.py

---

## 📞 Быстрые ссылки

| Что нужно | Где искать |
|-----------|-----------|
| Начать работу | `README.md` |
| Примеры интеграции | `INTEGRATION.md` |
| Детальная информация | `MODULE_SUMMARY.md` |
| Базовый класс | `bot_core.py` |
| Утилиты | `utils.py` |
| Константы | `constants.py` |
| Аналитика | `analytics.py` |
| Тесты | `test_imports.py` |

---

**Создано**: 2026-01-27  
**Версия**: 1.4.5  
**Расположение**: `/home/user/vadim1/bot_final_v1.4.1/bot_modules/`

