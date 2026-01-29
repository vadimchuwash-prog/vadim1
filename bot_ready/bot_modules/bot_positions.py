"""
🎯 BOT POSITIONS MODULE
Управление позициями торгового бота

КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.5:
- 🔥 БАГ #4: Добавлен метод reset_position() (он вызывался но НЕ СУЩЕСТВОВАЛ!)
- 🔥 БАГ #5: Убрали reduceOnly для BingX Hedge режима
- 🔥 БАГ #8: Защита от бесконечного цикла при ошибках закрытия позиции
  * Счетчик попыток закрытия (max 3)
  * Автоматическое отключение трейлинга при превышении лимита
  * TP ордер продолжает работать
  * Уведомления в Telegram о критических ошибках

v1.4.2:
- 🔧 Range Trailing для позиций в боковике
- 🔧 Правильное определение position_side из API (для BingX)
- 🔧 Детальное логирование синхронизации позиций

v1.4.1:
- Детальное логирование операций с позициями
"""

import time
from datetime import datetime, timedelta
from config import *


class BotPositionsMixin:
    """
    Миксин для управления позициями торгового бота.
    
    Предоставляет методы для:
    - Открытия позиций (limit ордера)
    - Закрытия позиций (market ордера)
    - Сброса состояния позиции
    - Синхронизации с биржей
    - Ожидания исполнения ордеров
    
    КРИТИЧЕСКИ ВАЖНО:
    - Все методы работают с self.in_position, self.position_side и другими атрибутами
    - Предполагается наличие методов: log(), exchange, tg, и других из основного класса
    - Содержит критические исправления v1.4.5 против зависаний и бесконечных циклов
    """

    def reset_position(self):
        """
        🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #4: Сброс состояния после закрытия позиции
        
        Этот метод вызывался в коде, но НЕ СУЩЕСТВОВАЛ до версии v1.4.5!
        Это приводило к тому, что состояние бота не очищалось после закрытия позиции.
        
        Сбрасывает:
        - Флаги позиции (in_position, position_side)
        - Цены (avg_price, first_entry_price, base_entry_price)
        - Размеры (total_size_coins, entry_usd_vol)
        - Счетчики (safety_count)
        - Защиту DCA (drawdown, multipliers, history)
        - Трейлинг (trailing_active, peak_price)
        - Ордера (tp_order_id, sl_order_id, dca_order_id)
        """
        self.in_position = False
        self.position_side = None
        self.avg_price = 0.0
        self.total_size_coins = 0.0
        self.safety_count = 0
        self.entry_usd_vol = 0.0
        self.base_entry_price = 0.0
        self.first_entry_price = 0.0
        self.current_trade_fees = 0.0
        self.current_confluence = 0
        self.current_stage = 0

        # Сброс защиты DCA
        self.max_drawdown_from_entry = 0.0
        self.max_weighted_drawdown = 0.0
        self.protection_multiplier = 1.0
        self.last_danger_increase_time = None
        self.peak_volatility_during_drawdown = 0.0
        self.lowest_price_since_entry = 0.0
        self.highest_price_since_entry = 0.0
        self.price_history = []
        self.atr_history = []

        # Сброс trailing
        self.reset_trailing()

        # Сброс ордеров
        self.tp_order_id = None
        self.sl_order_id = None
        self.dca_order_id = None

        self.log("✅ Position state reset", Col.GREEN)

    def wait_for_order_fill(self, order_id, timeout=30):
        """
        Ожидание исполнения ордера с таймаутом.
        
        Args:
            order_id: ID ордера на бирже
            timeout: Таймаут ожидания в секундах (по умолчанию 30)
            
        Returns:
            tuple: (success: bool, fill_price: float)
                - success: True если ордер исполнен, False если отменен/отклонен/истек
                - fill_price: Средняя цена исполнения (0 если не исполнен)
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                order = self.exchange.fetch_order(order_id, self.symbol)
                if order['status'] == 'closed':
                    fill_price = float(order.get('average') or order.get('price') or 0)
                    return True, fill_price
                elif order['status'] in ['canceled', 'rejected', 'expired']:
                    return False, 0
                time.sleep(2)
            except: 
                pass
        return False, 0

    def _sync_position_with_exchange(self):
        """
        Синхронизация позиции с биржей - ИСПРАВЛЕНО v1.4.2
        
        Критические исправления:
        - Используем positionSide из API (для BingX)
        - BingX возвращает ПОЛОЖИТЕЛЬНОЕ amount даже для SHORT
        - Восстанавливаем base_entry_price, entry_usd_vol
        - Примерно определяем safety_count из размера позиции
        - Сбрасываем защиту DCA если позиция отсутствует
        
        Детальное логирование для диагностики.
        """
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            found = False

            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))

                if amt != 0:
                    self.in_position = True

                    # 🔧 ИСПРАВЛЕНИЕ: Используем positionSide из API (для BingX)
                    # BingX возвращает ПОЛОЖИТЕЛЬНОЕ amount даже для SHORT!
                    position_side_from_api = pos.get('side') or pos['info'].get('positionSide', '')

                    # 🆕 v1.4.2: Детальное логирование для диагностики
                    self.log(f"🔍 Sync Debug: amt={amt}, api_side={position_side_from_api}", Col.GRAY)

                    if position_side_from_api in ['LONG', 'long', 'Long']:
                        self.position_side = "Buy"
                    elif position_side_from_api in ['SHORT', 'short', 'Short']:
                        self.position_side = "Sell"
                    else:
                        # Фоллбэк на старый метод (для других бирж)
                        self.position_side = "Buy" if amt > 0 else "Sell"
                        self.log(f"⚠️ Sync: Unknown positionSide '{position_side_from_api}', using fallback", Col.YELLOW)

                    self.total_size_coins = abs(amt)
                    self.avg_price = float(pos.get('entryPrice', 0))
                    if self.avg_price == 0:
                        self.avg_price = float(pos['info'].get('entryPrice', 0))

                    # Восстанавливаем base_entry_price
                    if not self.base_entry_price or self.base_entry_price == 0:
                        self.base_entry_price = self.avg_price

                    # Восстанавливаем entry_usd_vol если нужно
                    if self.entry_usd_vol == 0:
                        real_lev = float(pos.get('leverage', LEVERAGE))
                        self.entry_usd_vol = (self.avg_price * self.total_size_coins) / real_lev

                    # Восстанавливаем safety_count (грубая оценка)
                    if self.safety_count == 0 and self.entry_usd_vol > 0:
                        position_usd = (self.avg_price * self.total_size_coins) / LEVERAGE
                        if position_usd > self.entry_usd_vol * 1.5:
                            # Примерно вычисляем уровень DCA
                            _, weights = self.get_dca_parameters()
                            cumulative = self.entry_usd_vol
                            for i, w in enumerate(weights):
                                cumulative += self.entry_usd_vol * w
                                # 🆕 v1.4.6: БАГ #17 - Защита от деления на ноль
                                if cumulative > 0 and abs(position_usd - cumulative) / cumulative < 0.15:
                                    self.safety_count = i + 1
                                    self.log(f"🔄 Restored DCA level: {self.safety_count}", Col.CYAN)
                                    break

                    found = True
                    self.log(f"🔄 Sync: {self.position_side} {self.total_size_coins:.4f} @ {self.avg_price:.2f}", Col.BLUE)
                    break
            
            if not found:
                self.in_position = False

                # 🆕 v1.4.3: Сброс защиты при отсутствии позиции
                self.max_drawdown_from_entry = 0.0
                self.max_weighted_drawdown = 0.0
                self.protection_multiplier = 1.0
                self.last_danger_increase_time = None
                self.peak_volatility_during_drawdown = 0.0
                self.lowest_price_since_entry = 0.0
                self.highest_price_since_entry = 0.0
                self.price_history = []
                self.atr_history = []

        except Exception as e:
            self.log(f"⚠️ Sync error: {e}", Col.YELLOW)

    def open_position_limit(self, signal_data, df):
        """
        🚀 Открытие позиции лимитным ордером
        
        Алгоритм:
        1. Проверка существующих позиций на бирже
        2. Расчет размера позиции на основе стадии и confluence
        3. Размещение limit ордера по bid/ask цене
        4. Ожидание исполнения ордера (30 сек)
        5. Обновление состояния бота и синхронизация
        6. Размещение TP, DCA, SL ордеров
        7. Активация Range Trailing для боковых рынков
        
        Args:
            signal_data: Словарь с сигналом {'signal': 'Buy'/'Sell', 'stage': 1-3, 'confluence': 0-7}
            df: DataFrame с рыночными данными
            
        КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.5:
        - Сброс счетчика попыток закрытия при новой позиции (предотвращение багов)
        - Активация многоуровневой Range Trailing защиты
        """
        try:
            # Проверка существующих позиций
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0)) != 0:
                    self.in_position = True
                    self._sync_position_with_exchange()
                    return
        except: 
            pass

        side = signal_data['signal']
        stage = signal_data['stage']
        confluence = signal_data['confluence']
        
        row = df.iloc[-2]
        
        stage_emoji = ["", "🟡", "🟠", "🔴"][stage]
        self.log(f"⏳ Opening {side} {stage_emoji} Stage{stage} (Confluence: {confluence}/7)", Col.YELLOW)
        self.log(f"   RSI={row['RSI']:.1f}, ATR={row['ATR_pct']:.4f}, ADX={row['ADX']:.1f}", Col.GRAY)

        try:
            self.refresh_wallet_status()
            
            vol_pct = self.calculate_smart_position_size_hybrid(df, stage)
            vol_usd = max(self.get_effective_balance() * vol_pct, MIN_EXCHANGE_ORDER_USD)
            
            ticker = self.exchange.fetch_ticker(self.symbol)
            limit_price = ticker['bid'] if side == 'Buy' else ticker['ask']
            
            raw_amount = (vol_usd * LEVERAGE) / limit_price
            size_coins = float(self.exchange.amount_to_precision(self.symbol, raw_amount))
            
            self.log(f"📝 Ordering: {size_coins} coins (~{vol_usd:.2f}$ = {vol_pct*100:.2f}%) @ {limit_price}", Col.GRAY)

            order = self.exchange.create_order(
                symbol=self.symbol, 
                type='limit', 
                side=side.lower(), 
                amount=size_coins, 
                price=limit_price, 
                params={'positionSide': 'LONG' if side == 'Buy' else 'SHORT'}
            )
            
            success, final_fill_price = self.wait_for_order_fill(order['id'])
            if not success:
                self.log("⚠️ Order timed out. Cancelling...", Col.YELLOW)
                try: 
                    self.exchange.cancel_order(order['id'], self.symbol)
                except: 
                    pass
                try: 
                    check = self.exchange.fetch_order(order['id'], self.symbol)
                    if check['status'] == 'closed':
                        final_fill_price = float(check['average'])
                        success = True
                    else: 
                        return
                except: 
                    return

            # Обновление состояния позиции
            self.in_position = True
            self.position_side = side
            self.avg_price = final_fill_price
            self.first_entry_price = final_fill_price
            self.base_entry_price = final_fill_price
            self.total_size_coins = size_coins
            self.entry_usd_vol = vol_usd
            self.safety_count = 0
            self.current_confluence = confluence
            self.current_stage = stage
            self.trade_start_time = datetime.now()
            self.trades_today += 1
            self.current_trade_fees = self.get_real_order_fee(order['id']) or ((size_coins * final_fill_price) * MAKER_FEE)
            
            self._sync_position_with_exchange()
            self.log(f"🟢 OPENED {stage_emoji}: {side} @ {final_fill_price:.4f} (Confluence: {confluence}/7)", Col.GREEN)
            
            # 🆕 v1.3: Blackbox логирование
            self.log_blackbox("ENTRY", {
                "side": side,
                "price": final_fill_price,
                "size": size_coins,
                "confluence": confluence,
                "stage": stage,
                "balance": self.balance,
                "entry_usd": vol_usd
            })
            
            self.send_or_update_trade_message(f"Open {stage_emoji} Stage{stage} 🚀")
            self.place_limit_tp()
            self.place_limit_dca()
            self.place_stop_loss()  # 🆕 Stop Loss
            self.reset_trailing()

            # 🆕 v1.4.5: Сброс счетчика попыток закрытия при новой позиции
            self.close_attempt_count = 0

            # 🆕 v1.4.9: Range Trailing - АДАПТИВНАЯ активация
            # Трейлинг активируется при достижении RANGE_TRAILING_ACTIVATION_RATIO от TP
            if not self.is_trending_market:
                self.range_market_type = True  # Флаг что это Range рынок
                self.range_trailing_enabled = False  # НЕ активируем сразу!
                self.range_peak_price = 0.0  # Пик будет установлен при активации
                self.last_tp_update_price = final_fill_price
                tp_dist = self.get_dynamic_tp_steps()
                activation_pct = tp_dist * RANGE_TRAILING_ACTIVATION_RATIO
                self.log(f"🎯 Range Market - Trailing activates at {RANGE_TRAILING_ACTIVATION_RATIO*100:.0f}% of TP (+{activation_pct*100:.2f}%)", Col.CYAN)
            else:
                self.range_market_type = False

            self.update_dashboard(force=True)

        except Exception as e:
            self.log(f"❌ Entry failed: {e}", Col.RED)
            try: 
                self.exchange.cancel_all_orders(self.symbol)
            except: 
                pass
            self._sync_position_with_exchange()

    def close_position_market(self, reason):
        """
        🏁 Закрытие позиции market ордером
        
        Алгоритм:
        1. Отмена всех активных ордеров (TP, DCA, SL)
        2. Размещение market ордера на закрытие
        3. Расчет PnL (gross и net с учетом комиссий)
        4. Обновление баланса и статистики сессии
        5. Запись в CSV лог
        6. Blackbox логирование
        7. Future Spy (мониторинг цены после выхода)
        8. Сброс защиты DCA и счетчиков
        
        Args:
            reason: Причина закрытия (строка для логов)
            
        КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.5:
        - 🔥 БАГ #8: Защита от бесконечного цикла при ошибках закрытия
          * Счетчик попыток (max_close_attempts = 3)
          * При превышении лимита - отключение трейлинга
          * TP ордер продолжает работать
          * Уведомления в Telegram о критических ошибках
        - 🔥 БАГ #5: Убрали reduceOnly для BingX Hedge режима
        """
        # Защита от вызова без позиции
        if not self.in_position or self.total_size_coins == 0 or self.position_side is None:
            self.log(f"⚠️ close_position_market called but no position open", Col.YELLOW)
            return

        try:
            self.cancel_all_orders()

            real_amount = self.total_size_coins
            price_guess = self.last_price

            side_to_close = "sell" if self.position_side == "Buy" else "buy"
            amount = float(self.exchange.amount_to_precision(self.symbol, real_amount))

            # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #5: Убрали reduceOnly для BingX Hedge режима!
            params = {'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='market',
                side=side_to_close,
                amount=amount,
                params=params
            )
            time.sleep(1) 
            
            exit_fee = self.get_real_order_fee(order['id']) or (real_amount * price_guess * TAKER_FEE)
            self.current_trade_fees += exit_fee
            
            try:
                filled_order = self.exchange.fetch_order(order['id'], self.symbol)
                exec_price = float(filled_order.get('average') or filled_order.get('price') or price_guess)
            except:
                exec_price = price_guess

            # Расчет PnL
            side_mult = 1 if self.position_side == "Buy" else -1
            gross_pnl = (exec_price - self.avg_price) * real_amount * side_mult
            net_pnl = gross_pnl - self.current_trade_fees
            
            self.balance += net_pnl
            self.in_position = False
            
            # Cooldown после проигрыша
            if net_pnl > 0:
                self.last_trade_time = datetime.now() - timedelta(hours=2) 
            else:
                self.last_trade_time = datetime.now()
            
            # Статистика
            self.session_total_pnl += net_pnl
            self.session_total_fees += self.current_trade_fees
            if net_pnl > 0: 
                self.session_wins += 1
            else: 
                self.session_losses += 1
            
            # CSV логирование
            try:
                with open(CSV_FILE, 'a', newline='') as f:
                    import csv
                    csv.writer(f).writerow([
                        datetime.now(), 
                        self.symbol, 
                        self.position_side, 
                        reason, 
                        net_pnl, 
                        self.current_trade_fees, 
                        self.avg_price, 
                        exec_price, 
                        self.safety_count, 
                        "MARKET", 
                        self.current_volatility, 
                        self.current_confluence
                    ])
            except: 
                pass

            self.log(f"🏁 CLOSED: {reason} | PnL: ${net_pnl:.2f}", Col.MAGENTA)
            
            # 🆕 v1.3: Blackbox логирование
            trade_duration = (datetime.now() - self.trade_start_time).total_seconds() if self.trade_start_time else 0
            self.log_blackbox("EXIT", {
                "reason": reason,
                "price": exec_price,
                "pnl": net_pnl,
                "pnl_pct": (net_pnl / self.entry_usd_vol * 100) if self.entry_usd_vol > 0 else 0,
                "fees": self.current_trade_fees,
                "duration_sec": trade_duration,
                "dca_count": self.safety_count
            })
            
            # 🆕 v1.3: Future Spy
            self.start_future_spy(exec_price, self.position_side, real_amount)
            
            self.send_or_update_trade_message(f"{reason} 🏁", pnl=net_pnl, exit_price=exec_price, is_final=True, calculated_fee_only=self.current_trade_fees)
            self.current_trade_fees = 0.0
            self.current_confluence = 0
            self.current_stage = 0

            # 🆕 v1.4.3: Сброс умной защиты DCA при закрытии позиции
            self.max_drawdown_from_entry = 0.0
            self.max_weighted_drawdown = 0.0
            self.protection_multiplier = 1.0
            self.last_danger_increase_time = None
            self.peak_volatility_during_drawdown = 0.0
            self.lowest_price_since_entry = 0.0
            self.highest_price_since_entry = 0.0
            self.price_history = []
            self.atr_history = []

            # Сброс trailing
            self.reset_trailing()

            # 🆕 v1.4.5: Сброс счетчика попыток после успешного закрытия
            self.close_attempt_count = 0

            if self.graceful_stop_mode:
                self.trading_active = False
                self.graceful_stop_mode = False
                self.tg.send("🛑 Stopped (Graceful)", self.get_keyboard())

            self.update_dashboard(force=True)

        except Exception as e:
            # 🆕 v1.4.5: КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ - Защита от бесконечного цикла
            self.close_attempt_count += 1
            self.log(f"❌ CRITICAL CLOSE ERROR (Попытка {self.close_attempt_count}/{self.max_close_attempts}): {e}", Col.RED)

            # Если превышен лимит попыток - ОСТАНАВЛИВАЕМ трейлинг, но НЕ останавливаем бота
            if self.close_attempt_count >= self.max_close_attempts:
                self.log(f"🚨 ЗАЩИТА АКТИВИРОВАНА: Превышен лимит попыток закрытия! Отключаю трейлинг для этой позиции.", Col.RED)
                self.log(f"⚠️ Позиция остается открытой. Трейлинг ОТКЛЮЧЕН. TP ордер продолжит работать.", Col.YELLOW)

                # Отключаем трейлинг, чтобы не спамить ошибками
                self.trailing_active = False
                self.range_trailing_enabled = False

                # Отправляем уведомление в Telegram
                try:
                    self.tg.send(f"🚨 КРИТИЧЕСКАЯ ОШИБКА\n\n"
                               f"Не удалось закрыть позицию после {self.max_close_attempts} попыток.\n"
                               f"Ошибка: {e}\n\n"
                               f"❌ Трейлинг отключен\n"
                               f"✅ TP ордер продолжит работать\n"
                               f"⚠️ Рекомендуется проверить позицию вручную")
                except: 
                    pass
