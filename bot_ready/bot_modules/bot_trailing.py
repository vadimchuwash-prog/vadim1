"""
🆕 v1.4.2: BotTrailingMixin - Модуль управления трейлинг-стопами
Содержит логику для TREND TRAILING и RANGE TRAILING режимов

🆕 v1.4.9: АДАПТИВНАЯ АКТИВАЦИЯ:
- TREND: активация при 70% пути к динамическому TP
- RANGE: активация при 50% пути к динамическому TP
- Закрытие по лимитному ордеру с перевыставлением каждые 5 секунд
- Трейлинг срабатывает ТОЛЬКО когда позиция в прибыли
"""

import time
from config import (
    TRAILING_ENABLED,
    TREND_TRAILING_ACTIVATION_RATIO,
    TREND_TRAILING_CALLBACK_RATIOS,
    TREND_TRAILING_ACTIVATION_VOL_ADJUST,
    RANGE_TRAILING_THRESHOLDS,
    RANGE_TRAILING_TP_UPDATE_THRESHOLD,
    RANGE_TRAILING_ACTIVATION_RATIO,
    TRAILING_CLOSE_USE_LIMIT,
    TRAILING_LIMIT_ORDER_TIMEOUT,
    TRAILING_LIMIT_MAX_RETRIES,
    Col
)


class BotTrailingMixin:
    """
    Миксин для управления трейлинг-стопами в боте.

    Поддерживает два режима:
    1. TREND TRAILING - Гибридный адаптивный трейлинг для трендовых движений
    2. RANGE TRAILING - Многоуровневая защита для флетового режима

    🆕 v1.4.8: Отложенная активация и лимитное закрытие
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
                self._close_trailing_position(f"Trend Trailing ({pnl_pct*100:+.2f}%)")
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

    def check_and_activate_range_trailing(self):
        """
        🆕 v1.4.9: АДАПТИВНАЯ активация Range Trailing
        Активируется при достижении RANGE_TRAILING_ACTIVATION_RATIO (50%) от динамического TP
        Пример: если TP = 0.35%, активация при 0.35% × 50% = +0.175%
        """
        if not self.in_position or not self.range_market_type:
            return

        # Если уже активирован - ничего не делаем
        if self.range_trailing_enabled:
            return

        if self.avg_price == 0:
            return

        current_price = self.last_price
        side_mult = 1 if self.position_side == "Buy" else -1
        pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult

        # 🆕 v1.4.9: Получаем динамический TP и рассчитываем порог активации
        tp_distance = self.get_dynamic_tp_steps()
        activation_threshold = tp_distance * RANGE_TRAILING_ACTIVATION_RATIO

        # Активируем при достижении % от TP
        if pnl_pct >= activation_threshold:
            self.range_trailing_enabled = True
            self.range_peak_price = current_price

            # Показываем многоуровневую защиту
            thresholds_str = " → ".join([f"{t[1]*100:.2f}%" for t in RANGE_TRAILING_THRESHOLDS])
            self.log(f"🎯 Range Trailing ACTIVATED @ ${current_price:.2f}", Col.CYAN)
            self.log(f"   PnL: {pnl_pct*100:+.2f}% >= {activation_threshold*100:.2f}% (TP={tp_distance*100:.2f}% × {RANGE_TRAILING_ACTIVATION_RATIO*100:.0f}%)", Col.GRAY)
            self.log(f"   Многоуровневые пороги: {thresholds_str}", Col.GRAY)

    def check_range_trailing(self):
        """
        🆕 v1.4.2: Range Trailing режим - Многоуровневая защита
        Для режима Range: закрывает позицию при откате от пика
        Порог отката зависит от уровня прибыли (0.05%-0.10%)
        TP продолжает двигаться вверх по мере роста цены

        🆕 v1.4.8: КРИТИЧЕСКИЕ ФИКСЫ:
        - Активация только при достижении RANGE_TRAILING_ACTIVATION_PROFIT
        - Трейлинг срабатывает ТОЛЬКО в прибыли
        - Закрытие лимитным ордером с перевыставлением
        """
        # 🆕 v1.4.8: Сначала проверяем активацию
        self.check_and_activate_range_trailing()

        if not self.range_trailing_enabled or not self.in_position:
            return False

        # 🆕 v1.4.6: БАГ #8, #9, #10 - Защита от деления на ноль
        if self.avg_price == 0 or self.range_peak_price == 0:
            return False

        current_price = self.last_price
        side_mult = 1 if self.position_side == "Buy" else -1

        # 🆕 v1.4.8: Рассчитываем текущий PnL
        pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult

        # Получаем текущий динамический порог
        current_callback_threshold = self.get_range_trailing_callback()

        # Обновляем пик цены ТОЛЬКО если позиция в плюсе
        if self.position_side == "Buy":
            if current_price > self.range_peak_price and pnl_pct > 0:
                old_peak = self.range_peak_price
                self.range_peak_price = current_price
                self.log(f"📈 Range Peak Updated: ${old_peak:.2f} → ${current_price:.2f} (PnL: {pnl_pct*100:+.2f}%, порог: {current_callback_threshold*100:.2f}%)", Col.CYAN)

                # Обновляем TP вверх (если изменение значительное)
                self._update_tp_for_range_trailing()

            # Проверяем откат от пика
            callback = (self.range_peak_price - current_price) / self.range_peak_price

        else:  # SHORT
            if (current_price < self.range_peak_price or self.range_peak_price == 0) and pnl_pct > 0:
                old_peak = self.range_peak_price
                self.range_peak_price = current_price
                self.log(f"📉 Range Peak Updated: ${old_peak:.2f} → ${current_price:.2f} (PnL: {pnl_pct*100:+.2f}%, порог: {current_callback_threshold*100:.2f}%)", Col.CYAN)

                # Обновляем TP вниз (если изменение значительное)
                self._update_tp_for_range_trailing()

            # Проверяем откат от пика
            callback = (current_price - self.range_peak_price) / self.range_peak_price

        # 🆕 v1.4.8: КРИТИЧЕСКИЙ ФИКС - Закрываем ТОЛЬКО если позиция в прибыли!
        # Трейлинг защищает ПРИБЫЛЬ, а не фиксирует убытки
        if callback >= current_callback_threshold and pnl_pct > 0:
            self.log(f"🔔 RANGE TRAILING STOP! Откат: {callback*100:.3f}% (порог: {current_callback_threshold*100:.2f}%)", Col.MAGENTA)
            self._close_trailing_position(f"Range Trailing ({pnl_pct*100:+.2f}%)")
            return True

        return False

    def _close_trailing_position(self, reason):
        """
        🆕 v1.4.8: Закрытие позиции по трейлингу
        Использует лимитный ордер с перевыставлением или рыночный (по настройке)
        """
        if TRAILING_CLOSE_USE_LIMIT:
            self._close_position_limit_trailing(reason)
        else:
            self.close_position_market(reason)

    def _close_position_limit_trailing(self, reason):
        """
        🆕 v1.4.8: Закрытие позиции ЛИМИТНЫМ ордером с перевыставлением

        Алгоритм:
        1. Выставляем лимитный ордер по текущей цене (чуть лучше для быстрого исполнения)
        2. Ждём TRAILING_LIMIT_ORDER_TIMEOUT секунд
        3. Если не исполнился - отменяем и перевыставляем по новой цене
        4. Максимум TRAILING_LIMIT_MAX_RETRIES попыток, потом market
        """
        if not self.in_position or self.total_size_coins == 0:
            return

        self.log(f"📋 Closing by LIMIT order: {reason}", Col.CYAN)

        # Отменяем все ордера (TP, DCA, SL)
        self.cancel_all_orders()

        real_amount = self.total_size_coins
        side_to_close = "sell" if self.position_side == "Buy" else "buy"
        amount = float(self.exchange.amount_to_precision(self.symbol, real_amount))

        for attempt in range(1, TRAILING_LIMIT_MAX_RETRIES + 1):
            try:
                # Получаем актуальную цену
                current_price = self.last_price

                # Для быстрого исполнения ставим цену чуть лучше рыночной
                # Sell - чуть ниже, Buy - чуть выше
                price_offset = current_price * 0.0001  # 0.01%
                if side_to_close == "sell":
                    limit_price = current_price - price_offset
                else:
                    limit_price = current_price + price_offset

                limit_price = float(self.exchange.price_to_precision(self.symbol, limit_price))

                self.log(f"   Попытка {attempt}/{TRAILING_LIMIT_MAX_RETRIES}: Limit {side_to_close} @ ${limit_price:.2f}", Col.GRAY)

                params = {'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
                order = self.exchange.create_order(
                    symbol=self.symbol,
                    type='limit',
                    side=side_to_close,
                    amount=amount,
                    price=limit_price,
                    params=params
                )

                order_id = order['id']

                # Ждём исполнения
                for _ in range(TRAILING_LIMIT_ORDER_TIMEOUT):
                    time.sleep(1)
                    try:
                        filled_order = self.exchange.fetch_order(order_id, self.symbol)
                        status = filled_order.get('status', '')

                        if status == 'closed':
                            # Ордер исполнен!
                            exec_price = float(filled_order.get('average') or filled_order.get('price') or limit_price)
                            self.log(f"✅ Limit order FILLED @ ${exec_price:.2f}", Col.GREEN)
                            self._finalize_trailing_close(reason, exec_price, real_amount)
                            return
                        elif status == 'canceled':
                            self.log(f"⚠️ Limit order was canceled externally", Col.YELLOW)
                            break
                    except Exception as e:
                        self.log(f"⚠️ Error checking order: {e}", Col.YELLOW)

                # Не исполнился за таймаут - отменяем
                try:
                    self.exchange.cancel_order(order_id, self.symbol)
                    self.log(f"🔄 Limit order canceled, retrying...", Col.YELLOW)
                except:
                    pass

            except Exception as e:
                self.log(f"❌ Limit order failed: {e}", Col.RED)

        # Все попытки исчерпаны - закрываем по рынку
        self.log(f"⚠️ Falling back to MARKET order after {TRAILING_LIMIT_MAX_RETRIES} attempts", Col.YELLOW)
        self.close_position_market(reason)

    def _finalize_trailing_close(self, reason, exec_price, amount):
        """
        🆕 v1.4.8: Завершение закрытия позиции по трейлингу (после лимитного ордера)
        """
        from config import TAKER_FEE

        # Расчет PnL
        side_mult = 1 if self.position_side == "Buy" else -1
        gross_pnl = (exec_price - self.avg_price) * amount * side_mult

        # Комиссия за закрытие
        exit_fee = amount * exec_price * TAKER_FEE
        self.current_trade_fees += exit_fee
        net_pnl = gross_pnl - self.current_trade_fees

        # Обновляем баланс
        self.current_balance += net_pnl
        self.session_pnl += net_pnl

        # Обновляем статистику
        if net_pnl > 0:
            self.session_wins += 1
        else:
            self.session_losses += 1

        # Логируем
        pnl_sign = "+" if net_pnl >= 0 else ""
        self.log(f"🏁 CLOSED: {reason} | PnL: ${pnl_sign}{net_pnl:.2f} (fees: ${self.current_trade_fees:.2f})", Col.MAGENTA)

        # Сбрасываем состояние позиции
        old_side = self.position_side
        self.in_position = False
        self.position_side = None
        self.total_size_coins = 0
        self.avg_price = 0.0
        self.dca_count = 0
        self.reset_trailing()
        self.reset_dca_protection()
        self.current_trade_fees = 0.0

        # Запись в CSV и blackbox
        try:
            self._log_trade_to_csv(old_side, exec_price, net_pnl, reason)
        except:
            pass

        try:
            self.blackbox_log_event('exit', {
                'reason': reason,
                'exit_price': exec_price,
                'pnl': net_pnl,
                'fees': self.current_trade_fees
            })
        except:
            pass

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
        self.range_market_type = False  # 🆕 v1.4.8
