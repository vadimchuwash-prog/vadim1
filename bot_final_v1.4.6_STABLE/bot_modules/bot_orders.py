"""
🛒 BOT ORDERS MODULE
Модуль управления ордерами: TP, DCA, Stop Loss

Извлечено из trading_bot.py для улучшения структуры кода
"""

import time
import traceback
from config import *


class BotOrdersMixin:
    """Mixin для управления ордерами бота"""
    
    def get_real_order_fee(self, order_id):
        """Получение реальной комиссии"""
        if not order_id: return 0.0
        total_fee = 0.0
        for _ in range(3):
            try:
                time.sleep(1.5)
                trades = self.exchange.fetch_my_trades(self.symbol, limit=10, params={'orderId': str(order_id)})
                for t in trades:
                    if str(t['order']) == str(order_id) and t['fee']: 
                        total_fee += float(t['fee']['cost'])
                if total_fee > 0: return total_fee
            except: pass
        return 0.0

    def cancel_all_orders(self):
        """Отмена всех ордеров"""
        try:
            if self.tp_order_id: self.exchange.cancel_order(self.tp_order_id, self.symbol)
            if self.dca_order_id: self.exchange.cancel_order(self.dca_order_id, self.symbol)
            if self.sl_order_id: self.exchange.cancel_order(self.sl_order_id, self.symbol)
        except: pass
        self.tp_order_id = None
        self.dca_order_id = None
        self.sl_order_id = None
        try: self.exchange.cancel_all_orders(self.symbol)
        except: pass

    def place_stop_loss(self):
        """🆕 Размещение Stop Loss ордера"""
        if not self.in_position or self.sl_order_id:
            return False
        
        try:
            side_mult = 1 if self.position_side == "Buy" else -1
            
            # SL на уровне MAX_ACCOUNT_LOSS_PCT
            sl_distance = MAX_ACCOUNT_LOSS_PCT
            sl_price = self.avg_price * (1 + (sl_distance * (-side_mult)))
            
            price = float(self.exchange.price_to_precision(self.symbol, sl_price))
            amount = float(self.exchange.amount_to_precision(self.symbol, self.total_size_coins))
            
            # Стоп-маркет ордер
            # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #5: Убрали reduceOnly для BingX Hedge режима!
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='stop_market',
                side="sell" if self.position_side == "Buy" else "buy",
                amount=amount,
                params={
                    'stopPrice': price,
                    'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'
                }
            )
            
            self.sl_order_id = order['id']
            self.log(f"🛡️ SL placed: ID={self.sl_order_id}, Price={price:.4f}", Col.RED)
            return True
            
        except Exception as e:
            self.log(f"❌ SL placement error: {e}", Col.RED)
            return False

    def place_limit_tp(self):
        """Размещение TP - ИСПРАВЛЕНО v1.4.1"""
        # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #10: Проверка позиции ПЕРЕД размещением TP!
        if not self.in_position:
            return False

        # 🆕 Синхронизация с биржей - проверяем что позиция РЕАЛЬНО существует!
        try:
            self._sync_position_with_exchange()
        except Exception as e:
            self.log(f"⚠️ TP: sync failed: {e}", Col.YELLOW)
            return False

        # 🆕 После синхронизации проверяем что позиция НЕ закрыта вручную
        if not self.in_position or self.total_size_coins == 0:
            self.log("🚨 Cannot place TP: position closed externally!", Col.RED)
            self.reset_position()
            return False

        # Отменяем старый TP если есть
        if self.tp_order_id:
            try:
                self.exchange.cancel_order(self.tp_order_id, self.symbol)
                self.log(f"🗑️ Cancelled old TP order {self.tp_order_id}", Col.GRAY)
            except Exception as e:
                self.log(f"⚠️ TP cancel error: {e}", Col.YELLOW)
            self.tp_order_id = None

        if self.total_size_coins <= 0:
            self.log("⚠️ TP: total_size_coins <= 0", Col.YELLOW)
            return False
        
        try:
            side_mult = 1 if self.position_side == "Buy" else -1
            
            # 🆕 v1.3: Используем динамический TP от ATR
            tp_distance = float(self.get_dynamic_tp_steps())
            
            price = float(self.exchange.price_to_precision(
                self.symbol, 
                self.avg_price * (1 + (tp_distance * side_mult))
            ))
            
            amount = float(self.exchange.amount_to_precision(self.symbol, self.total_size_coins))
            
            # 🆕 v1.4.1: Логирование параметров
            order_side = "sell" if self.position_side == "Buy" else "buy"
            self.log(f"📝 TP Params: side={order_side}, amount={amount}, price={price:.4f}, avg={self.avg_price:.4f}, dist={tp_distance*100:.2f}%", Col.GRAY)
            
            # 🆕 v1.4.1: Проверка минимального объёма
            if amount <= 0:
                self.log(f"❌ TP: amount rounded to 0 (total_size={self.total_size_coins})", Col.RED)
                return False
            
            order = self.exchange.create_order(
                symbol=self.symbol, 
                type='limit', 
                side=order_side,
                amount=amount, 
                price=price, 
                params={'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
            )
            self.tp_order_id = order['id']
            self.log(f"✅ TP placed: ID={self.tp_order_id}, Price={price:.4f}", Col.GREEN)
            return True
            
        except Exception as e:
            # 🆕 v1.4.1: Детальное логирование ошибки
            self.log(f"❌ TP placement FAILED: {e}", Col.RED)
            self.log(f"   avg_price={self.avg_price}, total_size={self.total_size_coins}, side={self.position_side}", Col.GRAY)
            self.log_debug(traceback.format_exc())
            return False

    def place_limit_dca(self):
        """Размещение DCA - УЛУЧШЕННАЯ ВЕРСИЯ v1.4.1"""
        # Защита от множественных вызовов
        if hasattr(self, '_dca_placing') and self._dca_placing:
            return False

        self._dca_placing = True

        # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #7: Проверка позиции ПЕРЕД размещением DCA!
        if not self.in_position:
            self._dca_placing = False
            return False

        # 🆕 Синхронизация с биржей - проверяем что позиция РЕАЛЬНО существует!
        try:
            self._sync_position_with_exchange()
        except Exception as e:
            self.log(f"⚠️ DCA: sync failed: {e}", Col.YELLOW)
            self._dca_placing = False
            return False

        # 🆕 После синхронизации проверяем что позиция НЕ закрыта вручную
        if not self.in_position or self.total_size_coins == 0:
            self.log("🚨 Cannot place DCA: position closed externally!", Col.RED)
            self.reset_position()
            self._dca_placing = False
            return False

        # 🆕 КРИТИЧНО! Проверяем свободную маржу на бирже
        try:
            balance_info = self.exchange.fetch_balance({'type': 'swap'})
            free_margin = float(balance_info['USDT']['free'])

            # Рассчитываем нужную маржу для следующей DCA
            dists, weights = self.get_dca_parameters()
            if self.safety_count >= len(weights):
                self._dca_placing = False
                return False

            weight = weights[self.safety_count]
            dca_vol_usd = self.entry_usd_vol * weight
            required_margin = dca_vol_usd * 1.2  # 20% буфер безопасности

            if free_margin < required_margin:
                self.log(f"🚨 Insufficient margin for DCA{self.safety_count+1}!", Col.RED)
                self.log(f"   Need: {required_margin:.2f}$ | Available: {free_margin:.2f}$", Col.YELLOW)
                self.log(f"⚠️ Position may be approaching liquidation!", Col.YELLOW)
                self._dca_placing = False
                return False
        except Exception as e:
            self.log(f"⚠️ Margin check failed: {e}", Col.YELLOW)

        try:
            if self.dca_order_id:
                try: 
                    self.exchange.cancel_order(self.dca_order_id, self.symbol)
                    self.log(f"🗑️ Cancelled old DCA {self.dca_order_id}", Col.GRAY)
                except: 
                    pass
                self.dca_order_id = None
            
            if self.safety_count >= SAFETY_ORDERS_COUNT:
                self._dca_placing = False
                return False

            # 🆕 v1.4.3: Обновляем умную защиту DCA
            self.update_protection_multiplier()

            dists, weights = self.get_dca_parameters()
            base_dist = dists[self.safety_count]

            dist_multiplier = self.get_smart_distance_multiplier(self.safety_count)

            # 🆕 v1.4.3: Применяем защитный множитель ПОВЕРХ всех остальных
            actual_dist = base_dist * dist_multiplier * self.protection_multiplier
            
            # 🔧 v1.3: ИСПРАВЛЕНО! DCA для SHORT теперь ВЫШЕ входа
            if self.position_side == "Buy":
                # LONG: DCA размещается НИЖЕ входа (при падении)
                dca_price = self.base_entry_price * (1 - actual_dist)
            else:
                # SHORT: DCA размещается ВЫШЕ входа (при росте)
                dca_price = self.base_entry_price * (1 + actual_dist)
            
            dca_price = float(self.exchange.price_to_precision(self.symbol, dca_price))
            
            weight = weights[self.safety_count]
            first_order_usd = self.entry_usd_vol
            dca_vol_usd = first_order_usd * weight
            dca_vol_usd = max(dca_vol_usd, MIN_EXCHANGE_ORDER_USD)
            
            dca_size_coins = (dca_vol_usd * LEVERAGE) / dca_price
            dca_size_coins = float(self.exchange.amount_to_precision(self.symbol, dca_size_coins))
            
            # 🆕 v1.4.1: Логирование параметров
            self.log(f"📝 DCA{self.safety_count+1} Params: side={self.position_side.lower()}, amount={dca_size_coins}, price={dca_price:.4f}, base={self.base_entry_price:.4f}, dist={actual_dist*100:.2f}%, weight={weight}x", Col.GRAY)
            
            # 🆕 v1.4.1: Проверка минимального объёма
            if dca_size_coins <= 0:
                self.log(f"❌ DCA: amount rounded to 0 (vol_usd={dca_vol_usd})", Col.RED)
                self._dca_placing = False
                return False
            
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='limit',
                side=self.position_side.lower(),
                amount=dca_size_coins,
                price=dca_price,
                params={'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
            )
            self.dca_order_id = order['id']
            
            self.log(f"✅ DCA{self.safety_count+1} placed: ID={self.dca_order_id}, Price={dca_price:.4f} (dist: {actual_dist*100:.2f}%, weight: {weight}x)", Col.CYAN)
            
            self._dca_placing = False
            return True
            
        except Exception as e:
            # 🆕 v1.4.1: Детальное логирование ошибки
            self.log(f"❌ DCA placement FAILED: {e}", Col.RED)
            self.log(f"   base_entry={self.base_entry_price}, safety_count={self.safety_count}, side={self.position_side}", Col.GRAY)
            self.log_debug(traceback.format_exc())
            self._dca_placing = False
            return False

    def execute_dca(self, fill_price, fill_amount, order_id):
        """Исполнение DCA (из ultrabtc7 - БЕЗ ИЗМЕНЕНИЙ!)"""
        try:
            self.safety_count += 1

            prev_total = self.total_size_coins
            self.total_size_coins += fill_amount
            # 🆕 v1.4.6: БАГ #19 - Защита от деления на ноль
            if self.total_size_coins > 0:
                self.avg_price = ((self.avg_price * prev_total) + (fill_price * fill_amount)) / self.total_size_coins
            else:
                self.avg_price = fill_price  # Fallback на цену заполнения

            # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #9: Обновляем base_entry_price после DCA!
            # Следующие DCA должны рассчитываться от НОВОЙ средней цены, а не от первоначальной!
            self.base_entry_price = self.avg_price

            dca_fee = self.get_real_order_fee(order_id) or ((fill_amount * fill_price) * MAKER_FEE)
            self.current_trade_fees += dca_fee

            self.dca_order_id = None
            
            self.log(f"🔨 DCA{self.safety_count} EXECUTED @ {fill_price:.4f}", Col.MAGENTA)
            
            # 🆕 v1.3: Blackbox логирование DCA
            self.log_blackbox("DCA_EXECUTED", {
                "level": self.safety_count,
                "price": fill_price,
                "size": fill_amount,
                "new_avg_price": self.avg_price,
                "total_size": self.total_size_coins,
                "fee": dca_fee
            })
            
            self.send_or_update_trade_message(f"DCA{self.safety_count} 🔨")
            
            self.place_limit_tp()
            
            if self.safety_count < SAFETY_ORDERS_COUNT:
                self.place_limit_dca()
            
            self.update_dashboard(force=True)
        except Exception as e:
            self.log(f"❌ DCA Execute Error: {e}", Col.RED)
