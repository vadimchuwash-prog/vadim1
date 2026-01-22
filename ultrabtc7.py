import time
import socket
import requests.packages.urllib3.util.connection as urllib3_cn

# FORCE IPV4 GLOBALLY
def allowed_gai_family():
    return socket.AF_INET
urllib3_cn.allowed_gai_family = allowed_gai_family

_old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = _old_getaddrinfo(*args, **kwargs)
    return [r for r in responses if r[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

import logging
import pandas as pd
import ta
import sys
import os
import csv
import json
import requests
import threading
import traceback
from datetime import datetime, timedelta, timezone
from cryptography.fernet import Fernet
import ccxt

# ==========================================
# 🛡️ AI LIBRARY SAFE IMPORT
# ==========================================
HAS_AI = False
try:
    from google import genai
    HAS_AI = True
except ImportError:
    pass
except Exception as e:
    print(f"⚠️ Ошибка импорта AI: {e}")

# ==========================================
# ⚙️ CONFIG V17.5 (TERMINAL INPUT + SMART COOLDOWN)
# ==========================================

# 🔑 API KEYS - БУДУТ ЗАПРОШЕНЫ В ТЕРМИНАЛЕ
AI_GEMINI_KEY = "AIzaSyDHrTaNZo8pR55GNmYLASC3yKtx-Y1HRcU" 
AI_MODEL_NAME = "gemini-flash-latest" 
TG_BOT_TOKEN = "" # Вводится в терминале

SYMBOL = 'BTC/USDT:USDT'
TIMEFRAME = '1m'

FUNDING_RATE_8H = 0.0001 

# 💰 УПРАВЛЕНИЕ КАПИТАЛОМ
LEVERAGE = 20                
ALLOWED_CAPITAL_PCT = 1.0    # 1.0 = 100%

# 🔥 SMART ENTRY (Среднее ~2%)
MIN_ENTRY_PCT = 0.012     # 1.2%
BASE_ENTRY_PCT = 0.020    # 2.0%
MAX_ENTRY_PCT = 0.028     # 2.8%

# 🔨 СЕТКА
SAFETY_ORDERS_COUNT = 5      
MIN_EXCHANGE_ORDER_USD = 5.1 

# Дистанции
HAMMER_DISTANCES_TREND = [0.006, 0.012, 0.020, 0.030, 0.045]
HAMMER_DISTANCES_RANGE = [0.010, 0.018, 0.030, 0.045, 0.065]

# Веса
HAMMER_WEIGHTS_TREND = [1.4, 2.0, 2.8, 3.5, 4.5]
HAMMER_WEIGHTS_RANGE = [1.6, 2.2, 3.0, 4.0, 5.0]

# 🎯 ВЫХОД
TP_STEPS_HIGH_VOL = [0.0070, 0.0060, 0.0050, 0.0040, 0.0030]  
TP_STEPS_MED_VOL = [0.0060, 0.0050, 0.0040, 0.0035, 0.0030]   
TP_STEPS_LOW_VOL = [0.0050, 0.0040, 0.0035, 0.0030, 0.0025]   

# 🔄 TRAILING STOP
TRAILING_ENABLED = True           
TRAILING_ACTIVATION_PCT = 0.0080   
TRAILING_CALLBACK_PCT = 0.0035     
TRAILING_UPDATE_INTERVAL = 3       

# 🛡️ ЗАЩИТА
MAX_ACCOUNT_LOSS_PCT = 0.30    

# 📊 ФИЛЬТРЫ
QUALITY_FILTER_ENABLED = True
MIN_VOLATILITY_PCT = 0.0003    

# ⏳ ТАЙМЕР ОХЛАЖДЕНИЯ
MIN_TIME_BETWEEN_TRADES = 3600  # 1 час, если словили Stop Loss
DAILY_TRADE_LIMIT = 150        

# 💸 КОМИССИИ
MAKER_FEE = 0.0002
TAKER_FEE = 0.0005

# ФАЙЛЫ
LOG_FILE = "bot_hybrid.log"
CSV_FILE = "trades_hybrid.csv"
MARKET_LOG_FILE = "market_hybrid.csv"
SECRETS_FILE = "encrypted_config.bin"
KEY_FILE = "secret.key"

class Col:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    MAGENTA = '\033[95m'
    GRAY = '\033[90m'

# ==========================================
# 🔐 SECURITY MANAGER
# ==========================================
class SecurityManager:
    def __init__(self):
        self.key = self._load_or_create_key()
        self.cipher = Fernet(self.key)
    
    def _load_or_create_key(self):
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, "rb") as f: return f.read()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, "wb") as f: f.write(key)
            return key
    
    def save_credentials(self, api_key, secret_key, tg_token, tg_chat_id):
        data = json.dumps({"api_key": api_key, "secret_key": secret_key, "tg_token": tg_token, "tg_chat_id": tg_chat_id}).encode()
        encrypted = self.cipher.encrypt(data)
        with open(SECRETS_FILE, "wb") as f: f.write(encrypted)
    
    def load_credentials(self):
        if not os.path.exists(SECRETS_FILE): return None
        with open(SECRETS_FILE, "rb") as f: encrypted = f.read()
        try: return json.loads(self.cipher.decrypt(encrypted))
        except: return None

# ==========================================
# 📱 TELEGRAM BOT
# ==========================================
class TelegramBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.offset = 0
        self._clear_updates()
    
    def _clear_updates(self):
        try:
            updates = self.get_updates()
            if updates:
                self.offset = updates[-1]['id'] + 1
        except: pass

    def send(self, message, keyboard=None):
        if not self.token or not self.chat_id: return None
        try:
            if len(message) > 4000: message = message[:4000] + "\n..."
            payload = {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML"}
            if keyboard: payload["reply_markup"] = json.dumps(keyboard)
            resp = requests.post(f"https://api.telegram.org/bot{self.token}/sendMessage", data=payload, timeout=10)
            
            if not resp.json().get('ok'):
                print(f"❌ TG Send Error: {resp.json().get('description')}")
                return None
            return resp.json().get('result', {}).get('message_id')
        except Exception as e: 
            print(f"❌ TG Network Error: {e}")
            return None
    
    def edit_message(self, message_id, text, keyboard=None):
        if not self.token or not self.chat_id or not message_id: return False
        try:
            payload = {"chat_id": self.chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
            if keyboard: payload["reply_markup"] = json.dumps(keyboard)
            resp = requests.post(f"https://api.telegram.org/bot{self.token}/editMessageText", data=payload, timeout=10)
            return resp.json().get('ok', False)
        except: return False
    
    def get_updates(self):
        if not self.token: return []
        try:
            url = f"https://api.telegram.org/bot{self.token}/getUpdates?offset={self.offset + 1}&timeout=1"
            response = requests.get(url, timeout=5)
            data = response.json()
            if not data.get('ok'): return []
            updates = []
            for item in data.get('result', []):
                self.offset = item['update_id']
                if 'callback_query' in item:
                    cb = item['callback_query']
                    if str(cb['message']['chat']['id']) == str(self.chat_id):
                        updates.append({'type': 'callback', 'value': cb['data'], 'id': cb['id'], 'msg_id': cb['message']['message_id']})
                elif 'message' in item:
                    msg = item['message']
                    if str(msg['chat']['id']) == str(self.chat_id) and 'text' in msg:
                        updates.append({'type': 'text', 'value': msg['text'], 'msg_id': msg['message_id']})
            return updates
        except: return []

# ==========================================
# 🤖 HYBRID TRADING BOT V17.5 (STABLE)
# ==========================================
class EnhancedTradingBot:
    def __init__(self, exchange_client, tg_bot):
        self.exchange = exchange_client
        self.tg = tg_bot
        self.has_ai = HAS_AI
        self.ai_key = AI_GEMINI_KEY
        self.ai_model_name = AI_MODEL_NAME
        
        self.running = True
        self.trading_active = True 
        self.graceful_stop_mode = False 
        self.symbol = SYMBOL
        self.balance = 0.0 
        self.peak_balance = 0.0
        
        self.in_position = False
        self.position_side = None
        self.avg_price = 0.0
        self.total_size_coins = 0.0
        self.base_entry_price = 0.0
        self.entry_usd_vol = 0.0
        self.safety_count = 0
        self.trade_start_time = None
        
        self.session_wins = 0
        self.session_losses = 0
        self.session_total_pnl = 0.0
        self.session_total_fees = 0.0
        self.trades_today = 0
        
        self.trade_msg_id = None    
        self.dashboard_msg_id = None
        self.last_dashboard_update = 0
        self.tp_order_id = None
        self.dca_order_id = None
        self.report_sent_today = False
        
        self.current_volatility = 0.0
        self.is_trending_market = False
        self.current_market_df = None
        self.last_price = 0.0
        self.last_trade_time = None
        self.current_trade_fees = 0.0
        self.last_funding_time = None

        self.trailing_active = False
        self.trailing_peak_price = 0.0
        
        if not self._configure_exchange(): sys.exit()
        
        self.refresh_wallet_status(notify=False)
        self.log(f"💳 Initial Balance: ${self.balance:.2f}", Col.GREEN)
        self._sync_position_with_exchange()
        self._cleanup_stray_orders()
        
        try:
            if not os.path.exists(CSV_FILE):
                with open(CSV_FILE, 'w', newline='') as f:
                    csv.writer(f).writerow(["Date", "Symbol", "Side", "Result", "PnL", "Fee", "Entry", "Exit", "DCA_Count", "Type", "Volatility", "TrendStrength"])
            if not os.path.exists(MARKET_LOG_FILE):
                 with open(MARKET_LOG_FILE, 'w', newline='') as f:
                     f.write("Timestamp,Close,EMA9,EMA15,Slope,ATR_pct,ADX,RSI,VolumeRatio\n")
        except Exception as e:
            self.log(f"⚠️ Init File Error: {e}", Col.RED)

        eff_bal = self.get_effective_balance()
        # [FIX] Исправлена ошибка Telegram с парсингом символа <
        self.tg.send(
            f"🚀 <b>Bot V17.5 (STABLE)</b>\n"
            f"💵 Bal: ${self.balance:.2f} | Work: ${eff_bal:.2f}\n"
            f"⚙️ Config: RSI &lt; 20 -> Grid x1.6 | Vol x0.8\n"
            f"AI: {'✅ ON' if self.has_ai else '❌ OFF'}", 
            self.get_keyboard()
        )
        self.update_dashboard(force=True)

    def log(self, text, color=Col.RESET):
        t = datetime.now().strftime("%H:%M:%S")
        msg = f"[{t}] {text}"
        print(f"{color}{msg}{Col.RESET}")
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"{msg}\n")
        except: pass

    def get_effective_balance(self):
        if ALLOWED_CAPITAL_PCT > 0 and ALLOWED_CAPITAL_PCT <= 1.0:
            return self.balance * ALLOWED_CAPITAL_PCT
        return self.balance

    def wait_for_order_fill(self, order_id, timeout=30):
        start = time.time()
        while (time.time() - start) < timeout:
            try:
                order = self.exchange.fetch_order(order_id, self.symbol)
                if order['status'] == 'closed':
                    return True, float(order['average'])
                elif order['status'] in ['canceled', 'rejected']:
                    return False, None
                time.sleep(1)
            except: time.sleep(1)
        return False, None

    def _configure_exchange(self):
        self.log(f"⚙️ Configuring {LEVERAGE}x for {self.symbol}...", Col.YELLOW)
        try:
            try: self.exchange.set_margin_mode('cross', self.symbol)
            except: pass
            try:
                self.exchange.set_leverage(LEVERAGE, self.symbol, {'side': 'LONG'})
                self.exchange.set_leverage(LEVERAGE, self.symbol, {'side': 'SHORT'})
            except: self.exchange.set_leverage(LEVERAGE, self.symbol, {'side': 'BOTH'})
            return True
        except Exception as e:
            self.log(f"❌ Leverage config failed: {e}", Col.RED)
            return False

    def _sync_position_with_exchange(self):
        self.cancel_all_orders()
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            found = False
            for pos in positions:
                amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))
                if amt != 0:
                    self.in_position = True
                    self.total_size_coins = abs(amt)
                    self.position_side = "Sell" if pos['side'] == 'short' else "Buy"
                    self.avg_price = float(pos['entryPrice'])
                    self.base_entry_price = self.avg_price 
                    self.last_price = self.avg_price
                    
                    real_lev = float(pos.get('leverage', LEVERAGE))
                    self.entry_usd_vol = (self.avg_price * self.total_size_coins) / real_lev
                    
                    if not self.trade_start_time: 
                        self.trade_start_time = datetime.now()
                    
                    # [FIX] Исправлена логика определения усреднения
                    # Сравниваем с MAX_ENTRY_PCT, чтобы большие "умные входы" не считались за усреднение
                    max_base_size = (self.get_effective_balance() * MAX_ENTRY_PCT * real_lev) / self.avg_price
                    
                    if self.total_size_coins > (max_base_size * 1.1):
                        self.safety_count = max(1, self.safety_count)
                        self.log(f"🔄 Sync: Restored Safety Count to {self.safety_count}", Col.CYAN)
                    else:
                        self.safety_count = 0

                    found = True
                    self.place_limit_tp()
                    self.place_limit_dca()
                    self.log(f"🔄 Sync: Pos found {self.position_side} {self.total_size_coins} @ {self.avg_price}", Col.BLUE)
                    break
            if not found: 
                self.in_position = False
                self.trade_msg_id = None 
                self.log("🔄 Sync: No position found", Col.GRAY)
        except Exception as e: self.log(f"⚠️ Sync error: {e}", Col.RED)

    def get_market_data_enhanced(self):
        try:
            ohlcv = self.exchange.fetch_ohlcv(self.symbol, timeframe=TIMEFRAME, limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            df['EMA9'] = ta.trend.ema_indicator(df['close'], window=9)
            df['EMA15'] = ta.trend.ema_indicator(df['close'], window=15)
            df['EMA9_slope'] = df['EMA9'].pct_change(periods=5)
            
            df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            df['ATR_pct'] = df['ATR'] / df['close']
            
            adx_ind = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14)
            df['ADX'] = adx_ind.adx()
            df['RSI'] = ta.momentum.rsi(df['close'], window=14)
            df['Volume_MA'] = df['volume'].rolling(window=20).mean()
            df['Volume_ratio'] = df['volume'] / df['Volume_MA']

            self.current_volatility = df['ATR_pct'].iloc[-1] if not pd.isna(df['ATR_pct'].iloc[-1]) else 0.0025
            self.is_trending_market = (df['ADX'].iloc[-1] > 25)
            self.current_market_df = df
            
            try:
                with open(MARKET_LOG_FILE, 'a') as f:
                    row = df.iloc[-1]
                    ts_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{ts_str},{row['close']},{row['EMA9']},{row['EMA15']},{row['ATR_pct']},{row['ADX']},{row['RSI']},{row['Volume_ratio']}\n")
            except: pass
            
            return df
        except Exception as e: 
            self.log(f"Market Data Error: {e}", Col.RED)
            return None

    def calculate_smart_position_size(self, df, side):
        row = df.iloc[-2]
        score = 0
        if row['ATR_pct'] > 0.005: score -= 2
        elif row['ATR_pct'] > 0.003: score -= 1
        elif row['ATR_pct'] < 0.002: score += 1
        if row['ADX'] > 35: score += 2      
        elif row['ADX'] > 25: score += 1
        elif row['ADX'] < 20: score -= 1    

        multiplier = 1.0 + (score * 0.15)
        final_pct = BASE_ENTRY_PCT * multiplier 
        final_pct = max(MIN_ENTRY_PCT, min(final_pct, MAX_ENTRY_PCT))
        
        return final_pct

    def get_smart_distance_multiplier(self, safety_count):
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
        if not self.has_ai: return
        t = threading.Thread(target=self._generate_and_send_ai_report, args=(manual,))
        t.start()

    def _generate_and_send_ai_report(self, manual):
        try:
            import google.genai as genai
            client = genai.Client(api_key=self.ai_key)
            try:
                with open(LOG_FILE, 'r', encoding='utf-8') as f: logs = "".join(f.readlines()[-40:])
            except: logs = "Logs unavailable"

            m_info = "N/A"
            if self.current_market_df is not None:
                row = self.current_market_df.iloc[-2]
                m_info = f"Close:{row['close']}, ADX:{row['ADX']:.1f}, RSI:{row['RSI']:.1f}"
            prompt = f"Ты — AI-аналитик. Рынок: {m_info}. Логи: {logs}. Дай совет."
            response = client.models.generate_content(model=self.ai_model_name, contents=prompt)
            self.tg.send(f"🤖 <b>AI REPORT:</b>\n{response.text}")
        except: pass

    def trigger_ai_chat_reply(self, user_question):
        if not self.has_ai: return
        t = threading.Thread(target=self._generate_ai_chat_response, args=(user_question,))
        t.start()

    def _generate_ai_chat_response(self, question):
        try:
            import google.genai as genai
            client = genai.Client(api_key=self.ai_key)
            prompt = f"User: {question}. Context: Log file. Short answer."
            response = client.models.generate_content(model=self.ai_model_name, contents=prompt)
            self.tg.send(f"💬 <b>AI:</b> {response.text}")
        except: pass

    def perform_health_check(self):
        try:
            if not self.in_position: return
            if not self.tp_order_id: self.place_limit_tp()
            
            if self.safety_count < SAFETY_ORDERS_COUNT:
                if self.dca_order_id:
                    try:
                        order = self.exchange.fetch_order(self.dca_order_id, self.symbol)
                        if order['status'] in ['canceled', 'rejected']:
                            self.dca_order_id = None
                            self.place_limit_dca()
                    except:
                        self.dca_order_id = None
                        self.place_limit_dca()
                else:
                    self.place_limit_dca()
        except Exception as e:
            self.log(f"⚠️ Health Check Error: {e}", Col.YELLOW)

    def update_dashboard(self, force=False):
        now = time.time()
        if not force and (now - self.last_dashboard_update < 15): return
        self.last_dashboard_update = now
        
        status = "🟢 ON" if self.trading_active else "🔴 STOP"
        
        dist_tp, dist_dca = "---", "---"
        pnl_pct = 0.0
        
        if self.in_position:
            side_mult = 1 if self.position_side == "Buy" else -1
            unrealized = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
            margin = (self.avg_price * self.total_size_coins) / LEVERAGE
            pnl_pct = (unrealized / margin) * 100 if margin > 0 else 0
            
            tp_steps = self.get_dynamic_tp_steps()
            target_tp = self.avg_price * (1 + (tp_steps[min(self.safety_count, len(tp_steps)-1)] * side_mult))
            dist_tp = f"{abs(target_tp - self.last_price)/self.last_price*100:.2f}%"
            
            if self.safety_count < SAFETY_ORDERS_COUNT:
                dists, _ = self.get_dca_parameters()
                mult = self.get_smart_distance_multiplier(self.safety_count)
                target_dca = self.base_entry_price * (1 + ((dists[self.safety_count] * mult) * (-side_mult)))
                dist_dca = f"{abs(self.last_price - target_dca)/self.last_price*100:.2f}%"
            else: dist_dca = "MAX"

        limit_txt = f"${self.get_effective_balance():.2f}"
        
        dash = (
            f"🚀 <b>Bot V17.5 (STABLE) | {status}</b>\n"
            f"💵 Bal: ${self.balance:.2f} | Work: {limit_txt}\n"
            f"💰 PnL: {self.session_total_pnl:+.2f}$\n"
            f"💲 Price: {self.last_price:.4f} | ATR: {self.current_volatility*100:.3f}%\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
        )
        if self.in_position:
            dash += (
                f"📊 <b>{self.position_side}</b> | PnL: {pnl_pct:+.2f}%\n"
                f"🏁 TP Dist: {dist_tp} | 🧱 DCA Dist: {dist_dca}\n"
                f"🔨 DCA: {self.safety_count}/{SAFETY_ORDERS_COUNT}"
            )
        else: dash += "💤 Waiting for signal..."
        
        if not self.dashboard_msg_id: 
            self.dashboard_msg_id = self.tg.send(dash, self.get_keyboard())
        else: 
            success = self.tg.edit_message(self.dashboard_msg_id, dash, self.get_keyboard())
            if not success: self.dashboard_msg_id = None

    def get_real_order_fee(self, order_id):
        if not order_id: return 0.0
        total_fee = 0.0
        for _ in range(3):
            try:
                time.sleep(1.5)
                trades = self.exchange.fetch_my_trades(self.symbol, limit=10, params={'orderId': str(order_id)})
                for t in trades:
                    if str(t['order']) == str(order_id) and t['fee']: total_fee += float(t['fee']['cost'])
                if total_fee > 0: return total_fee
            except: pass
        return 0.0

    def send_or_update_trade_message(self, event, pnl=0.0, exit_price=None, is_final=False, calculated_fee_only=0.0):
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
        s_btn = {"text": "🛑 STOP (Graceful)", "callback_data": "graceful_stop"}
        if not self.trading_active: s_btn = {"text": "▶️ START", "callback_data": "start_bot"}
        elif self.graceful_stop_mode: s_btn = {"text": "⚠️ CANCEL STOP", "callback_data": "cancel_stop"}
        
        return {"inline_keyboard": [
            [s_btn],
            [{"text": "📊 Bal", "callback_data": "balance"}, {"text": "🧠 AI Report", "callback_data": "ai_report"}],
            [{"text": "🔄 Refresh", "callback_data": "refresh"}, {"text": "💣 Panic Sell", "callback_data": "panic_sell"}]
        ]}

    def check_telegram_commands(self):
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

            elif up['type'] == 'text':
                text = up['value'].strip()
                if text.startswith('?') or text.startswith('/ask '):
                    q = text.lstrip('?/ ').strip()
                    if q:
                        self.tg.send(f"⏳ Думаю: {q}...")
                        self.trigger_ai_chat_reply(q)

    def cancel_all_orders(self):
        try:
            if self.tp_order_id: self.exchange.cancel_order(self.tp_order_id, self.symbol)
            if self.dca_order_id: self.exchange.cancel_order(self.dca_order_id, self.symbol)
        except: pass
        self.tp_order_id = None
        self.dca_order_id = None
        try: self.exchange.cancel_all_orders(self.symbol)
        except: pass

    def _cleanup_stray_orders(self):
        try:
            orders = self.exchange.fetch_open_orders(self.symbol)
            if not orders: return
            if not self.in_position: 
                self.exchange.cancel_all_orders(self.symbol)
                return
            known = [str(self.tp_order_id), str(self.dca_order_id)]
            for o in orders:
                if str(o['id']) not in known:
                    try: self.exchange.cancel_order(o['id'], self.symbol)
                    except: pass
        except: pass

    def refresh_wallet_status(self, notify=False):
        try:
            bal = self.exchange.fetch_balance({'type': 'swap'})
            if 'USDT' in bal: self.balance = float(bal['USDT']['total'])
            if self.peak_balance < self.balance: self.peak_balance = self.balance
        except: pass

    def get_dynamic_tp_steps(self):
        if self.current_volatility > 0.004: return TP_STEPS_HIGH_VOL
        elif self.current_volatility > 0.0025: return TP_STEPS_MED_VOL
        return TP_STEPS_LOW_VOL

    def get_dca_parameters(self):
        if self.is_trending_market: return HAMMER_DISTANCES_TREND, HAMMER_WEIGHTS_TREND
        return HAMMER_DISTANCES_RANGE, HAMMER_WEIGHTS_RANGE

    def process_funding(self):
        if not self.in_position or not self.last_funding_time:
            self.last_funding_time = datetime.now(); return
        if (datetime.now() - self.last_funding_time).total_seconds() >= 8 * 3600:
            cost = (self.total_size_coins * self.avg_price) * FUNDING_RATE_8H
            self.log(f"📉 Funding estimated: -{cost:.2f}$", Col.GRAY)
            self.last_funding_time = datetime.now()

    def check_trailing_stop(self):
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
                if current_price > self.trailing_peak_price: self.trailing_peak_price = current_price
                callback = (self.trailing_peak_price - current_price) / self.trailing_peak_price
            else:
                if current_price < self.trailing_peak_price: self.trailing_peak_price = current_price
                callback = (current_price - self.trailing_peak_price) / self.trailing_peak_price
            
            if callback >= TRAILING_CALLBACK_PCT:
                self.log(f"🔔 TRAILING STOP TRIGGERED!", Col.MAGENTA)
                self.close_position_market(f"Trailing Stop (+{pnl_pct*100:.2f}%)")
                return True
        return False

    def reset_trailing(self):
        self.trailing_active = False
        self.trailing_peak_price = 0.0

    def check_entry_signal(self, df):
        if not self.trading_active or self.graceful_stop_mode: return None
        if self.trades_today >= DAILY_TRADE_LIMIT: return None
        if self.last_trade_time and (datetime.now() - self.last_trade_time).total_seconds() < MIN_TIME_BETWEEN_TRADES: 
            return None
        
        row, prev = df.iloc[-2], df.iloc[-3]
        if pd.isna(row['EMA9']): return None
        
        buy_sig = row['EMA9'] > row['EMA15']
        sell_sig = row['EMA9'] < row['EMA15']
        side = "Buy" if buy_sig else "Sell" if sell_sig else None
        
        if not side: return None
        
        ema9_change = row['EMA9'] - prev['EMA9']
        if (side == "Buy" and ema9_change < 0): return None
        if (side == "Sell" and ema9_change > 0): return None
        
        if QUALITY_FILTER_ENABLED:
            if not pd.isna(row['ATR_pct']) and row['ATR_pct'] < MIN_VOLATILITY_PCT: return None
        
        return side

    def open_position_limit(self, side, df):
        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                if float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0)) != 0:
                    self.in_position = True
                    self._sync_position_with_exchange()
                    return
        except: pass

        row = df.iloc[-2]
        self.log(f"⏳ Opening {side} (EMA9={row['EMA9']:.2f}, ATR={row['ATR_pct']:.4f})", Col.YELLOW)

        try:
            self.refresh_wallet_status()
            
            vol_pct = self.calculate_smart_position_size(df, side)
            vol_usd = max(self.get_effective_balance() * vol_pct, MIN_EXCHANGE_ORDER_USD)
            
            ticker = self.exchange.fetch_ticker(self.symbol)
            limit_price = ticker['bid'] if side == 'Buy' else ticker['ask']
            
            raw_amount = (vol_usd * LEVERAGE) / limit_price
            size_coins = float(self.exchange.amount_to_precision(self.symbol, raw_amount))
            
            self.log(f"📝 Ordering: {size_coins} coins (~{vol_usd}$) @ {limit_price}", Col.GRAY)

            order = self.exchange.create_order(
                symbol=self.symbol, type='limit', side=side.lower(), amount=size_coins, 
                price=limit_price, params={'positionSide': 'LONG' if side == 'Buy' else 'SHORT'}
            )
            
            success, final_fill_price = self.wait_for_order_fill(order['id'])
            if not success:
                self.log("⚠️ Order timed out. Cancelling...", Col.YELLOW)
                try: self.exchange.cancel_order(order['id'], self.symbol)
                except: pass
                try: 
                    check = self.exchange.fetch_order(order['id'], self.symbol)
                    if check['status'] == 'closed':
                        final_fill_price = float(check['average'])
                        success = True
                    else: return
                except: return

            self.in_position = True
            self.position_side = side
            self.avg_price = final_fill_price
            self.first_entry_price = final_fill_price
            self.base_entry_price = final_fill_price
            self.total_size_coins = size_coins
            self.entry_usd_vol = vol_usd
            self.safety_count = 0
            self.trade_start_time = datetime.now()
            self.trades_today += 1
            self.current_trade_fees = self.get_real_order_fee(order['id']) or ((size_coins * final_fill_price) * MAKER_FEE)
            
            self._sync_position_with_exchange()
            self.log(f"🟢 OPENED: {side} @ {final_fill_price:.4f}", Col.GREEN)
            self.send_or_update_trade_message("Open Position 🚀")
            self.place_limit_tp()
            self.place_limit_dca()
            self.reset_trailing()
            self.update_dashboard(force=True)

        except Exception as e:
            self.log(f"❌ Entry failed: {e}", Col.RED)
            try: self.exchange.cancel_all_orders(self.symbol)
            except: pass
            self._sync_position_with_exchange()

    def place_limit_tp(self):
        if self.tp_order_id:
            try: self.exchange.cancel_order(self.tp_order_id, self.symbol)
            except: pass
            self.tp_order_id = None
        if self.total_size_coins <= 0: return False
        try:
            side_mult = 1 if self.position_side == "Buy" else -1
            tp_steps = self.get_dynamic_tp_steps()
            tp_pct = tp_steps[min(self.safety_count, len(tp_steps) - 1)]
            price = float(self.exchange.price_to_precision(self.symbol, self.avg_price * (1 + (tp_pct * side_mult))))
            
            amount = float(self.exchange.amount_to_precision(self.symbol, self.total_size_coins))
            
            order = self.exchange.create_order(
                symbol=self.symbol, type='limit', side="sell" if self.position_side == "Buy" else "buy",
                amount=amount, price=price, params={'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
            )
            self.tp_order_id = order['id']
            return True
        except: return False

    def place_limit_dca(self):
        if self.dca_order_id:
            try: self.exchange.cancel_order(self.dca_order_id, self.symbol)
            except: pass
            self.dca_order_id = None
        if self.safety_count >= SAFETY_ORDERS_COUNT: return False
        try:
            dists, weights = self.get_dca_parameters()
            base_dist = dists[self.safety_count]
            
            dist_multiplier = self.get_smart_distance_multiplier(self.safety_count)
            actual_dist = base_dist * dist_multiplier
            
            volume_factor = 1.0
            current_rsi = 50.0
            if self.current_market_df is not None and not self.current_market_df.empty:
                current_rsi = self.current_market_df['RSI'].iloc[-2]
            
            if self.position_side == "Buy":
                if current_rsi < 20: volume_factor = 0.8
                elif current_rsi < 30: volume_factor = 0.9
            elif self.position_side == "Sell":
                if current_rsi > 80: volume_factor = 0.8
                elif current_rsi > 70: volume_factor = 0.9

            vol_usd = self.entry_usd_vol * weights[self.safety_count] * volume_factor
            
            side_mult = 1 if self.position_side == "Buy" else -1
            price = float(self.exchange.price_to_precision(self.symbol, self.base_entry_price * (1 - actual_dist * side_mult)))
            
            raw_size = (vol_usd * LEVERAGE) / price
            size = float(self.exchange.amount_to_precision(self.symbol, raw_size))
            
            order = self.exchange.create_order(
                symbol=self.symbol, type='limit', side="buy" if self.position_side == "Buy" else "sell",
                amount=size, price=price, params={'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'}
            )
            self.dca_order_id = order['id']
            
            log_suffix = f" | Vol x{volume_factor}" if volume_factor != 1.0 else ""
            self.log(f"🔨 DCA placed @ {price:.4f} (Dist: {actual_dist*100:.2f}%{log_suffix})", Col.BLUE)
            return True
        except: return False

    def execute_dca(self, price, size, order_id=None):
        self.log(f"⚡ DCA FILLED @ {price:.4f}!", Col.YELLOW)
        self.dca_order_id = None
        if self.tp_order_id:
            try: self.exchange.cancel_order(self.tp_order_id, self.symbol)
            except: pass
        
        self.current_trade_fees += (self.get_real_order_fee(order_id) or (size * price * MAKER_FEE))
        self.avg_price = ((self.total_size_coins * self.avg_price) + (size * price)) / (self.total_size_coins + size)
        self.total_size_coins += size
        self.safety_count += 1
        
        self._sync_position_with_exchange()
        self.send_or_update_trade_message(f"DCA #{self.safety_count} 🧱")
        self.place_limit_tp()
        self.place_limit_dca()
        self.update_dashboard(force=True)

    def close_position_market(self, reason="Signal"):
        if not self.in_position: return
        self.reset_trailing()
        try:
            self.exchange.cancel_all_orders(self.symbol)
            time.sleep(0.5)

            positions = self.exchange.fetch_positions([self.symbol])
            real_amount = 0.0
            for pos in positions:
                 amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))
                 if amt != 0:
                     real_amount = abs(amt)
                     self.position_side = "Sell" if pos['side'] == 'short' else "Buy" 
                     break
            
            if real_amount == 0:
                self.log("⚠️ Position already closed!", Col.YELLOW)
                self.in_position = False
                return

            self.log(f"🚨 Closing REAL amount: {real_amount} (Reason: {reason})", Col.MAGENTA)
            
            amount = float(self.exchange.amount_to_precision(self.symbol, real_amount))

            params = {
                'reduceOnly': True,
                'positionSide': 'LONG' if self.position_side == 'Buy' else 'SHORT'
            }
            
            ticker = self.exchange.fetch_ticker(self.symbol)
            price_guess = ticker['bid'] if self.position_side == 'Buy' else ticker['ask']

            order = self.exchange.create_order(
                symbol=self.symbol, 
                type='market', 
                side='sell' if self.position_side == 'Buy' else 'buy', 
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
            
            if net_pnl > 0:
                self.last_trade_time = datetime.now() - timedelta(hours=2) 
            else:
                self.last_trade_time = datetime.now()
            
            self.session_total_pnl += net_pnl
            self.session_total_fees += self.current_trade_fees
            if net_pnl > 0: self.session_wins += 1
            else: self.session_losses += 1
            
            try:
                with open(CSV_FILE, 'a', newline='') as f:
                    csv.writer(f).writerow([datetime.now(), self.symbol, self.position_side, reason, net_pnl, self.current_trade_fees, self.avg_price, exec_price, self.safety_count, "MARKET", self.current_volatility, 0])
            except: pass

            self.log(f"🏁 CLOSED: {reason} | PnL: ${net_pnl:.2f}", Col.MAGENTA)
            self.send_or_update_trade_message(f"{reason} 🏁", pnl=net_pnl, exit_price=exec_price, is_final=True, calculated_fee_only=self.current_trade_fees)
            self.current_trade_fees = 0.0
            
            if self.graceful_stop_mode:
                self.trading_active = False
                self.graceful_stop_mode = False
                self.tg.send("🛑 Stopped (Graceful)", self.get_keyboard())
            
            self.update_dashboard(force=True)
            
        except Exception as e:
            self.log(f"❌ CRITICAL CLOSE ERROR: {e}", Col.RED)

    def run(self):
        last_doctor_check = 0
        last_pnl_log = 0
        while self.running:
            try:
                self.check_telegram_commands()
                if time.time() - self.last_dashboard_update > 15: self.update_dashboard()
                
                try:
                    ticker = self.exchange.fetch_ticker(self.symbol)
                    self.last_price = float(ticker['last'])
                except: pass

                if self.has_ai:
                    now_utc = datetime.now(timezone.utc)
                    if now_utc.hour == 15 and now_utc.minute == 0 and not self.report_sent_today:
                         self.trigger_ai_report_thread(manual=False)
                         self.report_sent_today = True
                    elif now_utc.hour == 15 and now_utc.minute > 1:
                         self.report_sent_today = False

                df = self.get_market_data_enhanced()
                if df is None: 
                    time.sleep(TRAILING_UPDATE_INTERVAL); continue
                
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
                    signal = self.check_entry_signal(df)
                    if signal: self.open_position_limit(signal, df)
                else:
                    self.process_funding()
                    
                    if time.time() - last_pnl_log > 30:
                        try:
                            side_mult = 1 if self.position_side == "Buy" else -1
                            cur_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
                            pnl_perc = (cur_pnl / self.balance) * 100
                            self.log(f"📉 Status: PnL {cur_pnl:.2f}$ ({pnl_perc:.2f}%) | DCA: {self.safety_count}", Col.BLUE)
                            last_pnl_log = time.time()
                        except: pass

                    if TRAILING_ENABLED and self.check_trailing_stop(): continue
                    
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
                        oids = [o['id'] for o in open_orders]
                        
                        if self.dca_order_id:
                             if self.dca_order_id not in oids:
                                 check = self.exchange.fetch_order(self.dca_order_id, self.symbol)
                                 if check['status'] == 'closed':
                                     self.execute_dca(float(check['average']), float(check['amount']), self.dca_order_id)
                                 elif check['status'] in ['canceled', 'rejected', 'expired']:
                                     self.log("⚠️ DCA Order Canceled! Resetting...", Col.RED)
                                     self.dca_order_id = None
                                     self.place_limit_dca()

                        if self.tp_order_id and self.tp_order_id not in oids:
                            check = self.exchange.fetch_order(self.tp_order_id, self.symbol)
                            if check['status'] == 'closed':
                                self.log("🎯 TP Executed!", Col.GREEN)
                                try: self.exchange.cancel_order(self.dca_order_id, self.symbol)
                                except: pass
                                
                                fill_price = float(check['average'])
                                tp_fee = self.get_real_order_fee(self.tp_order_id) or (self.total_size_coins * fill_price * MAKER_FEE)
                                self.current_trade_fees += tp_fee
                                
                                side_mult = 1 if self.position_side == "Buy" else -1
                                net = ((fill_price - self.avg_price) * self.total_size_coins * side_mult) - self.current_trade_fees
                                self.balance += net
                                self.in_position = False
                                
                                self.last_trade_time = datetime.now() - timedelta(hours=2)

                                self.session_total_pnl += net
                                self.session_total_fees += self.current_trade_fees
                                if net > 0: self.session_wins += 1
                                else: self.session_losses += 1
                                
                                try:
                                    with open(CSV_FILE, 'a', newline='') as f:
                                        csv.writer(f).writerow([datetime.now(), self.symbol, self.position_side, "TP", net, self.current_trade_fees, self.avg_price, fill_price, self.safety_count, "LIMIT", self.current_volatility, 0])
                                except: pass
                                
                                self.send_or_update_trade_message("Take Profit 🎯", pnl=net, exit_price=fill_price, is_final=True, calculated_fee_only=self.current_trade_fees)
                                self.current_trade_fees = 0.0
                                if self.graceful_stop_mode:
                                    self.trading_active = False
                                    self.graceful_stop_mode = False
                                    self.tg.send("🛑 Stopped (Deal done)", self.get_keyboard())
                                self.update_dashboard(force=True)
                    except: pass
                
                time.sleep(TRAILING_UPDATE_INTERVAL)
            except KeyboardInterrupt: self.running = False
            except Exception as e: 
                self.log(f"💥 Error: {e}", Col.RED); 
                self.log_debug(traceback.format_exc())
                time.sleep(5)

if __name__ == "__main__":
    sec = SecurityManager()
    creds = sec.load_credentials()
    if not creds:
        print("🔑 Setup Credentials (BINGX):")
        sec.save_credentials(input("API Key: "), input("Secret Key: "), input("TG Token: "), input("TG Chat ID: "))
        creds = sec.load_credentials()
    try:
        ex = ccxt.bingx({
            'apiKey': creds['api_key'], 
            'secret': creds['secret_key'], 
            'enableRateLimit': True, 
            'timeout': 10000,
            'options': {'defaultType': 'swap'}
        })
        tg_token = creds['tg_token'] if creds['tg_token'] else TG_BOT_TOKEN
        bot = EnhancedTradingBot(ex, TelegramBot(tg_token, creds['tg_chat_id']))
        bot.run()
    except Exception as e: print(f"\n❌ Error: {e}")