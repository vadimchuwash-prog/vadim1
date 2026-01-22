"""
🤖 HYBRID TRADING BOT v1.4.1
Основной торговый бот с гибридной системой входа
КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.1:
- Детальное логирование place_limit_tp()
- Детальное логирование place_limit_dca()
- Исправлено сравнение ID ордеров
"""

import time
import logging
import pandas as pd
import ta
import sys
import os
import csv
import json
import threading
import traceback
from datetime import datetime, timedelta, timezone

from config import *
from telegram_bot import TelegramBot
from ai_assistant import AIAssistant

# ==========================================
# 🤖 HYBRID TRADING BOT v1.1
# ==========================================
class HybridTradingBot:
    def __init__(self, exchange, telegram_bot):
        self.exchange = exchange
        self.tg = telegram_bot
        self.symbol = SYMBOL
        self.timeframe = TIMEFRAME
        
        # AI
        self.has_ai = HAS_AI and AI_GEMINI_KEY
        self.ai_key = AI_GEMINI_KEY
        self.ai_model_name = AI_MODEL_NAME
        self.report_sent_today = False
        
        # Баланс
        self.balance = 0.0
        self.peak_balance = 0.0
        self.start_balance = 0.0
        self.refresh_wallet_status()
        self.start_balance = self.balance
        
        # Позиция
        self.in_position = False
        self.position_side = None
        self.avg_price = 0.0
        self.total_size_coins = 0.0
        self.first_entry_price = 0.0
        self.base_entry_price = 0.0
        self.entry_usd_vol = 0.0
        self.safety_count = 0
        self.current_confluence = 0
        self.current_stage = 0
        
        # Ордера
        self.tp_order_id = None
        self.dca_order_id = None
        self.sl_order_id = None  # 🆕 Stop Loss ордер
        
        # Трейлинг
        self.trailing_active = False
        self.trailing_peak_price = 0.0
        
        # Статистика
        self.session_total_pnl = 0.0
        self.session_total_fees = 0.0
        self.session_wins = 0
        self.session_losses = 0
        self.current_trade_fees = 0.0
        self.trades_today = 0
        self.trade_start_time = None
        
        # Рынок
        self.last_price = 0.0
        self.current_volatility = 0.0
        self.is_trending_market = True
        self.current_market_df = None
        self.last_trade_time = None
        self.last_funding_time = None
        
        # UI
        self.dashboard_msg_id = None
        self.trade_msg_id = None
        self.last_dashboard_update = 0
        
        # Контроль
        self.running = True
        self.trading_active = True
        self.graceful_stop_mode = False
        
        # Логирование
        logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')
        self.log("🚀 Hybrid Bot v1.1 Started!", Col.GREEN)
        self.log(f"💰 Starting Balance: ${self.balance:.2f}", Col.CYAN)
        if self.has_ai: self.log("🤖 AI Analytics & Chat: ENABLED", Col.CYAN)
        
        # CSV заголовки
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='') as f:
                csv.writer(f).writerow(['timestamp', 'symbol', 'side', 'reason', 'pnl', 'fees', 'entry', 'exit', 'dca_count', 'order_type', 'volatility', 'confluence'])
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 🆕 v1.3: НОВЫЕ ФУНКЦИИ
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def log_blackbox(self, event_type, data):
        """
        🆕 v1.3: Blackbox JSON логирование
        Записывает все события в JSON для детального анализа
        """
        import json
        from datetime import datetime
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data
        }
        
        try:
            with open("blackbox.json", "a", encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            pass  # Тихо игнорируем ошибки логирования
    
    def check_pnl_audit(self):
        """
        🆕 v1.3: PnL Audit - проверка корректности расчётов
        Сравнивает расчётный PnL с данными биржи
        Детектор скрытых комиссий, багов, лагов
        """
        if not self.in_position or self.total_size_coins == 0:
            return
        
        try:
            # Расчётный PnL
            side_mult = 1 if self.position_side == "Buy" else -1
            calc_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
            
            # PnL от биржи
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))
                
                if abs(amt) > 0.0001:
                    exchange_pnl = float(pos.get('unrealizedPnl', 0))
                    
                    # Проверка расхождения (только если PnL значимый)
                    if abs(exchange_pnl) > 1.0:
                        diff = abs(calc_pnl - exchange_pnl)
                        diff_pct = (diff / abs(exchange_pnl)) * 100 if abs(exchange_pnl) > 0 else 0
                        
                        if diff_pct > 10:  # 10% расхождение
                            msg = (f"⚠️ <b>PnL MISMATCH!</b>\n"
                                   f"Расчёт: {calc_pnl:.2f}$\n"
                                   f"Биржа: {exchange_pnl:.2f}$\n"
                                   f"Разница: {diff_pct:.1f}%")
                            
                            self.log(msg.replace('<b>', '').replace('</b>', ''), Col.RED)
                            self.tg.send(msg)
                            
                            # Логируем в blackbox
                            self.log_blackbox("PNL_MISMATCH", {
                                "calc_pnl": calc_pnl,
                                "exchange_pnl": exchange_pnl,
                                "diff": diff,
                                "diff_pct": diff_pct
                            })
                    break
        except Exception as e:
            self.log(f"⚠️ PnL Audit error: {e}", Col.YELLOW)
    
    def start_future_spy(self, exit_price, exit_side, exit_size):
        """
        🆕 v1.3: Future Spy - анализ упущенной прибыли
        Следит за ценой 15 минут после выхода
        Помогает оптимизировать TP и Trailing
        """
        import threading
        
        def spy_thread():
            start_time = time.time()
            max_price = exit_price
            min_price = exit_price
            
            self.log(f"🔮 Future Spy started: monitoring for 15 minutes...", Col.MAGENTA)
            
            while time.time() - start_time < 900:  # 15 минут
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    price = float(ticker['last'])
                    
                    max_price = max(max_price, price)
                    min_price = min(min_price, price)
                    
                    time.sleep(10)  # Проверка каждые 10 секунд
                except:
                    break
            
            # Вычисляем упущенную прибыль
            if exit_side == "Buy":
                missed_profit = (max_price - exit_price) * exit_size
                best_exit = max_price
            else:
                missed_profit = (exit_price - min_price) * exit_size
                best_exit = min_price
            
            if missed_profit > 0.5:  # Упущено больше $0.5
                missed_pct = (missed_profit / (exit_price * exit_size)) * 100
                
                msg = (f"🔮 <b>Future Spy Report:</b>\n"
                       f"Exit: {exit_price:.2f}\n"
                       f"Best: {best_exit:.2f}\n"
                       f"Missed: ${missed_profit:.2f} ({missed_pct:.2f}%)")
                
                self.log(msg.replace('<b>', '').replace('</b>', ''), Col.MAGENTA)
                self.tg.send(msg)
                
                # Логируем в blackbox
                self.log_blackbox("FUTURE_SPY", {
                    "missed_profit": missed_profit,
                    "missed_pct": missed_pct,
                    "exit_price": exit_price,
                    "best_price": best_exit,
                    "max_price": max_price,
                    "min_price": min_price
                })
            else:
                self.log(f"🔮 Future Spy: Exit was optimal (missed < $0.5)", Col.GRAY)
        
        # Запускаем в отдельном потоке
        threading.Thread(target=spy_thread, daemon=True).start()

    def log(self, msg, color=Col.WHITE):
        print(f"{color}{msg}{Col.RESET}")
        logging.info(msg)
    
    def log_debug(self, msg):
        logging.debug(msg)

    def get_effective_balance(self):
        return self.balance * ALLOWED_CAPITAL_PCT

    def get_market_data_enhanced(self):
        """Получение рыночных данных с индикаторами"""
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=200)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # EMA
            df['EMA9'] = ta.trend.EMAIndicator(df['close'], 9).ema_indicator()
            df['EMA15'] = ta.trend.EMAIndicator(df['close'], 15).ema_indicator()
            df['EMA20'] = ta.trend.EMAIndicator(df['close'], 20).ema_indicator()
            df['EMA50'] = ta.trend.EMAIndicator(df['close'], 50).ema_indicator()
            
            # RSI
            df['RSI'] = ta.momentum.RSIIndicator(df['close'], 14).rsi()
            
            # ATR
            df['ATR'] = ta.volatility.AverageTrueRange(df['high'], df['low'], df['close'], 14).average_true_range()
            df['ATR_pct'] = df['ATR'] / df['close']
            
            # ADX
            df['ADX'] = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], 14).adx()
            
            # MACD
            macd = ta.trend.MACD(df['close'])
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            df['MACD_hist'] = macd.macd_diff()
            
            self.current_volatility = df['ATR_pct'].iloc[-2] if not pd.isna(df['ATR_pct'].iloc[-2]) else 0.0
            
            # Определение тренда
            if not pd.isna(df['ADX'].iloc[-2]):
                self.is_trending_market = df['ADX'].iloc[-2] > 25
            
            self.current_market_df = df
            return df
        except Exception as e: 
            self.log(f"Market Data Error: {e}", Col.RED)
            return None

    def calculate_confluence_score(self, df):
        """🎯 Система confluence scoring (0-7)"""
        row = df.iloc[-2]
        prev = df.iloc[-3]
        score = 0
        
        # Фактор 1: RSI нейтральный
        if abs(row['RSI'] - 50) < 15:
            score += 1
        
        # Фактор 2: Тренд
        if row['EMA9'] > row['EMA20']:
            score += 1
        
        # Фактор 3: EMA momentum
        ema_momentum = (row['EMA9'] - prev['EMA9']) / prev['EMA9'] if prev['EMA9'] != 0 else 0
        if abs(ema_momentum) > 0.0001:
            score += 1
        
        # Фактор 4: Объём выше среднего
        volume_ratio = row['volume'] / df['volume'].iloc[-20:].mean()
        if volume_ratio > 1.2:
            score += 1
        
        # Фактор 5: Сильный RSI
        if abs(row['RSI'] - 50) < 10:
            score += 1
        
        # Фактор 6: Высокий объём
        if volume_ratio > 1.5:
            score += 1
        
        # Фактор 7: Спокойный рынок
        avg_atr = df['ATR_pct'].iloc[-20:].mean()
        if row['ATR_pct'] < avg_atr * 1.5:
            score += 1
        
        return score

    def check_entry_signal_hybrid(self, df):
        """🚀 Гибридная система входа"""
        if not self.trading_active or self.graceful_stop_mode:
            return None
        
        if self.trades_today >= DAILY_TRADE_LIMIT:
            return None
        
        if self.last_trade_time and (datetime.now() - self.last_trade_time).total_seconds() < MIN_TIME_BETWEEN_TRADES:
            return None
        
        row, prev = df.iloc[-2], df.iloc[-3]
        
        if pd.isna(row['EMA9']):
            return None
        
        # 1. Базовый сигнал
        buy_sig = row['EMA9'] > row['EMA15']
        sell_sig = row['EMA9'] < row['EMA15']
        side = "Buy" if buy_sig else "Sell" if sell_sig else None
        
        if not side:
            return None
        
        # 2. Momentum
        ema9_change = row['EMA9'] - prev['EMA9']
        if (side == "Buy" and ema9_change < 0):
            return None
        if (side == "Sell" and ema9_change > 0):
            return None
        
        # 3. Волатильность
        if QUALITY_FILTER_ENABLED:
            if not pd.isna(row['ATR_pct']) and row['ATR_pct'] < MIN_VOLATILITY_PCT:
                return None
        
        # 4. RSI безопасность
        if row['RSI'] < RSI_SAFE_MIN or row['RSI'] > RSI_SAFE_MAX:
            return None
        
        # 5. Фильтр объёма
        volume_ratio = row['volume'] / df['volume'].iloc[-20:].mean()
        if volume_ratio < MIN_VOLUME_RATIO:
            return None
        
        # 6. Микротренд
        candles = [
            df.iloc[-2]['close'] > df.iloc[-2]['open'],
            df.iloc[-3]['close'] > df.iloc[-3]['open']
        ]
        
        if side == "Buy":
            bullish_count = sum(candles)
            if bullish_count < MIN_MICROTREND_CANDLES:
                return None
        else:
            bearish_count = sum([not c for c in candles])
            if bearish_count < MIN_MICROTREND_CANDLES:
                return None
        
        # 7. Защита от ножа
        price_change_3 = (row['close'] - df.iloc[-4]['close']) / df.iloc[-4]['close']
        if abs(price_change_3) > KNIFE_PROTECTION_PCT:
            return None
        
        # 8. Confluence scoring
        confluence = self.calculate_confluence_score(df)
        
        if confluence < MIN_CONFLUENCE_SCORE:
            return None
        
        # Определяем стадию
        if confluence >= 5:
            stage = 3
        elif confluence >= 3:
            stage = 2
        else:
            stage = 1
        
        details = {
            'rsi': row['RSI'],
            'volume_ratio': volume_ratio,
            'atr_pct': row['ATR_pct'],
            'adx': row['ADX'],
            'price_change_3': price_change_3 * 100
        }
        
        return {
            'signal': side,
            'stage': stage,
            'confluence': confluence,
            'details': details
        }

    def calculate_smart_position_size_hybrid(self, df, stage):
        """🔥 Гибридный размер позиции"""
        row = df.iloc[-2]
        
        # Базовый по стадии
        if stage == 3:
            min_pct = STAGE3_MIN_ENTRY
            base_pct = STAGE3_BASE_ENTRY
            max_pct = STAGE3_MAX_ENTRY
        elif stage == 2:
            min_pct = STAGE2_MIN_ENTRY
            base_pct = STAGE2_BASE_ENTRY
            max_pct = STAGE2_MAX_ENTRY
        else:
            min_pct = STAGE1_MIN_ENTRY
            base_pct = STAGE1_BASE_ENTRY
            max_pct = STAGE1_MAX_ENTRY
        
        # Адаптация
        score = 0
        
        if row['ATR_pct'] > 0.005:
            score -= 1
        elif row['ATR_pct'] < 0.002:
            score += 1
        
        if row['ADX'] > 35:
            score += 1
        elif row['ADX'] < 20:
            score -= 1
        
        multiplier = 1.0 + (score * 0.10)
        final_pct = base_pct * multiplier
        
        final_pct = max(min_pct, min(final_pct, max_pct))
        
        return final_pct

    def get_smart_distance_multiplier(self, safety_count):
        """🔨 ИЗ ULTRABTC7 - Умный множитель DCA"""
        BASE_ATR = 0.0020 
        atr_factor = 1.0
        if self.current_volatility > 0:
            atr_factor = self.current_volatility / BASE_ATR
            atr_factor = max(0.8, min(atr_factor, 2.5))

        rsi_factor = 1.0
        current_rsi = 50.0
        if self.current_market_df is not None:
            current_rsi = self.current_market_df['RSI'].iloc[-2]
        
        if self.position_side == "Buy":
            if current_rsi < 20: rsi_factor = 1.6
            elif current_rsi < 30: rsi_factor = 1.3
            elif current_rsi < 40: rsi_factor = 1.1   
        elif self.position_side == "Sell":
            if current_rsi > 80: rsi_factor = 1.6
            elif current_rsi > 70: rsi_factor = 1.3
            elif current_rsi > 60: rsi_factor = 1.1

        geo_factor = 1.1 ** safety_count
        return atr_factor * rsi_factor * geo_factor

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
            
            prompt = f"Ты — AI-аналитик. Рынок: {m_info}. Логи: {logs}. Дай совет."
            response = client.models.generate_content(model=self.ai_model_name, contents=prompt)
            self.tg.send(f"🤖 <b>AI REPORT:</b>\n{response.text}")
        except: 
            pass

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
            
        except Exception as e:
            self.tg.send(f"❌ AI chat error: {str(e)[:100]}")

    def perform_health_check(self):
        """🆕 v1.2.1 - АГРЕССИВНАЯ проверка здоровья позиции"""
        try:
            if not self.in_position: 
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
║ 🚀 <b>HYBRID BOT v1.1</b> {status_icon} {status_text}
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
            dist_tp_pct = abs((target_tp - self.last_price) / self.last_price * 100)
            
            # DCA дистанция
            if self.safety_count < SAFETY_ORDERS_COUNT:
                dists, _ = self.get_dca_parameters()
                mult = self.get_smart_distance_multiplier(self.safety_count)
                target_dca = self.base_entry_price * (1 + ((dists[self.safety_count] * mult) * (-side_mult)))
                dist_dca_pct = abs((self.last_price - target_dca) / self.last_price * 100)
                dca_str = f"{dist_dca_pct:.2f}%"
            else:
                dca_str = "MAX"
            
            # Trailing status
            if self.trailing_active:
                trail_icon = "🎯"
                trail_str = f"ACTIVE @ ${self.trailing_peak_price:.2f}"
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
            if not success: self.dashboard_msg_id = None

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
                cid, mid = up['id'], up['msg_id']
                if up['value'] == "start_bot":
                    self.trading_active = True
                    self.graceful_stop_mode = False
                    self.tg.edit_message(mid, "✅ Started!", self.get_keyboard())
                elif up['value'] == "graceful_stop":
                    self.graceful_stop_mode = True
                    self.tg.edit_message(mid, "⏳ Finishing trade...", self.get_keyboard())
                    if not self.in_position: 
                        self.trading_active = False
                        self.graceful_stop_mode = False
                elif up['value'] == "cancel_stop":
                    self.graceful_stop_mode = False
                    self.tg.edit_message(mid, "✅ Continued.", self.get_keyboard())
                elif up['value'] == "panic_sell":
                    self.close_position_market("Panic Sell")
                elif up['value'] == "balance":
                    self.refresh_wallet_status()
                    self.tg.edit_message(mid, f"💵 Bal: ${self.balance:.2f}", self.get_keyboard())
                elif up['value'] == "refresh":
                    self.update_dashboard(force=True)
                elif up['value'] == "ai_report":
                    self.trigger_ai_report_thread(manual=True)
            
            # 🆕 Обработка текстовых сообщений (AI чат)
            elif up['type'] == 'text':
                text = up['value'].strip()
                if text.startswith('?') or text.startswith('/ask '):
                    q = text.lstrip('?/').replace('ask', '').strip()
                    if q:
                        self.tg.send(f"⏳ Думаю над вопросом: {q[:50]}...")
                        self.trigger_ai_chat_reply(q)

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

    def refresh_wallet_status(self, notify=False):
        """Обновление баланса"""
        try:
            bal = self.exchange.fetch_balance({'type': 'swap'})
            if 'USDT' in bal: self.balance = float(bal['USDT']['total'])
            if self.peak_balance < self.balance: self.peak_balance = self.balance
        except: pass

    def get_dynamic_tp_steps(self):
        """
        🆕 v1.3: Динамический TP от ATR в реальном времени
        Формула: Base (0.35%) + (ATR% * 0.5)
        """
        base_tp = 0.0035  # 0.35% базовый
        atr_component = 0.0  # Инициализация
        
        if self.current_volatility > 0:
            # ATR компонент (0.5x от волатильности)
            atr_component = float(self.current_volatility) * 0.5
            dynamic_tp = base_tp + atr_component
        else:
            dynamic_tp = base_tp
        
        # Ограничения: минимум 0.25%, максимум 1.0%
        dynamic_tp = max(0.0025, min(dynamic_tp, 0.010))
        
        self.log(f"🎯 Dynamic TP: {dynamic_tp*100:.2f}% (Base: {base_tp*100:.2f}%, ATR: +{atr_component*100:.3f}%)", Col.GRAY)
        
        return float(dynamic_tp)

    def get_dca_parameters(self):
        """Параметры DCA"""
        if self.is_trending_market: 
            return HAMMER_DISTANCES_TREND, HAMMER_WEIGHTS_TREND
        return HAMMER_DISTANCES_RANGE, HAMMER_WEIGHTS_RANGE

    def process_funding(self):
        """Обработка funding fee"""
        if not self.in_position or not self.last_funding_time:
            self.last_funding_time = datetime.now()
            return
        if (datetime.now() - self.last_funding_time).total_seconds() >= 8 * 3600:
            cost = (self.total_size_coins * self.avg_price) * FUNDING_RATE_8H
            self.log(f"📉 Funding estimated: -{cost:.2f}$", Col.GRAY)
            self.last_funding_time = datetime.now()

    def check_trailing_stop(self):
        """Trailing stop"""
        if not TRAILING_ENABLED or not self.in_position: return False
        current_price = self.last_price 
        side_mult = 1 if self.position_side == "Buy" else -1
        pnl_pct = (current_price - self.avg_price) / self.avg_price * side_mult
        
        if not self.trailing_active:
            if pnl_pct >= TRAILING_ACTIVATION_PCT:
                self.trailing_active = True
                self.trailing_peak_price = current_price
                self.log(f"🎯 Trailing ACTIVATED @ {current_price:.4f}", Col.CYAN)
                return False
        
        if self.trailing_active:
            if self.position_side == "Buy":
                if current_price > self.trailing_peak_price: 
                    self.trailing_peak_price = current_price
                callback = (self.trailing_peak_price - current_price) / self.trailing_peak_price
            else:
                if current_price < self.trailing_peak_price: 
                    self.trailing_peak_price = current_price
                callback = (current_price - self.trailing_peak_price) / self.trailing_peak_price
            
            if callback >= TRAILING_CALLBACK_PCT:
                self.log(f"🔔 TRAILING STOP TRIGGERED!", Col.MAGENTA)
                self.close_position_market(f"Trailing Stop (+{pnl_pct*100:.2f}%)")
                return True
        return False

    def reset_trailing(self):
        """Сброс trailing"""
        self.trailing_active = False
        self.trailing_peak_price = 0.0

    def wait_for_order_fill(self, order_id, timeout=30):
        """Ожидание исполнения ордера"""
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
        """Синхронизация позиции - УЛУЧШЕННАЯ"""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            found = False
            
            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))
                
                if amt != 0:
                    self.in_position = True
                    self.position_side = "Buy" if amt > 0 else "Sell"
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
                                if abs(position_usd - cumulative) / cumulative < 0.15:
                                    self.safety_count = i + 1
                                    self.log(f"🔄 Restored DCA level: {self.safety_count}", Col.CYAN)
                                    break
                    
                    found = True
                    self.log(f"🔄 Sync: {self.position_side} {self.total_size_coins:.4f} @ {self.avg_price:.2f}", Col.BLUE)
                    break
            
            if not found:
                self.in_position = False
                
        except Exception as e:
            self.log(f"⚠️ Sync error: {e}", Col.YELLOW)

    def open_position_limit(self, signal_data, df):
        """🚀 Открытие позиции"""
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0)) != 0:
                    self.in_position = True
                    self._sync_position_with_exchange()
                    return
        except: pass

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
                except: pass
                try: 
                    check = self.exchange.fetch_order(order['id'], self.symbol)
                    if check['status'] == 'closed':
                        final_fill_price = float(check['average'])
                        success = True
                    else: 
                        return
                except: 
                    return

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
            self.update_dashboard(force=True)

        except Exception as e:
            self.log(f"❌ Entry failed: {e}", Col.RED)
            try: 
                self.exchange.cancel_all_orders(self.symbol)
            except: pass
            self._sync_position_with_exchange()


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
            order = self.exchange.create_order(
                symbol=self.symbol,
                type='stop_market',
                side="sell" if self.position_side == "Buy" else "buy",
                amount=amount,
                params={
                    'stopPrice': price,
                    'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT',
                    'reduceOnly': True
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
        if not self.in_position:
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
                params={
                    'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT',
                    'reduceOnly': True
                }
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
        if not self.in_position:
            return False

        # Защита от множественных вызовов
        if hasattr(self, '_dca_placing') and self._dca_placing:
            return False

        self._dca_placing = True

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
            
            dists, weights = self.get_dca_parameters()
            base_dist = dists[self.safety_count]
            
            dist_multiplier = self.get_smart_distance_multiplier(self.safety_count)
            actual_dist = base_dist * dist_multiplier
            
            # 🔧 v1.3: ИСПРАВЛЕНО! DCA для SHORT теперь ВЫШЕ входа
            if self.position_side == "Buy":
                # LONG: DCA размещается НИЖЕ входа (при падении)
                dca_price = self.base_entry_price * (1 - actual_dist)
            else:
                # SHORT: DCA размещается ВЫШЕ входа (при росте)
                dca_price = self.base_entry_price * (1 + actual_dist)
            
            dca_price = float(self.exchange.price_to_precision(self.symbol, dca_price))
            
            weight = weights[self.safety_count]

            # 🆕 v1.5: Volume Factor - защита от ножей (из ultrabtc7)
            volume_factor = 1.0
            current_rsi = 50.0
            if self.current_market_df is not None:
                current_rsi = self.current_market_df['RSI'].iloc[-2]

            if self.position_side == "Buy":
                if current_rsi < 20:
                    volume_factor = 0.8  # -20% при панике
                elif current_rsi < 30:
                    volume_factor = 0.9  # -10% при сильном перепродаже
            elif self.position_side == "Sell":
                if current_rsi > 80:
                    volume_factor = 0.8  # -20% при эйфории
                elif current_rsi > 70:
                    volume_factor = 0.9  # -10% при сильной перекупленности

            first_order_usd = self.entry_usd_vol
            dca_vol_usd = first_order_usd * weight * volume_factor
            dca_vol_usd = max(dca_vol_usd, MIN_EXCHANGE_ORDER_USD)
            
            dca_size_coins = (dca_vol_usd * LEVERAGE) / dca_price
            dca_size_coins = float(self.exchange.amount_to_precision(self.symbol, dca_size_coins))
            
            # 🆕 v1.4.1: Логирование параметров
            vol_log = f", vol_factor={volume_factor:.1f}x" if volume_factor != 1.0 else ""
            self.log(f"📝 DCA{self.safety_count+1} Params: side={self.position_side.lower()}, amount={dca_size_coins}, price={dca_price:.4f}, base={self.base_entry_price:.4f}, dist={actual_dist*100:.2f}%, weight={weight}x{vol_log}", Col.GRAY)
            
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
            
            vol_suffix = f", vol x{volume_factor:.1f}" if volume_factor != 1.0 else ""
            self.log(f"✅ DCA{self.safety_count+1} placed: ID={self.dca_order_id}, Price={dca_price:.4f} (dist: {actual_dist*100:.2f}%, weight: {weight}x{vol_suffix})", Col.CYAN)
            
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
            self.avg_price = ((self.avg_price * prev_total) + (fill_price * fill_amount)) / self.total_size_coins
            
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

    def close_position_market(self, reason):
        """Закрытие позиции"""
        try:
            self.cancel_all_orders()
            
            real_amount = self.total_size_coins
            price_guess = self.last_price
            
            side_to_close = "sell" if self.position_side == "Buy" else "buy"
            amount = float(self.exchange.amount_to_precision(self.symbol, real_amount))
            
            params = {'reduceOnly': True, 'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
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

            side_mult = 1 if self.position_side == "Buy" else -1
            gross_pnl = (exec_price - self.avg_price) * real_amount * side_mult
            net_pnl = gross_pnl - self.current_trade_fees
            
            self.balance += net_pnl
            self.in_position = False

            # 🆕 v1.5: Охлаждение по PnL (из ultrabtc7)
            # Trailing Stop всегда в плюсе (активация +0.8%, откат 0.35%)
            # Поэтому проверяем по результату, а не по причине
            if net_pnl > 0:
                self.last_trade_time = datetime.now() - timedelta(hours=2)  # БЕЗ ОХЛАЖДЕНИЯ
            else:
                self.last_trade_time = datetime.now()  # С ОХЛАЖДЕНИЕМ (1 час)
            
            self.session_total_pnl += net_pnl
            self.session_total_fees += self.current_trade_fees
            if net_pnl > 0: self.session_wins += 1
            else: self.session_losses += 1
            
            try:
                with open(CSV_FILE, 'a', newline='') as f:
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
            except: pass

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
            
            if self.graceful_stop_mode:
                self.trading_active = False
                self.graceful_stop_mode = False
                self.tg.send("🛑 Stopped (Graceful)", self.get_keyboard())
            
            self.update_dashboard(force=True)
            
        except Exception as e:
            self.log(f"❌ CRITICAL CLOSE ERROR: {e}", Col.RED)

    def run(self):
        """Главный цикл"""
        last_doctor_check = 0
        last_pnl_log = 0
        
        while self.running:
            try:
                self.check_telegram_commands()
                if time.time() - self.last_dashboard_update > 15: 
                    self.update_dashboard()
                
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.last_price = float(ticker['last'])
                except: 
                    pass

                if self.has_ai:
                    now_utc = datetime.now(timezone.utc)
                    if now_utc.hour == 15 and now_utc.minute == 0 and not self.report_sent_today:
                         self.trigger_ai_report_thread(manual=False)
                         self.report_sent_today = True
                    elif now_utc.hour == 15 and now_utc.minute > 1:
                         self.report_sent_today = False

                df = self.get_market_data_enhanced()
                if df is None: 
                    time.sleep(TRAILING_UPDATE_INTERVAL)
                    continue
                
                if time.time() - last_doctor_check > 20:
                    if not self.in_position:
                         try:
                             positions = self.exchange.fetch_positions([self.symbol])
                             for pos in positions:
                                 if float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0)) != 0:
                                     self.log("🚑 Doctor: Found orphan position!", Col.MAGENTA)
                                     self._sync_position_with_exchange()
                         except: pass
                    else:
                        self.perform_health_check()
                    last_doctor_check = time.time()

                if not self.in_position:
                    signal_data = self.check_entry_signal_hybrid(df)
                    if signal_data: 
                        self.open_position_limit(signal_data, df)
                else:
                    self.process_funding()
                    
                    if time.time() - last_pnl_log > 30:
                        try:
                            side_mult = 1 if self.position_side == "Buy" else -1
                            cur_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
                            pnl_perc = (cur_pnl / self.balance) * 100 if self.balance > 0 else 0
                            self.log(f"📉 Status: PnL {cur_pnl:.2f}$ ({pnl_perc:.2f}%) | DCA: {self.safety_count}", Col.BLUE)
                            last_pnl_log = time.time()
                        except: pass

                    if TRAILING_ENABLED and self.check_trailing_stop(): 
                        continue
                    
                    try:
                        max_loss = self.get_effective_balance() * MAX_ACCOUNT_LOSS_PCT
                        side_mult = 1 if self.position_side == "Buy" else -1
                        u_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
                        
                        if u_pnl <= -max_loss:
                            self.close_position_market(f"STOP LOSS -{MAX_ACCOUNT_LOSS_PCT*100}%")
                            continue
                    except: pass

                    try:
                        open_orders = self.exchange.fetch_open_orders(self.symbol)
                        oids = [str(o['id']) for o in open_orders]  # 🆕 v1.4.1: Приведение к строкам
                        
                        if self.dca_order_id:
                             if str(self.dca_order_id) not in oids:  # 🆕 v1.4.1: Сравнение строк
                                 check = self.exchange.fetch_order(self.dca_order_id, self.symbol)
                                 if check['status'] == 'closed':
                                     self.execute_dca(float(check['average']), float(check['amount']), self.dca_order_id)
                                 elif check['status'] in ['canceled', 'rejected', 'expired']:
                                     self.log("⚠️ DCA Order Canceled! Resetting...", Col.RED)
                                     self.dca_order_id = None
                                     self.place_limit_dca()

                        if self.tp_order_id and str(self.tp_order_id) not in oids:  # 🆕 v1.4.1: Сравнение строк
                            check = self.exchange.fetch_order(self.tp_order_id, self.symbol)
                            if check['status'] == 'closed':
                                self.log("🎯 TP Executed!", Col.GREEN)
                                try: 
                                    self.exchange.cancel_order(self.dca_order_id, self.symbol)
                                except: pass
                                
                                fill_price = float(check['average'])
                                tp_fee = self.get_real_order_fee(self.tp_order_id) or (self.total_size_coins * fill_price * MAKER_FEE)
                                self.current_trade_fees += tp_fee
                                
                                side_mult = 1 if self.position_side == "Buy" else -1
                                net = ((fill_price - self.avg_price) * self.total_size_coins * side_mult) - self.current_trade_fees
                                self.balance += net
                                self.in_position = False

                                # 🆕 v1.5: Охлаждение по PnL (TP обычно в плюсе)
                                if net > 0:
                                    self.last_trade_time = datetime.now() - timedelta(hours=2)
                                else:
                                    self.last_trade_time = datetime.now()

                                self.session_total_pnl += net
                                self.session_total_fees += self.current_trade_fees
                                if net > 0: self.session_wins += 1
                                else: self.session_losses += 1
                                
                                try:
                                    with open(CSV_FILE, 'a', newline='') as f:
                                        csv.writer(f).writerow([
                                            datetime.now(), 
                                            self.symbol, 
                                            self.position_side,
                                            "TP Executed",
                                            net,
                                            self.current_trade_fees,
                                            self.avg_price,
                                            fill_price,
                                            self.safety_count,
                                            "LIMIT",
                                            self.current_volatility,
                                            self.current_confluence
                                        ])
                                except: pass
                                
                                self.log(f"🏁 TP EXIT: ${net:.2f}", Col.GREEN)
                                self.current_trade_fees = 0.0
                                self.current_confluence = 0
                                self.current_stage = 0
                                
                                if self.graceful_stop_mode:
                                    self.trading_active = False
                                    self.graceful_stop_mode = False
                                    self.tg.send("🛑 Stopped (Graceful)", self.get_keyboard())
                                
                                self.update_dashboard(force=True)
                    except Exception as e:
                        self.log(f"⚠️ Orders check error: {e}", Col.YELLOW)
                
                time.sleep(TRAILING_UPDATE_INTERVAL)
                
            except KeyboardInterrupt:
                self.log("\n⏹️  Bot stopped by user", Col.YELLOW)
                self.running = False
                break
            except Exception as e:
                self.log(f"⚠️ Main loop error: {e}", Col.RED)
                time.sleep(5)
