"""
🤖 HYBRID TRADING BOT v1.4.6 - MAIN CLASS
Главный класс бота с модульной архитектурой

КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.6:
- 🔥 Добавлен метод run() - главный торговый цикл (БЫЛ УТЕРЯН при модуляризации!)
- 🛡️ Защита от бесконечного цикла закрытия позиции
- 🔧 Все модули разбиты на логические компоненты
- ✅ Сохранен весь функционал из v1.4.5
"""

import time
import csv
from datetime import datetime, timezone

from bot_modules.bot_core import HybridTradingBot
from bot_modules.bot_indicators import BotIndicatorsMixin
from bot_modules.bot_positions import BotPositionsMixin
from bot_modules.bot_trailing import BotTrailingMixin
from bot_modules.bot_protection import BotProtectionMixin
from bot_modules.bot_orders import BotOrdersMixin
from bot_modules.bot_monitoring import BotMonitoringMixin
from bot_modules.analytics import AnalyticsMixin

from config import (
    TRAILING_ENABLED, TRAILING_UPDATE_INTERVAL,
    MAX_ACCOUNT_LOSS_PCT, SAFETY_ORDERS_COUNT,
    CSV_FILE, MAKER_FEE, Col
)


class HybridTradingBotModular(
    BotIndicatorsMixin,
    BotPositionsMixin,
    BotTrailingMixin,
    BotOrdersMixin,
    BotProtectionMixin,
    BotMonitoringMixin,
    AnalyticsMixin,
    HybridTradingBot
):
    """
    🤖 Модульный торговый бот v1.4.6

    Наследует миксины в порядке приоритета:
    1. BotIndicatorsMixin - индикаторы и анализ
    2. BotPositionsMixin - управление позициями
    3. BotTrailingMixin - трейлинг стопы
    4. BotOrdersMixin - управление ордерами
    5. BotProtectionMixin - умная защита DCA
    6. BotMonitoringMixin - мониторинг и телеграм
    7. AnalyticsMixin - аналитика (Black Box, PnL Audit, Future Spy)
    8. HybridTradingBot - базовый класс
    """

    def run(self):
        """
        🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Главный торговый цикл
        Этот метод был утерян при модуляризации в v1.4.5!
        Восстановлен из trading_bot_OLD_BACKUP.py с исправлениями.
        """
        last_doctor_check = 0
        last_pnl_log = 0

        while self.running:
            try:
                # 1. Обработка команд Telegram
                self.check_telegram_commands()

                # 2. Обновление дашборда
                if time.time() - self.last_dashboard_update > 15:
                    self.update_dashboard()

                # 3. Получение текущей цены
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.last_price = float(ticker['last'])
                except:
                    pass

                # 4. AI отчёт по расписанию (15:00 UTC)
                if self.has_ai:
                    now_utc = datetime.now(timezone.utc)
                    if now_utc.hour == 15 and now_utc.minute == 0 and not self.report_sent_today:
                        self.trigger_ai_report_thread(manual=False)
                        self.report_sent_today = True
                    elif now_utc.hour == 15 and now_utc.minute > 1:
                        self.report_sent_today = False

                # 5. Получение рыночных данных с индикаторами
                df = self.get_market_data_enhanced()
                if df is None:
                    time.sleep(TRAILING_UPDATE_INTERVAL)
                    continue

                # 6. Health Check (каждые 20 секунд)
                if time.time() - last_doctor_check > 20:
                    if not self.in_position:
                        # Проверяем, не появилась ли "сиротская" позиция на бирже
                        try:
                            positions = self.exchange.fetch_positions([self.symbol])
                            for pos in positions:
                                if float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0)) != 0:
                                    self.log("🚑 Doctor: Found orphan position!", Col.MAGENTA)
                                    self._sync_position_with_exchange()
                        except:
                            pass
                    else:
                        self.perform_health_check()
                    last_doctor_check = time.time()

                # 7. Торговая логика
                if not self.in_position:
                    # === НЕТ ПОЗИЦИИ: Ищем сигнал для входа ===
                    signal_data = self.check_entry_signal_hybrid(df)
                    if signal_data:
                        self.open_position_limit(signal_data, df)
                else:
                    # === ЕСТЬ ПОЗИЦИЯ: Управляем ей ===

                    # 7.1 Обработка funding fee
                    self.process_funding()

                    # 7.2 Периодический лог PnL (каждые 30 секунд)
                    if time.time() - last_pnl_log > 30:
                        try:
                            side_mult = 1 if self.position_side == "Buy" else -1
                            cur_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
                            pnl_perc = (cur_pnl / self.balance) * 100 if self.balance > 0 else 0
                            self.log(f"📉 Status: PnL {cur_pnl:.2f}$ ({pnl_perc:.2f}%) | DCA: {self.safety_count}", Col.BLUE)
                            last_pnl_log = time.time()
                        except:
                            pass

                    # 7.3 Trailing Stop (выбор по типу рынка)
                    if self.is_trending_market:
                        if TRAILING_ENABLED and self.check_trailing_stop():
                            continue
                    else:
                        if self.check_range_trailing():
                            continue

                    # 7.4 Проверка максимального убытка (Stop Loss через PnL биржи)
                    try:
                        max_loss = self.get_effective_balance() * MAX_ACCOUNT_LOSS_PCT
                        u_pnl = self.get_current_pnl()

                        if u_pnl <= -max_loss:
                            self.log(f"🚨 STOP LOSS TRIGGERED! PnL: {u_pnl:.2f}$ / Max: -{max_loss:.2f}$", Col.RED)
                            self.close_position_market(f"STOP LOSS -{MAX_ACCOUNT_LOSS_PCT*100}%")
                            continue
                    except:
                        pass

                    # 7.5 Мониторинг ордеров (TP/DCA исполнение)
                    try:
                        open_orders = self.exchange.fetch_open_orders(self.symbol)
                        oids = [str(o['id']) for o in open_orders]

                        # Проверка DCA ордера
                        if self.dca_order_id:
                            if str(self.dca_order_id) not in oids:
                                check = self.exchange.fetch_order(self.dca_order_id, self.symbol)
                                if check['status'] == 'closed':
                                    self.execute_dca(float(check['average']), float(check['amount']), self.dca_order_id)
                                elif check['status'] in ['canceled', 'rejected', 'expired']:
                                    self.log("⚠️ DCA Order Canceled! Checking position...", Col.RED)
                                    self.dca_order_id = None

                                    try:
                                        self._sync_position_with_exchange()
                                        if not self.in_position or self.total_size_coins == 0:
                                            self.log("🚨 DCA canceled because position closed externally!", Col.RED)
                                            self.reset_position()
                                        else:
                                            self.log("✅ Position exists, replacing DCA...", Col.YELLOW)
                                            self.place_limit_dca()
                                    except Exception as e:
                                        self.log(f"⚠️ DCA canceled handler error: {e}", Col.YELLOW)
                                        self.reset_position()

                        # Проверка TP ордера
                        if self.tp_order_id and str(self.tp_order_id) not in oids:
                            check = self.exchange.fetch_order(self.tp_order_id, self.symbol)
                            if check['status'] == 'closed':
                                self.log("🎯 TP Executed!", Col.GREEN)
                                try:
                                    self.exchange.cancel_order(self.dca_order_id, self.symbol)
                                except:
                                    pass

                                fill_price = float(check['average'])
                                tp_fee = self.get_real_order_fee(self.tp_order_id) or (self.total_size_coins * fill_price * MAKER_FEE)
                                self.current_trade_fees += tp_fee

                                side_mult = 1 if self.position_side == "Buy" else -1
                                net = ((fill_price - self.avg_price) * self.total_size_coins * side_mult) - self.current_trade_fees
                                self.balance += net
                                self.in_position = False

                                from datetime import timedelta
                                self.last_trade_time = datetime.now() - timedelta(hours=2)

                                self.session_total_pnl += net
                                self.session_total_fees += self.current_trade_fees
                                if net > 0:
                                    self.session_wins += 1
                                else:
                                    self.session_losses += 1

                                # Сохраняем данные ДО сброса для логирования
                                saved_side = self.position_side
                                saved_avg = self.avg_price
                                saved_safety = self.safety_count
                                saved_fees = self.current_trade_fees
                                saved_confluence = self.current_confluence

                                try:
                                    with open(CSV_FILE, 'a', newline='') as f:
                                        csv.writer(f).writerow([
                                            datetime.now(),
                                            self.symbol,
                                            saved_side,
                                            "TP",
                                            net,
                                            saved_fees,
                                            saved_avg,
                                            fill_price,
                                            saved_safety,
                                            "LIMIT",
                                            self.current_volatility,
                                            saved_confluence
                                        ])
                                except:
                                    pass

                                self.log_blackbox("TP_CLOSED", {"pnl": net, "price": fill_price})

                                tg_msg = (f"🎯 <b>TP HIT!</b>\n"
                                         f"💰 PnL: {net:.2f}$ (Net)\n"
                                         f"📊 Exit: {fill_price:.2f}\n"
                                         f"🔄 DCA Used: {saved_safety}\n"
                                         f"💸 Fees: {saved_fees:.2f}$")
                                self.tg.send(tg_msg)

                                self.reset_position()

                                if self.graceful_stop_mode:
                                    self.trading_active = False
                                    self.graceful_stop_mode = False
                                    self.tg.send("🛑 Stopped (Graceful)", self.get_keyboard())

                                self.update_dashboard(force=True)

                            elif check['status'] in ['canceled', 'rejected', 'expired']:
                                self.log("⚠️ TP Order Canceled! Checking position...", Col.RED)
                                self.tp_order_id = None

                                try:
                                    self._sync_position_with_exchange()
                                    if not self.in_position or self.total_size_coins == 0:
                                        self.log("🚨 TP canceled because position closed externally!", Col.RED)
                                        self.reset_position()
                                    else:
                                        self.log("✅ Position exists, replacing TP...", Col.YELLOW)
                                        self.place_limit_tp()
                                except Exception as e:
                                    self.log(f"⚠️ TP canceled handler error: {e}", Col.YELLOW)
                                    self.reset_position()

                    except Exception as e:
                        self.log(f"⚠️ Order check error: {e}", Col.YELLOW)

                time.sleep(TRAILING_UPDATE_INTERVAL)

            except KeyboardInterrupt:
                self.log("⏹️ Bot stopped by user", Col.YELLOW)
                self.running = False
                break
            except Exception as e:
                self.log(f"⚠️ Loop iteration error: {e}", Col.YELLOW)
                time.sleep(5)


# Для обратной совместимости
TradingBot = HybridTradingBotModular
