"""
🛡️ BOT PROTECTION MODULE v1.4.3
Умная защита DCA с условной активацией

Содержит:
- Расчет уровня опасности
- Проверку безопасности для возврата DCA
- Обновление множителя защиты
- Умный множитель дистанции DCA
"""

from statistics import mean
from datetime import datetime
from config import *

class BotProtectionMixin:
    """Миксин для умной защиты DCA"""
    
    def get_smart_distance_multiplier(self, safety_count):
        """🔨 ИЗ ULTRABTC7 - Умный множитель DCA"""
        BASE_ATR = 0.0020
        atr_factor = 1.0
        # 🆕 v1.4.6: БАГ #12 - Защита от деления на ноль (хотя BASE_ATR константа)
        if self.current_volatility > 0 and BASE_ATR > 0:
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

    def get_dca_parameters(self):
        """Параметры DCA"""
        if self.is_trending_market:
            return HAMMER_DISTANCES_TREND, HAMMER_WEIGHTS_TREND
        return HAMMER_DISTANCES_RANGE, HAMMER_WEIGHTS_RANGE

    def calculate_danger_level(self):
        """
        🆕 v1.4.3: Расчёт уровня опасности для просадки (0.0 - 1.0)
        Защита активируется только при реальной опасности!
        """
        danger_signals = []

        # 1. Скорость падения (за последние 5 минут)
        if len(self.price_history) >= 5:
            price_5min_ago = self.price_history[-5]
            if price_5min_ago > 0:
                speed_drop = abs((price_5min_ago - self.last_price) / price_5min_ago)

                is_adverse_move = False
                if self.position_side == "Buy" and self.last_price < price_5min_ago:
                    is_adverse_move = True
                elif self.position_side == "Sell" and self.last_price > price_5min_ago:
                    is_adverse_move = True

                if is_adverse_move and speed_drop > PROTECTION_SPEED_DROP_THRESHOLD:
                    danger_signals.append(min(speed_drop / PROTECTION_SPEED_DROP_THRESHOLD, 1.0))

        # 2. Новые экстремумы
        if self.current_market_df is not None and len(self.current_market_df) >= PROTECTION_CANDLES_LOOKBACK:
            recent_data = self.current_market_df.tail(PROTECTION_CANDLES_LOOKBACK)

            if self.position_side == "Buy":
                recent_low = recent_data['low'].min()
                if self.last_price <= recent_low * 1.0001:
                    danger_signals.append(1.0)
            else:
                recent_high = recent_data['high'].max()
                if self.last_price >= recent_high * 0.9999:
                    danger_signals.append(1.0)

        # 3. Волатильность НЕ падает
        if len(self.atr_history) >= 3:
            avg_atr = mean(self.atr_history[-3:])
            if self.current_volatility > avg_atr * PROTECTION_ATR_STABLE_RATIO:
                danger_signals.append(0.5)

        # 4. Серия однонаправленных свечей
        if self.current_market_df is not None and len(self.current_market_df) >= 5:
            last_5 = self.current_market_df.tail(5)

            if self.position_side == "Buy":
                red_candles = sum(1 for i in range(len(last_5)) if last_5['close'].iloc[i] < last_5['open'].iloc[i])
                if red_candles >= PROTECTION_DIRECTIONAL_CANDLES:
                    danger_signals.append(red_candles / 5.0)
            else:
                green_candles = sum(1 for i in range(len(last_5)) if last_5['close'].iloc[i] > last_5['open'].iloc[i])
                if green_candles >= PROTECTION_DIRECTIONAL_CANDLES:
                    danger_signals.append(green_candles / 5.0)

        # 🆕 v1.4.6: БАГ #14 - КРИТИЧНО! Проверка ПЕРЕД делением на len()
        if danger_signals:
            danger_level = sum(danger_signals) / len(danger_signals)
        else:
            danger_level = 0.0

        return danger_level

    def check_safety_for_dca_return(self):
        """
        🆕 v1.4.3: Проверка безопасности для возврата DCA ближе
        """
        checks = {
            'volatility': False,
            'time': False,
            'price_extreme': False,
            'rsi': False,
            'recovery': False
        }

        # 1. Волатильность снизилась?
        if self.peak_volatility_during_drawdown > 0:
            checks['volatility'] = self.current_volatility < (self.peak_volatility_during_drawdown * PROTECTION_VOLATILITY_RATIO)
        else:
            checks['volatility'] = True

        # 2. Прошло время?
        if self.last_danger_increase_time:
            time_elapsed = (datetime.now() - self.last_danger_increase_time).total_seconds()
            checks['time'] = time_elapsed > PROTECTION_MIN_SAFE_TIME
        else:
            checks['time'] = True

        # 3. Цена не делает новых экстремумов?
        if self.current_market_df is not None and len(self.current_market_df) >= 5:
            last_5_candles = self.current_market_df.tail(5)

            if self.position_side == "Buy":
                recent_low = last_5_candles['low'].min()
                checks['price_extreme'] = self.last_price > recent_low * 1.001
            else:
                recent_high = last_5_candles['high'].max()
                checks['price_extreme'] = self.last_price < recent_high * 0.999
        else:
            checks['price_extreme'] = True

        # 4. RSI в безопасной зоне?
        if self.current_market_df is not None and len(self.current_market_df) > 0:
            current_rsi = self.current_market_df['RSI'].iloc[-1]
            checks['rsi'] = 35 < current_rsi < 65
        else:
            checks['rsi'] = True

        # 5. Восстановление значительное?
        # 🆕 v1.4.6: БАГ #15-16 - Защита от деления на ноль
        if self.position_side == "Buy" and self.lowest_price_since_entry > 0 and self.avg_price > self.lowest_price_since_entry:
            denominator = self.avg_price - self.lowest_price_since_entry
            if denominator > 0:
                recovery_ratio = (self.last_price - self.lowest_price_since_entry) / denominator
                checks['recovery'] = recovery_ratio > PROTECTION_RECOVERY_MIN
            else:
                checks['recovery'] = True  # Если знаменатель 0, считаем безопасным
        elif self.position_side == "Sell" and self.highest_price_since_entry > 0 and self.avg_price < self.highest_price_since_entry:
            denominator = self.highest_price_since_entry - self.avg_price
            if denominator > 0:
                recovery_ratio = (self.highest_price_since_entry - self.last_price) / denominator
                checks['recovery'] = recovery_ratio > PROTECTION_RECOVERY_MIN
            else:
                checks['recovery'] = True  # Если знаменатель 0, считаем безопасным
        else:
            checks['recovery'] = True

        passed_checks = [k for k, v in checks.items() if v]
        failed_checks = [k for k, v in checks.items() if not v]
        is_safe = len(passed_checks) >= PROTECTION_MIN_CHECKS

        return {
            'is_safe': is_safe,
            'checks': checks,
            'passed': passed_checks,
            'failed': failed_checks,
            'score': f"{len(passed_checks)}/5"
        }

    def update_protection_multiplier(self):
        """
        🆕 v1.4.3: Обновление множителя защиты DCA
        """
        if not self.in_position or self.avg_price == 0:
            return

        # Обновляем историю
        self.price_history.append(self.last_price)
        if len(self.price_history) > 10:
            self.price_history.pop(0)

        self.atr_history.append(self.current_volatility)
        if len(self.atr_history) > 10:
            self.atr_history.pop(0)

        side_mult = 1 if self.position_side == "Buy" else -1
        unrealized_pct = ((self.last_price - self.avg_price) / self.avg_price) * side_mult * 100

        # Отслеживаем экстремумы
        if self.position_side == "Buy":
            if self.lowest_price_since_entry == 0 or self.last_price < self.lowest_price_since_entry:
                self.lowest_price_since_entry = self.last_price
        else:
            if self.highest_price_since_entry == 0 or self.last_price > self.highest_price_since_entry:
                self.highest_price_since_entry = self.last_price

        # УВЕЛИЧЕНИЕ ЗАЩИТЫ
        if unrealized_pct < 0:
            current_drawdown = abs(unrealized_pct)

            if current_drawdown > self.max_drawdown_from_entry:
                self.max_drawdown_from_entry = current_drawdown

            danger_level = self.calculate_danger_level()

            if danger_level > PROTECTION_DANGER_THRESHOLD:
                weighted_drawdown = current_drawdown * danger_level

                if weighted_drawdown > self.max_weighted_drawdown:
                    self.max_weighted_drawdown = weighted_drawdown
                    self.last_danger_increase_time = datetime.now()

                    if self.current_volatility > self.peak_volatility_during_drawdown:
                        self.peak_volatility_during_drawdown = self.current_volatility

                    new_multiplier = 1.0 + (weighted_drawdown * PROTECTION_AGGRESSION)

                    if new_multiplier > self.protection_multiplier:
                        self.protection_multiplier = new_multiplier
                        self.log(f"🛡️ Protection UP: {self.protection_multiplier:.2f}x", Col.YELLOW)

        # СНИЖЕНИЕ ЗАЩИТЫ
        elif self.protection_multiplier > 1.0:
            safety_checks = self.check_safety_for_dca_return()

            if safety_checks['is_safe']:
                old_mult = self.protection_multiplier
                self.protection_multiplier = max(1.0, self.protection_multiplier - PROTECTION_DECAY_RATE)

                if self.protection_multiplier < old_mult:
                    self.log(f"🔓 Protection DOWN: {self.protection_multiplier:.2f}x", Col.GREEN)
            else:
                failed = ', '.join(safety_checks['failed'])
                self.log(f"⏸️ Protection HOLD: {self.protection_multiplier:.2f}x", Col.GRAY)
