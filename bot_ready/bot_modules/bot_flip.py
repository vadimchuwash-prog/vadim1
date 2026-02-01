"""
v1.5.1: SMART FLIP MODULE
Разворот позиции при подтверждённом движении против

Логика:
1. SL закрывает убыточную позицию
2. Проверяем: ADX > порога? Тренд подтверждён?
3. Если да → открываем позицию в ОБРАТНОМ направлении (1.5x размер)
4. Flip-позиция получает расширенный TP (едем по тренду)
5. DCA работает и для flip позиций

v1.5.1 улучшения:
- Размер flip 1.5x (чтобы отбить убыток от SL)
- TP для flip шире на 50% (FLIP_TP_MULTIPLIER)
- Полная поддержка DCA в flip-позициях
"""

import time
from datetime import datetime, timedelta
from config import (
    FLIP_ENABLED,
    FLIP_ADX_THRESHOLD,
    FLIP_COOLDOWN,
    FLIP_SIZE_RATIO,
    FLIP_MAX_PER_SESSION,
    FLIP_TP_MULTIPLIER,
    LEVERAGE,
    SAFETY_ORDERS_COUNT,
    Col
)


class BotFlipMixin:
    """
    Миксин для Smart Flip - разворота позиции при движении против.
    """

    def check_and_execute_flip(self, original_side, sl_price):
        """
        v1.5.0: Проверить условия и выполнить flip после SL.

        Args:
            original_side: "Buy" или "Sell" - сторона закрытой позиции
            sl_price: Цена закрытия по SL

        Returns:
            bool: True если flip выполнен
        """
        if not FLIP_ENABLED:
            return False

        # Проверка лимита flip за сессию
        if self.flip_count >= FLIP_MAX_PER_SESSION:
            self.log(f"  Flip skipped: max {FLIP_MAX_PER_SESSION} flips reached", Col.GRAY)
            return False

        # Проверка кулдауна
        if self.last_flip_time:
            elapsed = (datetime.now() - self.last_flip_time).total_seconds()
            if elapsed < FLIP_COOLDOWN:
                self.log(f"  Flip skipped: cooldown {FLIP_COOLDOWN - elapsed:.0f}s remaining", Col.GRAY)
                return False

        # Проверка ADX (подтверждение тренда)
        try:
            if self.current_market_df is None or len(self.current_market_df) < 2:
                self.log("  Flip skipped: no market data", Col.GRAY)
                return False

            row = self.current_market_df.iloc[-2]
            adx = float(row.get('ADX', 0))

            if adx < FLIP_ADX_THRESHOLD:
                self.log(f"  Flip skipped: ADX {adx:.1f} < {FLIP_ADX_THRESHOLD} (weak trend)", Col.GRAY)
                return False

        except Exception as e:
            self.log(f"  Flip skipped: ADX check error: {e}", Col.YELLOW)
            return False

        # Определяем направление flip
        flip_side = "Sell" if original_side == "Buy" else "Buy"
        self.log(f"🔄 SMART FLIP: {original_side} → {flip_side} (ADX: {adx:.1f})", Col.MAGENTA)

        # Открываем позицию в обратном направлении
        try:
            return self._execute_flip_entry(flip_side, sl_price, adx)
        except Exception as e:
            self.log(f"  Flip entry failed: {e}", Col.RED)
            return False

    def _execute_flip_entry(self, flip_side, price, adx):
        """
        Открыть flip-позицию.

        Args:
            flip_side: "Buy" или "Sell"
            price: Текущая цена
            adx: Значение ADX

        Returns:
            bool: True если позиция открыта
        """
        # Размер flip = базовый размер × FLIP_SIZE_RATIO
        effective_bal = self.get_effective_balance()
        flip_usd = effective_bal * 0.02 * FLIP_SIZE_RATIO  # ~2% от effective balance
        flip_usd = max(flip_usd, 6.0)  # Минимум $6

        current_price = self.last_price or price
        flip_coins = (flip_usd * LEVERAGE) / current_price
        flip_coins = float(self.exchange.amount_to_precision(self.symbol, flip_coins))

        if flip_coins <= 0:
            self.log("  Flip: amount too small", Col.YELLOW)
            return False

        self.log(f"  Flip entry: {flip_side} {flip_coins} BTC @ ~${current_price:.2f} (${flip_usd:.2f})", Col.CYAN)

        order = self.exchange.create_order(
            symbol=self.symbol,
            type='market',
            side=flip_side.lower(),
            amount=flip_coins,
            params={'positionSide': 'LONG' if flip_side == 'Buy' else 'SHORT'}
        )

        # Получаем цену исполнения
        time.sleep(2)
        filled_order = self.exchange.fetch_order(order['id'], self.symbol)
        fill_price = float(filled_order.get('average') or filled_order.get('price') or current_price)

        # Обновляем состояние
        self.in_position = True
        self.position_side = flip_side
        self.avg_price = fill_price
        self.base_entry_price = fill_price
        self.total_size_coins = flip_coins
        self.first_entry_price = fill_price
        self.entry_usd_vol = flip_usd
        self.safety_count = 0
        self.current_trade_fees = float(filled_order.get('fee', {}).get('cost', 0)) or (flip_coins * fill_price * 0.0005)

        # Flip state
        self.flip_count += 1
        self.last_flip_time = datetime.now()
        self.is_flip_position = True

        # Ставим TP, DCA, SL (flip получает полный набор ордеров)
        self.place_limit_tp()
        if self.safety_count < SAFETY_ORDERS_COUNT:
            self.place_limit_dca()
        self.place_stop_loss()

        # Range/Trend setup
        if not self.is_trending_market:
            self.range_market_type = True
            self.range_trailing_enabled = False
            self.range_peak_price = 0.0
            self.last_tp_update_price = fill_price
        else:
            self.range_market_type = False

        self.log(f"  FLIP OPENED: {flip_side} @ ${fill_price:.2f} | ADX: {adx:.1f}", Col.GREEN)
        self.log(f"  Flip #{self.flip_count}/{FLIP_MAX_PER_SESSION} this session", Col.GRAY)

        # Telegram
        self.tg.send(
            f"🔄 <b>SMART FLIP</b>\n"
            f"{'🟢' if flip_side == 'Buy' else '🔴'} {flip_side} @ ${fill_price:.2f}\n"
            f"📊 ADX: {adx:.1f}\n"
            f"💰 Size: ${flip_usd:.2f} ({flip_coins} BTC)"
        )

        self.update_dashboard(force=True)
        return True
