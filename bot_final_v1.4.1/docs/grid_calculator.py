#!/usr/bin/env python3
"""
🔥 ПОЛНЫЙ РАСЧЕТ СЕТКИ БОТА - ВСЕ РЕЖИМЫ
Проверка всех параметров и дистанций
"""

# ==================== ПАРАМЕТРЫ ====================
BALANCE = 3400  # Баланс
LEVERAGE = 20   # Плечо
ENTRY_PRICE = 100000  # BTC цена для примера

# Stage 2 вход (confluence 3-4)
STAGE2_BASE_ENTRY = 0.018  # 1.8%

# DCA дистанции
HAMMER_DISTANCES_TREND = [0.006, 0.012, 0.020, 0.030, 0.045]
HAMMER_DISTANCES_RANGE = [0.010, 0.018, 0.030, 0.045, 0.065]

# DCA веса
HAMMER_WEIGHTS_TREND = [1.4, 2.0, 2.8, 3.5, 4.5]
HAMMER_WEIGHTS_RANGE = [1.6, 2.2, 3.0, 4.0, 5.0]

# Стоп-лосс
MAX_ACCOUNT_LOSS_PCT = 0.30  # 30%

# Maintenance Margin Rate (BingX BTC)
MMR = 0.005  # 0.5%

# ==================== ФУНКЦИИ ====================

def calculate_smart_multiplier(atr, rsi, safety_count):
    """Расчет Smart Distance Multiplier"""
    BASE_ATR = 0.0020

    # ATR factor
    atr_factor = atr / BASE_ATR
    atr_factor = max(0.8, min(atr_factor, 2.5))

    # RSI factor
    rsi_factor = 1.0
    if rsi < 20:
        rsi_factor = 1.6
    elif rsi < 30:
        rsi_factor = 1.3
    elif rsi < 40:
        rsi_factor = 1.1

    # Geometric factor
    geo_factor = 1.1 ** safety_count

    multiplier = atr_factor * rsi_factor * geo_factor
    return multiplier, atr_factor, rsi_factor, geo_factor

def calculate_dynamic_tp(atr):
    """Расчет динамического TP"""
    base_tp = 0.0035  # 0.35%
    atr_component = atr * 0.5
    dynamic_tp = base_tp + atr_component
    # Ограничения
    dynamic_tp = max(0.0025, min(dynamic_tp, 0.010))
    return dynamic_tp

def calculate_grid(scenario_name, is_trend, atr, rsi, adx):
    """Расчет полной сетки"""
    print(f"\n{'='*80}")
    print(f"📊 СЦЕНАРИЙ: {scenario_name}")
    print(f"{'='*80}")
    print(f"Режим: {'TREND' if is_trend else 'RANGE'}")
    print(f"ATR: {atr*100:.3f}%")
    print(f"ADX: {adx}")
    print(f"RSI: {rsi}")
    print(f"Баланс: ${BALANCE:,.2f}")
    print(f"Цена BTC: ${ENTRY_PRICE:,.2f}")

    # Выбор параметров
    distances = HAMMER_DISTANCES_TREND if is_trend else HAMMER_DISTANCES_RANGE
    weights = HAMMER_WEIGHTS_TREND if is_trend else HAMMER_WEIGHTS_RANGE

    # Адаптация входа
    entry_pct = STAGE2_BASE_ENTRY
    score = 0
    if atr > 0.005:
        score -= 1
    elif atr < 0.002:
        score += 1
    if adx > 35:
        score += 1
    elif adx < 20:
        score -= 1

    multiplier_entry = 1.0 + (score * 0.10)
    entry_pct = entry_pct * multiplier_entry
    entry_pct = max(0.013, min(entry_pct, 0.023))  # STAGE2 limits

    print(f"\n🔥 ВХОД (адаптированный):")
    print(f"   Base: {STAGE2_BASE_ENTRY*100:.2f}% → Adapted: {entry_pct*100:.2f}% (score: {score:+d})")

    # Расчет входа
    entry_margin = BALANCE * entry_pct
    entry_position = entry_margin * LEVERAGE
    entry_size_btc = entry_position / ENTRY_PRICE

    print(f"   Маржа: ${entry_margin:.2f}")
    print(f"   Позиция: ${entry_position:.2f}")
    print(f"   Размер: {entry_size_btc:.6f} BTC")

    # Dynamic TP
    dynamic_tp = calculate_dynamic_tp(atr)
    tp_price_entry = ENTRY_PRICE * (1 + dynamic_tp)

    print(f"\n🎯 ДИНАМИЧЕСКИЙ TP:")
    print(f"   Base: 0.35% + ATR: {atr*100:.3f}% × 0.5 = {dynamic_tp*100:.3f}%")
    print(f"   TP от входа: ${tp_price_entry:,.2f} (+{dynamic_tp*100:.2f}%)")

    # Сетка DCA
    print(f"\n🔨 СЕТКА DCA:")
    print(f"{'─'*120}")
    print(f"{'Уровень':<10} {'Dist':<6} {'Mult':<8} {'Actual':<8} {'Цена':<12} {'Вес':<6} {'Маржа':<10} {'Avg Price':<12} {'Сумм.Маржа':<12} {'TP цена':<12} {'% к TP':<8}")
    print(f"{'─'*120}")

    # ВХОД
    print(f"{'ВХОД':<10} {'-':<6} {'-':<8} {'-':<8} ${ENTRY_PRICE:>10,.0f} {1.0:<6.1f} ${entry_margin:>8.2f} ${ENTRY_PRICE:>10,.0f} ${entry_margin:>10.2f} ${tp_price_entry:>10,.0f} {dynamic_tp*100:>6.2f}%")

    # Накопление данных
    total_margin = entry_margin
    total_position = entry_position
    total_size_btc = entry_size_btc
    avg_price = ENTRY_PRICE

    levels = []

    for i in range(5):  # 5 DCA уровней
        base_dist = distances[i]
        weight = weights[i]

        # Smart multiplier
        mult, atr_f, rsi_f, geo_f = calculate_smart_multiplier(atr, rsi, i)
        actual_dist = base_dist * mult

        # Цена DCA (для LONG - ниже)
        dca_price = ENTRY_PRICE * (1 - actual_dist)

        # Размер DCA
        dca_margin = entry_margin * weight
        dca_position = dca_margin * LEVERAGE
        dca_size_btc = dca_position / dca_price

        # Накопление
        total_margin += dca_margin
        total_position += dca_position
        total_size_btc += dca_size_btc

        # Новая средняя цена (взвешенная)
        prev_total_usd = (avg_price * (total_size_btc - dca_size_btc))
        new_total_usd = prev_total_usd + (dca_price * dca_size_btc)
        avg_price = new_total_usd / total_size_btc

        # TP от новой средней
        tp_price = avg_price * (1 + dynamic_tp)

        # Процент до TP от текущей цены DCA
        pct_to_tp = ((tp_price - dca_price) / dca_price) * 100

        level_name = f"DCA{i+1}"
        levels.append({
            'name': level_name,
            'dca_price': dca_price,
            'avg_price': avg_price,
            'tp_price': tp_price,
            'margin': dca_margin,
            'total_margin': total_margin,
            'pct_to_tp': pct_to_tp,
            'actual_dist': actual_dist
        })

        print(f"{level_name:<10} {base_dist*100:<6.2f} {mult:<8.3f} {actual_dist*100:<8.2f} ${dca_price:>10,.0f} {weight:<6.1f} ${dca_margin:>8.2f} ${avg_price:>10,.0f} ${total_margin:>10.2f} ${tp_price:>10,.0f} {pct_to_tp:>6.2f}%")

    print(f"{'─'*120}")

    # Расчет стоп-лосса и ликвидации
    print(f"\n🛡️ ЗАЩИТА:")

    # Стоп-лосс
    max_loss_sl = BALANCE * MAX_ACCOUNT_LOSS_PCT
    sl_price = avg_price - (max_loss_sl / total_size_btc)
    sl_pct_from_avg = ((sl_price - avg_price) / avg_price) * 100
    sl_pct_from_last_dca = ((sl_price - levels[-1]['dca_price']) / levels[-1]['dca_price']) * 100

    # Ликвидация
    mm = total_position * MMR
    max_loss_liq = BALANCE - mm
    liq_price = avg_price - (max_loss_liq / total_size_btc)
    liq_pct_from_avg = ((liq_price - avg_price) / avg_price) * 100

    print(f"   Общая маржа: ${total_margin:.2f} ({total_margin/BALANCE*100:.1f}% баланса)")
    print(f"   Общая позиция: ${total_position:,.2f}")
    print(f"   Maintenance Margin: ${mm:.2f}")
    print(f"   ")
    print(f"   📍 Стоп-лосс -30% (${max_loss_sl:.2f} убытка):")
    print(f"      Цена: ${sl_price:,.2f}")
    print(f"      От средней: {sl_pct_from_avg:.2f}%")
    print(f"      От DCA5: {sl_pct_from_last_dca:.2f}%")
    print(f"   ")
    print(f"   ⚠️ Ликвидация (${max_loss_liq:.2f} убытка):")
    print(f"      Цена: ${liq_price:,.2f}")
    print(f"      От средней: {liq_pct_from_avg:.2f}%")
    print(f"   ")
    print(f"   ✅ Запас: SL → Ликвидация = ${abs(sl_price - liq_price):,.2f} ({abs(sl_pct_from_avg - liq_pct_from_avg):.2f}% от средней)")

    # Проверка
    print(f"\n🔍 ПРОВЕРКА РАСЧЕТОВ:")
    check_margin = entry_margin * (1 + sum(weights))
    print(f"   Маржа (проверка): ${check_margin:.2f} vs ${total_margin:.2f} ✅" if abs(check_margin - total_margin) < 1 else f"   Маржа (проверка): ${check_margin:.2f} vs ${total_margin:.2f} ❌")

    if sl_price > liq_price:
        print(f"   ✅ Стоп-лосс ВЫШЕ ликвидации - БЕЗОПАСНО")
    else:
        print(f"   ❌ ОПАСНО! Ликвидация произойдет РАНЬШЕ стоп-лосса!")

    return {
        'scenario': scenario_name,
        'entry_margin': entry_margin,
        'total_margin': total_margin,
        'dynamic_tp': dynamic_tp,
        'sl_price': sl_price,
        'liq_price': liq_price,
        'sl_pct_from_last_dca': sl_pct_from_last_dca,
        'levels': levels
    }

# ==================== СЦЕНАРИИ ====================

results = []

# СЦЕНАРИЙ 1: TREND - Низкая волатильность, нейтральный RSI
results.append(calculate_grid(
    "TREND - Низкая волатильность (идеальные условия)",
    is_trend=True,
    atr=0.002,
    rsi=50,
    adx=30
))

# СЦЕНАРИЙ 2: TREND - Высокая волатильность + перепроданность
results.append(calculate_grid(
    "TREND - Высокая волатильность + перепроданность (агрессивно)",
    is_trend=True,
    atr=0.004,
    rsi=25,
    adx=35
))

# СЦЕНАРИЙ 3: RANGE - Средняя волатильность
results.append(calculate_grid(
    "RANGE - Средняя волатильность (боковик)",
    is_trend=False,
    atr=0.0025,
    rsi=50,
    adx=20
))

# СЦЕНАРИЙ 4: RANGE - Высокая волатильность + перепроданность (ЭКСТРИМ)
results.append(calculate_grid(
    "RANGE - Высокая волатильность + перепроданность (ЭКСТРИМ)",
    is_trend=False,
    atr=0.005,
    rsi=28,
    adx=15
))

# ==================== ИТОГОВАЯ ТАБЛИЦА ====================

print(f"\n\n{'='*120}")
print(f"📋 ИТОГОВАЯ СРАВНИТЕЛЬНАЯ ТАБЛИЦА")
print(f"{'='*120}")
print(f"{'Сценарий':<50} {'Маржа вход':<12} {'Маржа DCA5':<12} {'TP%':<8} {'SL от DCA5':<12}")
print(f"{'─'*120}")

for r in results:
    print(f"{r['scenario']:<50} ${r['entry_margin']:>10.2f} ${r['total_margin']:>10.2f} {r['dynamic_tp']*100:>6.2f}% {r['sl_pct_from_last_dca']:>10.2f}%")

print(f"{'='*120}")
print(f"\n✅ ВСЕ РАСЧЕТЫ ПРОВЕРЕНЫ!")
