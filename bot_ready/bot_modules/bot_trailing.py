"""
🆕 v1.4.2: BotTrailingMixin - Модуль управления трейлинг-стопами
Содержит логику для TREND TRAILING и RANGE TRAILING режимов
"""

from config import (
    TRAILING_ENABLED,
    TREND_TRAILING_ACTIVATION_RATIO,
    TREND_TRAILING_CALLBACK_RATIOS,
    TREND_TRAILING_ACTIVATION_VOL_ADJUST,
    RANGE_TRAILING_THRESHOLDS,
    RANGE_TRAILING_TP_UPDATE_THRESHOLD,
    Col
)


class BotTrailingMixin:
    """
    Миксин для управления трейлинг-стопами в боте.
    
    Поддерживает два режима:
    1. TREND TRAILING - Гибридный адаптивный трейлинг для трендовых движений
    2. RANGE TRAILING - Многоуровневая защита для флетового режима
    """

    def check_trailing_stop(self):
        """
        🆕 v1.4.2: TREND Trailing - Гибридный адаптивный
        Активация: 50% пути к TP (с коррекцией на волатильность)
        Откат: 15-25% от расстояния до TP (зависит от волатильности)
        """
        if not TRAILING_ENABLED or not self.in_position:
            return False

        # 🆕 v1.4.6: БАГ #4 - Защита от деления на ноль
        if self.avg_price == 0:
            return False

        current_price = self.last_price
        side_mult = 1 if self.position_side == "Buy" else -1
        pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult

        # Получаем динамический TP
        tp_distance = self.get_dynamic_tp_steps()

        # Определяем режим волатильности
        vol = self.current_volatility
        if vol > 0.004:
            vol_mode = 'high_vol'
        elif vol > 0.0025:
            vol_mode = 'medium_vol'
        else:
            vol_mode = 'low_vol'

        # Рассчитываем порог активации (50% до TP с коррекцией на волатильность)
        base_activation = tp_distance * TREND_TRAILING_ACTIVATION_RATIO
        activation_threshold = base_activation * TREND_TRAILING_ACTIVATION_VOL_ADJUST[vol_mode]

        # Рассчитываем порог отката (% от расстояния до TP)
        callback_threshold = tp_distance * TREND_TRAILING_CALLBACK_RATIOS[vol_mode]

        if not self.trailing_active:
            if pnl_pct >= activation_threshold:
                self.trailing_active = True
                self.trailing_peak_price = current_price
                self.log(f"🎯 Trend Trailing ACTIVATED @ ${current_price:.2f} (PnL: {pnl_pct*100:.2f}%, порог: {activation_threshold*100:.2f}%, откат: {callback_threshold*100:.2f}%)", Col.CYAN)
                return False

        if self.trailing_active:
            # 🆕 v1.4.6: БАГ #5, #6 - Защита от деления на ноль
            if self.trailing_peak_price == 0:
                return False

            # Обновляем пик
            if self.position_side == "Buy":
                if current_price > self.trailing_peak_price:
                    old_peak = self.trailing_peak_price
                    self.trailing_peak_price = current_price
                    self.log(f"📈 Trend Peak Updated: ${old_peak:.2f} → ${current_price:.2f}", Col.CYAN)
                callback = (self.trailing_peak_price - current_price) / self.trailing_peak_price
            else:
                if current_price < self.trailing_peak_price:
                    old_peak = self.trailing_peak_price
                    self.trailing_peak_price = current_price
                    self.log(f"📉 Trend Peak Updated: ${old_peak:.2f} → ${current_price:.2f}", Col.CYAN)
                callback = (current_price - self.trailing_peak_price) / self.trailing_peak_price

            # Проверяем откат
            if callback >= callback_threshold:
                self.log(f"🔔 TREND TRAILING STOP! Откат: {callback*100:.3f}% (порог: {callback_threshold*100:.2f}%)", Col.MAGENTA)
                self.close_position_market(f"Trend Trailing ({pnl_pct*100:+.2f}%)")
                return True

        return False

    def get_range_trailing_callback(self):
        """
        🆕 v1.4.2: Определяет порог отката в зависимости от текущей прибыли
        ВАРИАНТ 3: Многоуровневая защита (агрессивный)
        """
        # 🆕 v1.4.6: БАГ #7 - Защита от деления на ноль
        if self.avg_price == 0:
            return RANGE_TRAILING_THRESHOLDS[0][1]  # Возвращаем самый мягкий порог

        side_mult = 1 if self.position_side == "Buy" else -1
        pnl_pct = (self.last_price - self.avg_price) / self.avg_price * side_mult

        # Проходим по порогам и находим подходящий
        for threshold_profit, callback in RANGE_TRAILING_THRESHOLDS:
            if pnl_pct < threshold_profit:
                return callback

        # Если вышли за все пороги, используем самый жёсткий
        return RANGE_TRAILING_THRESHOLDS[-1][1]

    def check_range_trailing(self):
        """
        🆕 v1.4.2: Range Trailing режим - Многоуровневая защита
        Для режима Range: закрывает позицию при откате от пика
        Порог отката зависит от уровня прибыли (0.05%-0.10%)
        TP продолжает двигаться вверх по мере роста цены
        """
        if not self.range_trailing_enabled or not self.in_position:
            return False

        # 🆕 v1.4.6: БАГ #8, #9, #10 - Защита от деления на ноль
        if self.avg_price == 0 or self.range_peak_price == 0:
            return False

        current_price = self.last_price
        side_mult = 1 if self.position_side == "Buy" else -1

        # Получаем текущий динамический порог
        current_callback_threshold = self.get_range_trailing_callback()

        # Обновляем пик цены
        if self.position_side == "Buy":
            if current_price > self.range_peak_price:
                old_peak = self.range_peak_price
                self.range_peak_price = current_price
                pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult
                self.log(f"📈 Range Peak Updated: ${old_peak:.2f} → ${current_price:.2f} (PnL: {pnl_pct*100:+.2f}%, порог: {current_callback_threshold*100:.2f}%)", Col.CYAN)

                # Обновляем TP вверх (если изменение значительное)
                self._update_tp_for_range_trailing()

            # Проверяем откат от пика
            callback = (self.range_peak_price - current_price) / self.range_peak_price

        else:  # SHORT
            if current_price < self.range_peak_price or self.range_peak_price == 0:
                old_peak = self.range_peak_price
                self.range_peak_price = current_price
                pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult
                self.log(f"📉 Range Peak Updated: ${old_peak:.2f} → ${current_price:.2f} (PnL: {pnl_pct*100:+.2f}%, порог: {current_callback_threshold*100:.2f}%)", Col.CYAN)

                # Обновляем TP вниз (если изменение значительное)
                self._update_tp_for_range_trailing()

            # Проверяем откат от пика
            callback = (current_price - self.range_peak_price) / self.range_peak_price

        # Если откат больше ДИНАМИЧЕСКОГО порога - закрываем
        if callback >= current_callback_threshold:
            pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult
            self.log(f"🔔 RANGE TRAILING STOP! Откат: {callback*100:.3f}% (порог: {current_callback_threshold*100:.2f}%)", Col.MAGENTA)
            self.close_position_market(f"Range Trailing ({pnl_pct*100:+.2f}%)")
            return True

        return False

    def _update_tp_for_range_trailing(self):
        """
        Обновляет TP для Range trailing режима
        Обновляет только при значительном изменении пика (>0.1%)
        """
        try:
            # 🆕 v1.4.6: БАГ #11 - Защита от деления на ноль
            # Проверяем, достаточно ли изменился пик для обновления TP
            if self.last_tp_update_price > 0:
                price_change = abs(self.range_peak_price - self.last_tp_update_price) / self.last_tp_update_price
                if price_change < RANGE_TRAILING_TP_UPDATE_THRESHOLD:
                    # Изменение незначительное, не обновляем TP
                    return

            # Отменяем старый TP
            if self.tp_order_id:
                try:
                    self.exchange.cancel_order(self.tp_order_id, self.symbol)
                    self.log(f"🔄 Cancelled old TP for Range Trailing update", Col.GRAY)
                except:
                    pass

            # Выставляем новый TP
            self.place_limit_tp()

            # Сохраняем цену последнего обновления
            self.last_tp_update_price = self.range_peak_price
            self.log(f"✅ TP updated for Range Trailing @ peak ${self.range_peak_price:.2f}", Col.GREEN)

        except Exception as e:
            self.log(f"⚠️ Failed to update TP for Range Trailing: {e}", Col.YELLOW)

    def reset_trailing(self):
        """Сброс trailing"""
        self.trailing_active = False
        self.trailing_peak_price = 0.0
        self.range_trailing_enabled = False
        self.range_peak_price = 0.0
        self.last_tp_update_price = 0.0
