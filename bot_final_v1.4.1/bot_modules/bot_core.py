"""
🤖 BOT CORE MODULE v1.4.7
Базовый класс торгового бота с инициализацией и утилитами

ИСПРАВЛЕНИЯ v1.4.7:
- 🔥 Добавлен мониторинг SL ордера в run() (КРИТИЧЕСКИЙ БАГ!)
- 🔧 Убран дублирующий answer_callback в Telegram
- 🔒 Убран захардкоженный API ключ из config.py

КРИТИЧЕСКИЕ ИСПРАВЛЕНИЯ v1.4.5:
- 🔧 Защита от бесконечных попыток закрытия
- 🔧 Улучшенная система логирования
- 🔧 Правильная инициализация всех переменных состояния

v1.4.2:
- 🔧 Range Trailing для режима Range
- 🔧 Многоуровневая защита позиций
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


class HybridTradingBot:
    """
    Гибридный торговый бот с поддержкой:
    - Trending режим (импульсные движения)
    - Range режим (боковик)
    - AI аналитика и чат
    - Многоуровневая защита рисков
    """
    
    def __init__(self, exchange, telegram_bot):
        """
        Инициализация торгового бота
        
        Args:
            exchange: Объект биржи (ccxt)
            telegram_bot: Объект Telegram бота
        """
        # ===== ОСНОВНЫЕ КОМПОНЕНТЫ =====
        self.exchange = exchange
        self.tg = telegram_bot
        self.symbol = SYMBOL
        self.timeframe = TIMEFRAME
        
        # ===== AI МОДУЛЬ =====
        self.has_ai = HAS_AI and AI_GEMINI_KEY
        self.ai_key = AI_GEMINI_KEY
        self.ai_model_name = AI_MODEL_NAME
        self.report_sent_today = False
        
        # ===== БАЛАНС =====
        self.balance = 0.0
        self.peak_balance = 0.0
        self.start_balance = 0.0
        self.refresh_wallet_status()
        self.start_balance = self.balance
        
        # ===== ПОЗИЦИЯ =====
        self.in_position = False
        self.position_side = None  # "Buy" или "Sell"
        self.avg_price = 0.0
        self.total_size_coins = 0.0
        self.first_entry_price = 0.0
        self.base_entry_price = 0.0
        self.entry_usd_vol = 0.0
        self.safety_count = 0  # Количество DCA
        self.current_confluence = 0
        self.current_stage = 0  # Стадия входа (1, 2, 3)
        
        # ===== ОРДЕРА =====
        self.tp_order_id = None   # Take Profit ордер
        self.dca_order_id = None  # DCA (усреднение) ордер
        self.sl_order_id = None   # Stop Loss ордер
        
        # ===== ТРЕЙЛИНГ =====
        self.trailing_active = False
        self.trailing_peak_price = 0.0

        # ===== RANGE TRAILING (v1.4.2, v1.4.8) =====
        # Многоуровневая защита для Range режима
        self.range_market_type = False  # 🆕 v1.4.8: Флаг Range рынка (трейлинг активируется позже)
        self.range_trailing_enabled = False
        self.range_peak_price = 0.0
        self.last_tp_update_price = 0.0

        # ===== ЗАЩИТА ОТ ЗАВИСАНИЯ (v1.4.5) =====
        self.close_attempt_count = 0
        self.max_close_attempts = 3

        # ===== СТАТИСТИКА =====
        self.session_total_pnl = 0.0
        self.session_total_fees = 0.0
        self.session_wins = 0
        self.session_losses = 0
        self.current_trade_fees = 0.0
        self.trades_today = 0
        self.trade_start_time = None
        
        # ===== РЫНОЧНЫЕ ДАННЫЕ =====
        self.last_price = 0.0
        self.current_volatility = 0.0
        self.is_trending_market = True
        self.current_market_df = None
        self.last_trade_time = None
        self.last_funding_time = None

        # ===== УМНАЯ ЗАЩИТА DCA (v1.4.3) =====
        # Conditional Protection - адаптивная защита от просадок
        self.max_drawdown_from_entry = 0.0
        self.max_weighted_drawdown = 0.0
        self.protection_multiplier = 1.0
        self.last_danger_increase_time = None
        self.peak_volatility_during_drawdown = 0.0
        self.lowest_price_since_entry = 0.0
        self.highest_price_since_entry = 0.0
        self.price_history = []
        self.atr_history = []

        # ===== UI =====
        self.dashboard_msg_id = None
        self.trade_msg_id = None
        self.last_dashboard_update = 0
        
        # ===== КОНТРОЛЬ БОТА =====
        self.running = True
        self.trading_active = True
        self.graceful_stop_mode = False
        
        # ===== ЛОГИРОВАНИЕ =====
        logging.basicConfig(
            filename=LOG_FILE, 
            level=logging.INFO, 
            format='%(asctime)s %(message)s'
        )
        self.log("🚀 Hybrid Bot v1.4.7 Started!", Col.GREEN)
        self.log(f"💰 Starting Balance: ${self.balance:.2f}", Col.CYAN)
        if self.has_ai:
            self.log("🤖 AI Analytics & Chat: ENABLED", Col.CYAN)
        
        # ===== CSV ФАЙЛ =====
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'side', 'reason', 
                    'pnl', 'fees', 'entry', 'exit', 
                    'dca_count', 'order_type', 'volatility', 'confluence'
                ])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # УТИЛИТЫ - Базовые вспомогательные методы
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def log(self, msg, color=Col.WHITE):
        """
        Логирование с цветным выводом в консоль
        
        Args:
            msg: Сообщение для логирования
            color: Цвет текста (из config.Col)
        """
        print(f"{color}{msg}{Col.RESET}")
        logging.info(msg)
    
    def log_debug(self, msg):
        """
        Логирование отладочной информации (только в файл)
        
        Args:
            msg: Отладочное сообщение
        """
        logging.debug(msg)

    def get_effective_balance(self):
        """
        Получить эффективный баланс для торговли
        Учитывает ALLOWED_CAPITAL_PCT из config
        
        Returns:
            float: Доступный баланс для торговли
        """
        return self.balance * ALLOWED_CAPITAL_PCT

    def get_current_pnl(self):
        """
        🆕 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Получить РЕАЛЬНЫЙ PnL с биржи
        НЕ рассчитывать вручную - брать напрямую от exchange!
        
        Returns:
            float: Текущий нереализованный PnL
        """
        if not self.in_position or self.total_size_coins == 0:
            return 0.0

        try:
            positions = self.exchange.fetch_positions([self.symbol])
            for pos in positions:
                # Проверяем наличие позиции
                amt = float(pos.get('contracts', 0) or pos['info'].get('positionAmt', 0))
                if abs(amt) > 0.0001:
                    # Возвращаем unrealized PnL напрямую с биржи
                    pnl = float(pos.get('unrealizedPnl', 0))
                    return pnl
            return 0.0
        except Exception as e:
            self.log(f"⚠️ get_current_pnl error: {e}", Col.YELLOW)
            # Fallback на расчёт (может быть неточно!)
            side_mult = 1 if self.position_side == "Buy" else -1
            fallback_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
            return fallback_pnl

    def refresh_wallet_status(self, notify=False):
        """
        Обновить баланс кошелька с биржи
        
        Args:
            notify: Отправить уведомление в Telegram
        """
        try:
            bal = self.exchange.fetch_balance()
            usdt = bal.get('USDT', {})
            self.balance = float(usdt.get('free', 0)) + float(usdt.get('used', 0))
            
            if self.balance > self.peak_balance:
                self.peak_balance = self.balance
            
            if notify:
                self.log(f"💰 Balance Updated: ${self.balance:.2f}", Col.CYAN)
                
        except Exception as e:
            self.log(f"⚠️ refresh_wallet_status error: {e}", Col.YELLOW)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PLACEHOLDER - Методы будут добавлены в других модулях
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def run(self):
        """
        Основной цикл бота
        TODO: Переместить в отдельный модуль main_loop.py
        """
        raise NotImplementedError("Метод run() должен быть реализован в основном файле")
