"""
🤖 ANALYTICS MODULE
Аналитика и логирование торговых событий

Функции:
- Black Box логирование
- PnL Audit (проверка соответствия)
- Future Spy (мониторинг закрытых позиций)
"""

import time
import json
import threading
from datetime import datetime

from config import *


class AnalyticsMixin:
    """
    Миксин для аналитики и логирования
    Добавляет методы к основному классу HybridTradingBot
    """
    
    def log_blackbox(self, event_type, data):
        """
        🆕 v1.3: BLACK BOX LOGGING
        Логирование всех ключевых событий в JSON формате
        
        Args:
            event_type: Тип события (ENTRY, EXIT, DCA, TP_UPDATE и т.д.)
            data: Словарь с данными события
        """
        try:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "event": event_type,
                "data": data
            }
            
            # Логируем в файл
            with open(BLACKBOX_LOG_FILE, 'a') as f:
                f.write(json.dumps(log_entry) + "\n")
                
        except Exception as e:
            self.log(f"⚠️ log_blackbox error: {e}", Col.YELLOW)

    def check_pnl_audit(self):
        """
        🆕 v1.4.2: PnL AUDIT - Проверка соответствия расчётов
        Сравнивает наш расчёт PnL с данными биржи
        
        ИСПРАВЛЕНО v1.4.2:
        - Учитываются комиссии
        - Порог повышен до 25% + $1
        - Меньше ложных срабатываний
        """
        if not self.in_position:
            return
        
        try:
            # PnL с биржи
            exchange_pnl = self.get_current_pnl()
            
            # Наш расчёт
            side_mult = 1 if self.position_side == "Buy" else -1
            calculated_pnl = (self.last_price - self.avg_price) * self.total_size_coins * side_mult
            
            # Разница
            diff = abs(exchange_pnl - calculated_pnl)
            
            # 🔧 ИСПРАВЛЕНО: Учитываем комиссии и повышаем порог
            fee_estimate = self.current_trade_fees
            threshold = max(abs(exchange_pnl) * 0.25, 1.0) + fee_estimate
            
            if diff > threshold:
                self.log(f"⚠️ PnL MISMATCH: Exchange=${exchange_pnl:.2f}, Calc=${calculated_pnl:.2f}, Diff=${diff:.2f}", Col.YELLOW)
                self.log_blackbox("PNL_AUDIT_MISMATCH", {
                    "exchange_pnl": exchange_pnl,
                    "calculated_pnl": calculated_pnl,
                    "difference": diff,
                    "threshold": threshold,
                    "fees": fee_estimate,
                    "avg_price": self.avg_price,
                    "last_price": self.last_price,
                    "position_size": self.total_size_coins,
                    "position_side": self.position_side
                })
                
        except Exception as e:
            self.log(f"⚠️ check_pnl_audit error: {e}", Col.YELLOW)

    def start_future_spy(self, exit_price, exit_side, exit_size):
        """
        🆕 v1.3: FUTURE SPY - Мониторинг "что было бы, если..."
        Отслеживает цену после выхода и считает упущенную прибыль
        
        Args:
            exit_price: Цена выхода
            exit_side: Сторона позиции (Buy/Sell)
            exit_size: Размер позиции
        """
        def spy_thread():
            try:
                start_time = time.time()
                max_profit = 0.0
                max_loss = 0.0
                
                while time.time() - start_time < 3600:  # 1 час
                    try:
                        ticker = self.exchange.fetch_ticker(self.symbol)
                        current_price = ticker['last']
                        
                        # Расчёт виртуального PnL
                        side_mult = 1 if exit_side == "Buy" else -1
                        virtual_pnl = (current_price - exit_price) * exit_size * side_mult
                        
                        if virtual_pnl > max_profit:
                            max_profit = virtual_pnl
                        if virtual_pnl < max_loss:
                            max_loss = virtual_pnl
                        
                        time.sleep(60)
                        
                    except:
                        break
                
                # Отчёт
                if max_profit > 5 or abs(max_loss) > 5:
                    report = f"📊 Future Spy Report (1h):\n"
                    report += f"Max Profit: ${max_profit:.2f}\n"
                    report += f"Max Loss: ${abs(max_loss):.2f}"
                    self.tg.send(report)
                    
                self.log_blackbox("FUTURE_SPY", {
                    "exit_price": exit_price,
                    "exit_side": exit_side,
                    "max_profit": max_profit,
                    "max_loss": max_loss
                })
                
            except Exception as e:
                self.log(f"⚠️ future_spy error: {e}", Col.YELLOW)
        
        threading.Thread(target=spy_thread, daemon=True).start()


# Функция для добавления миксина к основному классу
def add_analytics_methods(bot_class):
    """
    Добавляет методы аналитики к классу бота
    
    Args:
        bot_class: Класс HybridTradingBot
    """
    for method_name in dir(AnalyticsMixin):
        if not method_name.startswith('_'):
            method = getattr(AnalyticsMixin, method_name)
            if callable(method):
                setattr(bot_class, method_name, method)
