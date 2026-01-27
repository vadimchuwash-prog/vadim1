"""
🤖 HYBRID TRADING BOT v1.4.6 - MONITORING MODULE
Модуль мониторинга, управления и AI функций

Функции:
- perform_health_check: Проверка здоровья позиции
- update_dashboard: Обновление дашборда в Telegram
- send_or_update_trade_message: Сообщения о сделках
- get_keyboard: Клавиатура Telegram
- check_telegram_commands: Обработка команд из Telegram
- trigger_ai_report_thread: Генерация AI отчётов
- trigger_ai_chat_reply: AI чат с пользователем
- process_funding: Обработка funding fee
"""

import time
import threading
from datetime import datetime
from config import *


class BotMonitoringMixin:
    """
    🔍 Миксин мониторинга и управления

    Методы:
    - perform_health_check: Агрессивная проверка позиции
    - update_dashboard: Telegram дашборд
    - send_or_update_trade_message: Уведомления о сделках
    - get_keyboard: Inline клавиатура
    - check_telegram_commands: Обработка команд
    - trigger_ai_report_thread: AI отчёты
    - trigger_ai_chat_reply: AI чат
    - process_funding: Funding fee
    """

    def perform_health_check(self):
        """🆕 v1.2.1 - АГРЕССИВНАЯ проверка здоровья позиции"""
        try:
            if not self.in_position:
                return

            # 🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ БАГ #6: Сначала синхронизация с биржей!
            self._sync_position_with_exchange()

            # Проверяем что позиция ЕЩЁ существует на бирже
            if not self.in_position or self.total_size_coins == 0:
                self.log("🚨 Doctor: Position closed externally!", Col.RED)
                self.reset_position()
                return

            # 1. Проверяем наличие TP ордера
            if not self.tp_order_id:
                self.log("🚑 Doctor: No TP order! Placing...", Col.YELLOW)
                self.place_limit_tp()
            else:
                # Проверяем что TP ордер существует на бирже
                try:
                    order = self.exchange.fetch_order(self.tp_order_id, self.symbol)
                    if order['status'] in ['canceled', 'rejected', 'expired']:
                        self.log(f"🚑 Doctor: TP order {self.tp_order_id} is {order['status']}! Re-placing...", Col.YELLOW)
                        self.tp_order_id = None
                        self.place_limit_tp()
                except Exception as e:
                    # Если ордер не найден - переставляем
                    self.log(f"🚑 Doctor: TP order {self.tp_order_id} not found! Re-placing...", Col.YELLOW)
                    self.tp_order_id = None
                    self.place_limit_tp()

            # 2. Проверяем DCA только если не на максимальном уровне
            if self.safety_count < SAFETY_ORDERS_COUNT:

                # 2.1 Вычисляем правильную цену DCA
                dists, weights = self.get_dca_parameters()
                dist_multiplier = self.get_smart_distance_multiplier(self.safety_count)
                base_dist = dists[self.safety_count]
                actual_dist = base_dist * dist_multiplier

                # Правильное направление для SHORT/LONG
                if self.position_side == "Buy":
                    expected_dca_price = self.base_entry_price * (1 - actual_dist)
                else:
                    expected_dca_price = self.base_entry_price * (1 + actual_dist)

                # 2.2 Проверяем существующий DCA ордер
                dca_needs_replacement = False

                if not self.dca_order_id:
                    dca_needs_replacement = True
                    self.log("🚑 Doctor: No DCA order! Placing...", Col.YELLOW)
                else:
                    try:
                        order = self.exchange.fetch_order(self.dca_order_id, self.symbol)

                        # Проверяем статус
                        if order['status'] in ['canceled', 'rejected', 'expired']:
                            dca_needs_replacement = True
                            self.log(f"🚑 Doctor: DCA order {self.dca_order_id} is {order['status']}! Re-placing...", Col.YELLOW)

                        # 🆕 ПРОВЕРЯЕМ ЦЕНУ - если ордер старый (цена отличается > 0.5%)
                        elif order['status'] == 'open':
                            current_price = float(order['price'])
                            price_diff_pct = abs((current_price - expected_dca_price) / expected_dca_price * 100)

                            if price_diff_pct > 0.5:  # Если цена отличается больше чем на 0.5%
                                dca_needs_replacement = True
                                self.log(f"🚑 Doctor: DCA price outdated! Current: {current_price:.4f}, Expected: {expected_dca_price:.4f} (diff: {price_diff_pct:.2f}%)", Col.YELLOW)
                                # Отменяем старый
                                try:
                                    self.exchange.cancel_order(self.dca_order_id, self.symbol)
                                    self.log(f"🗑️ Cancelled outdated DCA {self.dca_order_id}", Col.GRAY)
                                except:
                                    pass

                    except Exception as e:
                        # Ордер не найден или ошибка - переставляем
                        dca_needs_replacement = True
                        self.log(f"🚑 Doctor: DCA order {self.dca_order_id} check failed! Re-placing...", Col.YELLOW)

                # 2.3 Переставляем DCA если нужно
                if dca_needs_replacement:
                    self.dca_order_id = None
                    self.place_limit_dca()

            # 3. 🆕 ДОПОЛНИТЕЛЬНО: Отменяем ВСЕ лишние ордера на бирже
            try:
                open_orders = self.exchange.fetch_open_orders(self.symbol)
                valid_order_ids = set()
                if self.tp_order_id:
                    valid_order_ids.add(str(self.tp_order_id))
                if self.dca_order_id:
                    valid_order_ids.add(str(self.dca_order_id))

                for order in open_orders:
                    order_id = str(order['id'])
                    if order_id not in valid_order_ids:
                        # Это какой-то старый/лишний ордер - отменяем
                        try:
                            self.exchange.cancel_order(order_id, self.symbol)
                            self.log(f"🗑️ Doctor: Cancelled orphan order {order_id} @ {order['price']}", Col.MAGENTA)
                        except:
                            pass
            except Exception as e:
                self.log(f"⚠️ Doctor: Orphan cleanup error: {e}", Col.YELLOW)

            # 4. 🆕 v1.3: PnL Audit
            self.check_pnl_audit()

        except Exception as e:
            self.log(f"⚠️ Health Check Error: {e}", Col.YELLOW)
            import traceback
            self.log_debug(traceback.format_exc())

    def update_dashboard(self, force=False):
        """📊 🆕 УЛУЧШЕННЫЙ ДАШБОРД"""
        now = time.time()
        if not force and (now - self.last_dashboard_update < 15): return
        self.last_dashboard_update = now

        # Статус
        status_icon = "🟢" if self.trading_active else "🔴"
        status_text = "ACTIVE" if self.trading_active else "STOPPED"
        if self.graceful_stop_mode:
            status_icon = "🟡"
            status_text = "STOPPING..."

        # Баланс и прогресс
        balance_change = self.balance - self.start_balance
        balance_pct = (balance_change / self.start_balance * 100) if self.start_balance > 0 else 0
        balance_icon = "📈" if balance_change >= 0 else "📉"

        # Винрейт
        total_trades = self.session_wins + self.session_losses
        win_rate = (self.session_wins / total_trades * 100) if total_trades > 0 else 0
        wr_icon = "🟢" if win_rate >= 60 else "🟡" if win_rate >= 50 else "🔴"

        # Рыночные условия
        vol_icon = "🔥" if self.current_volatility > 0.004 else "📊" if self.current_volatility > 0.0025 else "😴"
        trend_icon = "📈" if self.is_trending_market else "↔️"

        # Начало дашборда
        dash = f"""╔══════════════════════════════
║ 🚀 <b>HYBRID BOT v1.4.6</b> {status_icon} {status_text}
╠══════════════════════════════
║
║ 💰 <b>БАЛАНС</b>
║ ├─ Текущий: <b>${self.balance:.2f}</b>
║ ├─ Стартовый: ${self.start_balance:.2f}
║ └─ Изменение: {balance_icon} <b>${balance_change:+.2f}</b> ({balance_pct:+.2f}%)
║
║ 📊 <b>СЕССИЯ</b>
║ ├─ PnL: <b>${self.session_total_pnl:+.2f}</b>
║ ├─ Комиссии: -${self.session_total_fees:.2f}
║ ├─ Сделок: {total_trades} (W:{self.session_wins} / L:{self.session_losses})
║ └─ Винрейт: {wr_icon} <b>{win_rate:.1f}%</b>
║
║ 🌍 <b>РЫНОК</b>
║ ├─ Цена: <b>${self.last_price:.2f}</b>
║ ├─ Волатильность: {vol_icon} {self.current_volatility*100:.3f}%
║ └─ Режим: {trend_icon} {'TREND' if self.is_trending_market else 'RANGE'}
"""

        # Если в позиции - добавляем детали
        if self.in_position:
            side_mult = 1 if self.position_side == "Buy" else -1
            unrealized = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
            margin = (self.avg_price * self.total_size_coins) / LEVERAGE
            pnl_pct = (unrealized / margin * 100) if margin > 0 else 0
            pnl_icon = "🟢" if unrealized >= 0 else "🔴"

            # Stage icon
            stage_icons = ["", "🟡", "🟠", "🔴"]
            stage_icon = stage_icons[self.current_stage] if self.current_stage <= 3 else "⭐"

            # Время в позиции
            if self.trade_start_time:
                time_in_trade = (datetime.now() - self.trade_start_time).total_seconds()
                hours = int(time_in_trade // 3600)
                minutes = int((time_in_trade % 3600) // 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            else:
                time_str = "N/A"

            # TP дистанция
            tp_distance = float(self.get_dynamic_tp_steps())
            target_tp = self.avg_price * (1 + (tp_distance * side_mult))
            # 🆕 v1.4.6: БАГ #2 - Защита от деления на ноль
            dist_tp_pct = abs((target_tp - self.last_price) / self.last_price * 100) if self.last_price != 0 else 0.0

            # DCA дистанция
            if self.safety_count < SAFETY_ORDERS_COUNT:
                dists, _ = self.get_dca_parameters()
                mult = self.get_smart_distance_multiplier(self.safety_count)
                target_dca = self.base_entry_price * (1 + ((dists[self.safety_count] * mult) * (-side_mult)))
                # 🆕 v1.4.6: БАГ #3 - Защита от деления на ноль
                dist_dca_pct = abs((self.last_price - target_dca) / self.last_price * 100) if self.last_price != 0 else 0.0
                dca_str = f"{dist_dca_pct:.2f}%"
            else:
                dca_str = "MAX"

            # Trailing status
            if self.range_trailing_enabled:
                trail_icon = "🎯"
                # Динамический порог в зависимости от прибыли
                current_callback = self.get_range_trailing_callback()
                callback_pct = current_callback * 100
                trail_str = f"RANGE @ ${self.range_peak_price:.2f} (-{callback_pct:.2f}%)"
            elif self.trailing_active:
                trail_icon = "🎯"
                # Вычисляем текущий порог для Trend trailing
                tp_dist = self.get_dynamic_tp_steps()
                vol = self.current_volatility
                vol_mode = 'high_vol' if vol > 0.004 else ('medium_vol' if vol > 0.0025 else 'low_vol')
                callback_pct = (tp_dist * TREND_TRAILING_CALLBACK_RATIOS[vol_mode]) * 100
                trail_str = f"TREND @ ${self.trailing_peak_price:.2f} (-{callback_pct:.2f}%)"
            else:
                trail_icon = "💤"
                trail_str = "Waiting..."

            dash += f"""║
╠══════════════════════════════
║ 📍 <b>ПОЗИЦИЯ</b> {stage_icon} Stage{self.current_stage}
╠══════════════════════════════
║
║ 🎯 <b>ВХОД</b>
║ ├─ Сторона: <b>{"📈 LONG" if self.position_side == "Buy" else "📉 SHORT"}</b>
║ ├─ Цена входа: ${self.avg_price:.4f}
║ ├─ Размер: {self.total_size_coins:.4f} BTC
║ ├─ Объём: ${self.entry_usd_vol:.2f}
║ ├─ Confluence: ⭐ {self.current_confluence}/7
║ └─ Время: ⏱️ {time_str}
║
║ 💹 <b>P&L</b>
║ ├─ Нереализ.: {pnl_icon} <b>${unrealized:+.2f}</b>
║ ├─ ROI: <b>{pnl_pct:+.2f}%</b>
║ └─ Комиссии: -${self.current_trade_fees:.2f}
║
║ 🔨 <b>DCA СЕТКА</b>
║ ├─ Уровень: <b>{self.safety_count}/{SAFETY_ORDERS_COUNT}</b>
║ ├─ След. DCA: {dca_str}
║ └─ Режим: {trend_icon} {'TREND' if self.is_trending_market else 'RANGE'}
║
║ 🏁 <b>ВЫХОД</b>
║ ├─ TP дист.: {dist_tp_pct:.2f}%
║ ├─ TP цена: ${target_tp:.4f}
║ └─ Trailing: {trail_icon} {trail_str}
"""
        else:
            # Нет позиции
            dash += f"""║
╠══════════════════════════════
║ 💤 <b>НЕТ ПОЗИЦИИ</b>
╠══════════════════════════════
║
║ Ожидание сигнала...
║
║ 📋 Сегодня сделок: {self.trades_today}/{DAILY_TRADE_LIMIT}
"""

        # Футер
        dash += """║
╚══════════════════════════════"""

        if not self.dashboard_msg_id:
            self.dashboard_msg_id = self.tg.send(dash, self.get_keyboard())
        else:
            success = self.tg.edit_message(self.dashboard_msg_id, dash, self.get_keyboard())
            # Если редактирование не удалось, попробуем создать новое сообщение только один раз
            if not success:
                self.log("⚠️ Failed to edit dashboard, sending new one", Col.YELLOW)
                self.dashboard_msg_id = self.tg.send(dash, self.get_keyboard())

    def send_or_update_trade_message(self, event, pnl=0.0, exit_price=None, is_final=False, calculated_fee_only=0.0):
        """Сообщение о сделке"""
        side_emoji = "📈" if self.position_side == "Buy" else "📉"
        current = exit_price if exit_price else self.last_price

        if not is_final and self.in_position:
            side_mult = 1 if self.position_side == "Buy" else -1
            pnl_val = (current - self.avg_price) * self.total_size_coins * side_mult
            fee_display = self.current_trade_fees
        else:
            pnl_val = pnl
            fee_display = calculated_fee_only

        roi = (pnl_val / self.entry_usd_vol * 100) if self.entry_usd_vol else 0

        msg = (
            f"🏁 <b>Сделка:</b> {self.symbol} {self.position_side} {side_emoji}\n"
            f"🔹 Событие: {event}\n"
            f"💰 PnL: <b>{pnl_val:+.2f}$</b> (ROI: {roi:+.2f}%)\n"
            f"💸 Комиссия: -{fee_display:.2f}$\n"
            f"📊 Вход: {self.avg_price:.4f} | Текущая: {current:.4f}\n"
            f"🔨 DCA: {self.safety_count}/{SAFETY_ORDERS_COUNT}"
        )
        if self.trade_msg_id:
            self.tg.edit_message(self.trade_msg_id, msg, self.get_keyboard())
            if is_final: self.trade_msg_id = None
        else:
            self.trade_msg_id = self.tg.send(msg, self.get_keyboard())

    def get_keyboard(self):
        """Клавиатура Telegram"""
        s_btn = {"text": "🛑 STOP (Graceful)", "callback_data": "graceful_stop"}
        if not self.trading_active:
            s_btn = {"text": "▶️ START", "callback_data": "start_bot"}
        elif self.graceful_stop_mode:
            s_btn = {"text": "⚠️ CANCEL STOP", "callback_data": "cancel_stop"}

        return {"inline_keyboard": [
            [s_btn],
            [{"text": "📊 Bal", "callback_data": "balance"}, {"text": "🧠 AI Report", "callback_data": "ai_report"}],
            [{"text": "🔄 Refresh", "callback_data": "refresh"}, {"text": "💣 Panic Sell", "callback_data": "panic_sell"}]
        ]}

    def check_telegram_commands(self):
        """Обработка команд Telegram"""
        for up in self.tg.get_updates():
            if up['type'] == 'callback':
                # 🔧 v1.4.2: Исправлен формат обработки callback
                callback_id = up['callback_id']
                msg_id = up['message_id']
                data = up['data']

                # Подтверждаем получение callback (убирает "часики")
                self.tg.answer_callback(callback_id)

                if data == "start_bot":
                    self.trading_active = True
                    self.graceful_stop_mode = False
                    self.tg.edit_message(msg_id, "✅ Бот запущен!", self.get_keyboard())
                    self.update_dashboard(force=True)

                elif data == "graceful_stop":
                    self.graceful_stop_mode = True
                    self.tg.edit_message(msg_id, "⏳ Завершаю текущую сделку...", self.get_keyboard())
                    if not self.in_position:
                        self.trading_active = False
                        self.graceful_stop_mode = False
                        self.update_dashboard(force=True)

                elif data == "cancel_stop":
                    self.graceful_stop_mode = False
                    self.tg.edit_message(msg_id, "✅ Остановка отменена!", self.get_keyboard())
                    self.update_dashboard(force=True)

                elif data == "panic_sell":
                    self.tg.answer_callback(callback_id, "⚠️ Экстренное закрытие!")
                    self.close_position_market("Panic Sell")

                elif data == "balance":
                    self.refresh_wallet_status()
                    bal_msg = f"💵 <b>Баланс:</b> ${self.balance:.2f}\n"
                    bal_msg += f"📈 <b>Пик:</b> ${self.peak_balance:.2f}\n"
                    bal_msg += f"{'📊' if self.balance >= self.start_balance else '📉'} <b>Изменение:</b> ${self.balance - self.start_balance:.2f}"
                    self.tg.edit_message(msg_id, bal_msg, self.get_keyboard())

                elif data == "refresh":
                    self.tg.answer_callback(callback_id, "🔄 Обновляю...")
                    self.update_dashboard(force=True)

                elif data == "ai_report":
                    self.tg.answer_callback(callback_id, "🤖 Генерирую отчёт...")
                    self.trigger_ai_report_thread(manual=True)

            # 🆕 Обработка текстовых сообщений (AI чат)
            elif up['type'] == 'message':
                text = up.get('text', '').strip()
                if text.startswith('?') or text.startswith('/ask '):
                    q = text.lstrip('?/').replace('ask', '').strip()
                    if q:
                        self.tg.send(f"⏳ Думаю над вопросом: {q[:50]}...")
                        self.trigger_ai_chat_reply(q)

    def trigger_ai_report_thread(self, manual=False):
        """AI отчёт"""
        if not self.has_ai: return
        t = threading.Thread(target=self._generate_and_send_ai_report, args=(manual,), daemon=True)
        t.start()

    def _generate_and_send_ai_report(self, manual):
        try:
            import google.genai as genai
            client = genai.Client(api_key=self.ai_key)

            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = "".join(f.readlines()[-40:])
            except:
                logs = "Logs unavailable"

            m_info = "N/A"
            if self.current_market_df is not None:
                row = self.current_market_df.iloc[-2]
                m_info = f"Close:{row['close']}, ADX:{row['ADX']:.1f}, RSI:{row['RSI']:.1f}"

            prompt = f"Ты — AI-аналитик торгового бота. Рынок: {m_info}. Последние логи: {logs}. Дай краткий анализ и совет (макс 200 слов)."
            response = client.models.generate_content(model=self.ai_model_name, contents=prompt)
            self.tg.send(f"🤖 <b>AI REPORT:</b>\n\n{response.text}")
            self.log("✅ AI Report sent", Col.GREEN)

        except ImportError as e:
            error_msg = "❌ <b>AI Error:</b> Библиотека google-genai не установлена.\n\nУстановите: pip install google-genai"
            self.tg.send(error_msg)
            self.log(f"❌ AI Import Error: {e}", Col.RED)

        except Exception as e:
            error_msg = f"❌ <b>AI Error:</b> {str(e)[:200]}"
            self.tg.send(error_msg)
            self.log(f"❌ AI Report Error: {e}", Col.RED)

    def trigger_ai_chat_reply(self, user_question):
        """🆕 AI ЧАТ - общение с ботом"""
        if not self.has_ai:
            self.tg.send("⚠️ AI chat unavailable (no API key or library)")
            return
        t = threading.Thread(target=self._generate_ai_chat_response, args=(user_question,), daemon=True)
        t.start()

    def _generate_ai_chat_response(self, question):
        """🆕 Генерация ответа AI на вопрос"""
        try:
            import google.genai as genai
            client = genai.Client(api_key=self.ai_key)

            # Собираем контекст
            context = []

            # Текущее состояние
            if self.in_position:
                side_mult = 1 if self.position_side == "Buy" else -1
                unrealized = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
                context.append(f"Current position: {self.position_side}, PnL: ${unrealized:.2f}, DCA: {self.safety_count}/{SAFETY_ORDERS_COUNT}")
            else:
                context.append("No position")

            # Статистика
            total = self.session_wins + self.session_losses
            wr = (self.session_wins / total * 100) if total > 0 else 0
            context.append(f"Session: PnL ${self.session_total_pnl:.2f}, Trades: {total} (WR: {wr:.1f}%)")

            # Рынок
            if self.current_market_df is not None:
                row = self.current_market_df.iloc[-2]
                context.append(f"Market: Price ${self.last_price:.2f}, RSI {row['RSI']:.1f}, ADX {row['ADX']:.1f}, ATR {self.current_volatility*100:.3f}%")

            # Логи (последние 20 строк)
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    logs = "".join(f.readlines()[-20:])
                    context.append(f"Recent logs: {logs[-500:]}")  # Последние 500 символов
            except:
                pass

            context_str = " | ".join(context)

            prompt = f"""You are an AI trading assistant. User asks: "{question}"

Context: {context_str}

Provide a short, helpful answer (max 200 words). Be specific and actionable if possible."""

            response = client.models.generate_content(model=self.ai_model_name, contents=prompt)
            self.tg.send(f"💬 <b>AI:</b> {response.text}")

        except ImportError as e:
            self.tg.send(f"❌ <b>AI Error:</b> Библиотека google-genai не установлена.\n\nУстановите: pip install google-genai")
            self.log(f"❌ AI Chat Import Error: {e}", Col.RED)
        except Exception as e:
            self.tg.send(f"❌ AI chat error: {str(e)[:200]}")
            self.log(f"❌ AI Chat Error: {e}", Col.RED)

    def process_funding(self):
        """Обработка funding fee"""
        if not self.in_position or not self.last_funding_time:
            self.last_funding_time = datetime.now()
            return
        if (datetime.now() - self.last_funding_time).total_seconds() >= 8 * 3600:
            cost = (self.total_size_coins * self.avg_price) * FUNDING_RATE_8H
            self.log(f"📉 Funding estimated: -{cost:.2f}$", Col.GRAY)
            self.last_funding_time = datetime.now()
