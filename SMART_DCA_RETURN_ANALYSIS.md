# 🧠 УМНЫЙ ВОЗВРАТ DCA - АНАЛИЗ И АЛГОРИТМ

## 📅 Дата: 2026-01-26

---

## 🎯 НОВОЕ ТРЕБОВАНИЕ:

> "При восстановлении DCA НЕ ВОЗВРАЩАЕТСЯ обратно, нет пусть возвращается обратно,
> но когда это уже безопасно и нет риска новой волны падения,
> либо очень снижена волатильность"

---

## 💡 КОНЦЕПЦИЯ: "Умный возврат с проверкой безопасности"

DCA должен работать как **двухстороннее реле с задержкой**:
- ⚡ **БЫСТРО отодвигается** при падении (защита)
- 🐌 **МЕДЛЕННО возвращается** только при подтверждении безопасности

---

## 🔐 КРИТЕРИИ БЕЗОПАСНОСТИ ДЛЯ ВОЗВРАТА:

### 1. 📉 ВОЛАТИЛЬНОСТЬ СНИЗИЛАСЬ
```python
# Текущая волатильность должна быть НИЖЕ чем при отодвигании
safety_check_volatility = current_ATR < (peak_ATR * 0.7)  # -30% от пика
```

**Логика:** Если ATR упал на 30%+, значит рынок успокоился

---

### 2. ⏳ ПРОШЛО ВРЕМЯ СТАБИЛИЗАЦИИ
```python
# Минимум 10-15 минут без новых просадок
time_since_last_drawdown_increase = now - last_drawdown_increase_time
safety_check_time = time_since_last_drawdown_increase > 600  # 10 минут
```

**Логика:** Быстрое восстановление может быть ложным (dead cat bounce)

---

### 3. 📊 ЦЕНА НЕ ДЕЛАЕТ НОВЫХ ЭКСТРЕМУМОВ
```python
# Для LONG: цена не делает новых минимумов
# Для SHORT: цена не делает новых максимумов
if position_side == "Buy":
    safety_check_price = last_price > lowest_price_in_last_N_candles
else:
    safety_check_price = last_price < highest_price_in_last_N_candles
```

**Логика:** Если делаются новые минимумы/максимумы - падение продолжается

---

### 4. 🎚️ RSI В БЕЗОПАСНОЙ ЗОНЕ
```python
# RSI не в экстремальной зоне
if position_side == "Buy":
    safety_check_rsi = 35 < RSI < 65  # Не перепроданность
else:
    safety_check_rsi = 35 < RSI < 65  # Не перекупленность
```

**Логика:** Экстремальный RSI = риск продолжения движения

---

### 5. 📈 ВОССТАНОВЛЕНИЕ ЗНАЧИТЕЛЬНОЕ
```python
# Цена восстановилась минимум на 50% от просадки
recovery_pct = (current_price - lowest_price) / (entry_price - lowest_price)
safety_check_recovery = recovery_pct > 0.5  # 50% восстановление
```

**Логика:** Небольшое восстановление может быть коррекцией в падении

---

## 🔧 АЛГОРИТМ РАБОТЫ:

### Переменные состояния (добавить в `__init__`):

```python
# Защита DCA
self.max_drawdown_from_entry = 0.0       # Максимальная просадка (%)
self.protection_multiplier = 1.0          # Текущий множитель защиты
self.last_drawdown_increase_time = None   # Когда последний раз увеличивалась просадка
self.peak_volatility_during_drawdown = 0.0  # Пиковая волатильность при просадке
self.lowest_price_since_entry = 0.0       # Минимум для LONG
self.highest_price_since_entry = 0.0      # Максимум для SHORT
```

---

### Функция обновления защиты (в `place_limit_dca()`):

```python
def update_protection_multiplier(self):
    """🛡️ Обновление множителя защиты DCA"""
    if not self.in_position or self.avg_price == 0:
        return

    # === ШАГ 1: Рассчитываем текущую просадку ===
    side_mult = 1 if self.position_side == "Buy" else -1
    unrealized_pct = ((self.last_price - self.avg_price) / self.avg_price) * side_mult * 100

    # === ШАГ 2: Отслеживаем экстремумы ===
    if self.position_side == "Buy":
        if self.lowest_price_since_entry == 0 or self.last_price < self.lowest_price_since_entry:
            self.lowest_price_since_entry = self.last_price
    else:
        if self.highest_price_since_entry == 0 or self.last_price > self.highest_price_since_entry:
            self.highest_price_since_entry = self.last_price

    # === ШАГ 3: УВЕЛИЧЕНИЕ ЗАЩИТЫ (быстро) ===
    if unrealized_pct < 0:  # Просадка
        current_drawdown = abs(unrealized_pct)

        # Если просадка увеличилась
        if current_drawdown > self.max_drawdown_from_entry:
            self.max_drawdown_from_entry = current_drawdown
            self.last_drawdown_increase_time = datetime.now()

            # Запоминаем пиковую волатильность
            if self.current_volatility > self.peak_volatility_during_drawdown:
                self.peak_volatility_during_drawdown = self.current_volatility

            # Рассчитываем новый множитель (АГРЕССИВНО)
            PROTECTION_AGGRESSION = 15  # 15% за каждый 1% просадки
            new_multiplier = 1.0 + (self.max_drawdown_from_entry * PROTECTION_AGGRESSION)

            if new_multiplier > self.protection_multiplier:
                self.protection_multiplier = new_multiplier
                self.log(f"🛡️ Protection INCREASED: {self.protection_multiplier:.2f}x (DD: {self.max_drawdown_from_entry:.2f}%)", Col.YELLOW)

    # === ШАГ 4: УМЕНЬШЕНИЕ ЗАЩИТЫ (медленно, с проверками) ===
    elif self.protection_multiplier > 1.0:
        # Проверяем все условия безопасности
        safety_checks = self.check_safety_for_dca_return()

        if safety_checks['is_safe']:
            # Медленное снижение (0.5% каждый вызов)
            DECAY_RATE = 0.005
            old_mult = self.protection_multiplier
            self.protection_multiplier = max(1.0, self.protection_multiplier - DECAY_RATE)

            if self.protection_multiplier < old_mult:
                self.log(f"🔓 Protection DECREASED: {self.protection_multiplier:.2f}x (conditions: {safety_checks['passed']})", Col.GREEN)
        else:
            # Не безопасно - не снижаем
            failed = safety_checks['failed']
            self.log(f"⏸️ Protection HOLD: {self.protection_multiplier:.2f}x (waiting: {', '.join(failed)})", Col.GRAY)


def check_safety_for_dca_return(self):
    """🔐 Проверка безопасности для возврата DCA ближе"""
    checks = {
        'volatility': False,
        'time': False,
        'price_extreme': False,
        'rsi': False,
        'recovery': False
    }

    # 1. Волатильность снизилась?
    if self.peak_volatility_during_drawdown > 0:
        checks['volatility'] = self.current_volatility < (self.peak_volatility_during_drawdown * 0.7)
    else:
        checks['volatility'] = True  # Нет данных - разрешаем

    # 2. Прошло время?
    if self.last_drawdown_increase_time:
        time_elapsed = (datetime.now() - self.last_drawdown_increase_time).total_seconds()
        checks['time'] = time_elapsed > 600  # 10 минут
    else:
        checks['time'] = True

    # 3. Цена не делает новых экстремумов?
    if self.current_market_df is not None and len(self.current_market_df) >= 5:
        last_5_candles = self.current_market_df.tail(5)

        if self.position_side == "Buy":
            # Для LONG: текущая цена выше минимума последних 5 свечей
            recent_low = last_5_candles['low'].min()
            checks['price_extreme'] = self.last_price > recent_low * 1.001  # +0.1% запас
        else:
            # Для SHORT: текущая цена ниже максимума последних 5 свечей
            recent_high = last_5_candles['high'].max()
            checks['price_extreme'] = self.last_price < recent_high * 0.999  # -0.1% запас
    else:
        checks['price_extreme'] = True

    # 4. RSI в безопасной зоне?
    if self.current_market_df is not None:
        current_rsi = self.current_market_df['RSI'].iloc[-2]
        checks['rsi'] = 35 < current_rsi < 65
    else:
        checks['rsi'] = True

    # 5. Восстановление значительное?
    if self.position_side == "Buy" and self.lowest_price_since_entry > 0:
        recovery_ratio = (self.last_price - self.lowest_price_since_entry) / (self.avg_price - self.lowest_price_since_entry)
        checks['recovery'] = recovery_ratio > 0.4  # 40% восстановление
    elif self.position_side == "Sell" and self.highest_price_since_entry > 0:
        recovery_ratio = (self.highest_price_since_entry - self.last_price) / (self.highest_price_since_entry - self.avg_price)
        checks['recovery'] = recovery_ratio > 0.4
    else:
        checks['recovery'] = True

    # Итоговая оценка
    passed_checks = [k for k, v in checks.items() if v]
    failed_checks = [k for k, v in checks.items() if not v]

    # Требуем минимум 4 из 5 проверок
    is_safe = len(passed_checks) >= 4

    return {
        'is_safe': is_safe,
        'checks': checks,
        'passed': passed_checks,
        'failed': failed_checks,
        'score': f"{len(passed_checks)}/5"
    }
```

---

## 📊 ПРИМЕРЫ РАБОТЫ:

### Пример 1: Быстрое падение, медленное восстановление

```
00:00 | Вход LONG @ 90,000$ | protection = 1.0x
00:05 | Падение до 88,000$ (-2.2%) | protection = 1.33x ⚡ БЫСТРО
      | ATR = 0.004, RSI = 28
00:10 | Восстановление до 89,000$ (-1.1%) | protection = 1.33x ⏸️ НЕ СНИЖАЕМ
      | Причина: time < 10min, RSI < 35
00:15 | Стабилизация @ 89,200$ (-0.9%) | protection = 1.32x 🐌 МЕДЛЕННО
      | ✅ time > 10min, ✅ RSI = 45, ✅ ATR = 0.0028 (-30%), ✅ recovery = 50%
00:20 | Продолжение восстановления | protection = 1.31x → 1.30x → ... → 1.0x
```

**Итог:** DCA вернулся ближе через 10+ минут после подтверждения безопасности

---

### Пример 2: Ложное восстановление (dead cat bounce)

```
00:00 | Вход LONG @ 90,000$ | protection = 1.0x
00:05 | Падение до 88,000$ (-2.2%) | protection = 1.33x ⚡
00:08 | Восстановление до 89,000$ | protection = 1.33x ⏸️ НЕ СНИЖАЕМ
      | Причина: ❌ time < 10min
00:10 | НОВОЕ падение до 87,000$ (-3.3%) | protection = 1.50x ⚡ УВЕЛИЧИВАЕМ
      | ✅ Защита сработала! DCA не успел вернуться ближе
```

**Итог:** Система не поверила быстрому восстановлению - ПРАВИЛЬНО!

---

### Пример 3: Стабильное восстановление

```
00:00 | Вход LONG @ 90,000$ | protection = 1.0x
00:05 | Падение до 87,500$ (-2.8%) | protection = 1.42x ⚡
      | ATR = 0.005, RSI = 25
00:15 | Восстановление до 89,000$ (-1.1%) | protection = 1.42x ⏸️ HOLD
      | Checks: ✅ time, ❌ volatility (ATR = 0.004), ❌ RSI = 32
00:25 | Стабилизация @ 89,500$ (-0.6%) | protection = 1.41x 🐌 START
      | Checks: ✅ time, ✅ volatility (ATR = 0.0032), ✅ RSI = 42, ✅ recovery = 60%, ✅ no new lows
00:30 | protection = 1.40x
00:35 | protection = 1.39x
...
01:00 | protection = 1.10x → продолжает медленно снижаться
```

**Итог:** Постепенное снижение защиты при стабильных условиях

---

## ⚙️ НАСТРОЙКИ:

```python
# В config.py добавить:

# 🛡️ УМНАЯ ЗАЩИТА DCA
PROTECTION_AGGRESSION = 15         # Множитель при просадке (15 = +15% за каждый 1% DD)
PROTECTION_DECAY_RATE = 0.005      # Скорость снижения (0.5% за цикл)
PROTECTION_MIN_SAFE_TIME = 600     # Минимум 10 минут без новых просадок
PROTECTION_VOLATILITY_RATIO = 0.7  # Волатильность должна упасть до 70% от пика
PROTECTION_RECOVERY_MIN = 0.4      # Минимум 40% восстановление
PROTECTION_MIN_CHECKS = 4          # Минимум 4 из 5 проверок для снижения
```

---

## 🎯 ПРЕИМУЩЕСТВА:

### ✅ По сравнению с "храповиком":
1. ✅ DCA всё равно быстро отодвигается при падении
2. ✅ DCA МОЖЕТ вернуться, но ТОЛЬКО когда безопасно
3. ✅ Не "застревает" далеко при длительной стабилизации
4. ✅ Адаптируется к реальным условиям рынка

### ✅ По сравнению с текущей системой:
1. ✅ Не переключается мгновенно при изменении ADX
2. ✅ Имеет "память" о просадках
3. ✅ Учитывает несколько факторов (не только ADX)
4. ✅ Защищает от dead cat bounce
5. ✅ Медленное возвращение = безопасность

---

## 🔄 ВЗАИМОДЕЙСТВИЕ С TREND/RANGE:

```python
# В place_limit_dca() после получения base_dist:

# 1. Получаем базовую дистанцию (TREND/RANGE)
dists, weights = self.get_dca_parameters()
base_dist = dists[self.safety_count]

# 2. Применяем старые множители (ATR, RSI, geo)
base_multiplier = self.get_smart_distance_multiplier(self.safety_count)

# 3. Обновляем защиту (НОВОЕ!)
self.update_protection_multiplier()

# 4. Итоговая дистанция
actual_dist = base_dist * base_multiplier * self.protection_multiplier
```

**Важно:** TREND/RANGE продолжает определять БАЗУ, а `protection_multiplier` работает ПОВЕРХ!

---

## 📈 СРАВНЕНИЕ С "ХРАПОВИКОМ":

| Ситуация | Храповик | Умный возврат |
|----------|----------|---------------|
| Падение -2% | +30% к DCA ⚡ | +30% к DCA ⚡ |
| Быстрое восстановление (5 мин) | Держит +30% 🔒 | Держит +30% ⏸️ |
| Стабилизация (15 мин) | Держит +30% 🔒 | Снижает до +25% 🐌 |
| Длительная стабильность (1 час) | Держит +30% 🔒 | Снижает до +5% 🐌 |
| Новое падение | +40% ⚡ | +40% ⚡ |

**Вывод:** Умный возврат = баланс между защитой и эффективностью

---

## 🧪 ДОПОЛНИТЕЛЬНЫЕ УЛУЧШЕНИЯ (опционально):

### 1. Адаптивная скорость снижения
```python
# Чем больше проверок пройдено, тем быстрее снижение
safety_score = len(passed_checks) / 5.0
DECAY_RATE = 0.005 * safety_score  # От 0.002 до 0.005
```

### 2. Визуализация в дашборде
```python
safety_checks = self.check_safety_for_dca_return()
if self.protection_multiplier > 1.0:
    message += f"\n🛡️ Защита: <b>{self.protection_multiplier:.2f}x</b> | Safety: {safety_checks['score']}"
```

### 3. Логирование событий
```python
# При увеличении защиты
self.log(f"🛡️ ↑ Protection: {self.protection_multiplier:.2f}x | DD: {self.max_drawdown_from_entry:.2f}%", Col.YELLOW)

# При снижении защиты
self.log(f"🔓 ↓ Protection: {self.protection_multiplier:.2f}x | Checks: {safety_checks['score']}", Col.GREEN)

# При блокировке снижения
self.log(f"⏸️ Protection HOLD: {self.protection_multiplier:.2f}x | Failed: {', '.join(failed)}", Col.GRAY)
```

---

## ✅ ИТОГ:

Эта система:
- ✅ Быстро защищает при падении (15% за каждый 1% DD)
- ✅ Медленно возвращает при восстановлении (0.5% за цикл)
- ✅ Требует 4 из 5 проверок безопасности для возврата
- ✅ Защищает от dead cat bounce (минимум 10 минут)
- ✅ Адаптируется к волатильности, RSI, экстремумам
- ✅ Не конфликтует с TREND/RANGE режимами

**Код:** ~100 строк (2 новые функции + инициализация)

**Сложность:** Средняя (но логика понятная)

**Результат:** DCA работает как умный торговец - быстро защищается, медленно рискует

---

**Автор:** Claude Code AI
**Версия:** Smart Return Algorithm v1.0
**Статус:** 📋 ГОТОВО К ОБСУЖДЕНИЮ
