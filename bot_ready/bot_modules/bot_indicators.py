"""
🔍 BOT INDICATORS MODULE v1.0
Модуль индикаторов и анализа рынка

Содержит:
- Получение и расчет рыночных данных с индикаторами
- Расчет confluence score для оценки качества сигнала
- Гибридная система проверки входных сигналов
- Расчет размера позиции в зависимости от стадии и рынка
- Динамические take-profit уровни на основе волатильности
"""

import pandas as pd
import ta
from datetime import datetime
from config import (
    DAILY_TRADE_LIMIT,
    MIN_TIME_BETWEEN_TRADES,
    QUALITY_FILTER_ENABLED,
    MIN_VOLATILITY_PCT,
    RSI_SAFE_MIN,
    RSI_SAFE_MAX,
    MIN_VOLUME_RATIO,
    MIN_MICROTREND_CANDLES,
    KNIFE_PROTECTION_PCT,
    MIN_CONFLUENCE_SCORE,
    STAGE1_MIN_ENTRY,
    STAGE1_BASE_ENTRY,
    STAGE1_MAX_ENTRY,
    STAGE2_MIN_ENTRY,
    STAGE2_BASE_ENTRY,
    STAGE2_MAX_ENTRY,
    STAGE3_MIN_ENTRY,
    STAGE3_BASE_ENTRY,
    STAGE3_MAX_ENTRY,
    TP_STEPS_HIGH_VOL,
    TP_STEPS_MED_VOL,
    TP_STEPS_LOW_VOL
)
from config import Col


class BotIndicatorsMixin:
    """
    Mixin класс для работы с индикаторами и анализом рынка
    
    Требуемые атрибуты в основном классе:
    - self.exchange: объект биржи для получения данных
    - self.symbol: торговая пара
    - self.timeframe: таймфрейм для анализа
    - self.trading_active: флаг активности торговли
    - self.graceful_stop_mode: флаг режима graceful stop
    - self.trades_today: количество сделок за сегодня
    - self.last_trade_time: время последней сделки
    - self.current_volatility: текущая волатильность (ATR%)
    - self.is_trending_market: флаг трендового рынка
    - self.current_market_df: текущий DataFrame с рыночными данными
    - self.log(): метод логирования
    """
    
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
        # 🆕 v1.4.6: БАГ #1 - Защита от деления на ноль
        volume_ratio = 0
        mean_vol = df['volume'].iloc[-20:].mean()
        if mean_vol > 0:
            volume_ratio = row['volume'] / mean_vol
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
        # 🆕 v1.4.6: БАГ #2 - Защита от деления на ноль
        mean_vol = df['volume'].iloc[-20:].mean()
        if mean_vol > 0:
            volume_ratio = row['volume'] / mean_vol
            if volume_ratio < MIN_VOLUME_RATIO:
                return None
        else:
            return None  # Нет данных по объёму
        
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
        # 🆕 v1.4.6: БАГ #3 - Защита от деления на ноль
        price_change_3 = 0
        price_3_candles_ago = df.iloc[-4]['close']
        if price_3_candles_ago > 0:
            price_change_3 = (row['close'] - price_3_candles_ago) / price_3_candles_ago
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

    def get_dynamic_tp_steps(self):
        """
        v1.5.1: Динамический TP от волатильности + уровня DCA

        Использует TP_STEPS массивы из config (3 уровня волатильности × 4 уровня DCA)
        + ATR компонент для точной адаптации

        Returns:
            float: TP distance (например 0.0055 = 0.55%)
        """
        # 1. Выбираем массив по волатильности
        vol = self.current_volatility
        if vol > 0.004:
            tp_steps = TP_STEPS_HIGH_VOL
            vol_label = "HIGH"
        elif vol > 0.0025:
            tp_steps = TP_STEPS_MED_VOL
            vol_label = "MED"
        else:
            tp_steps = TP_STEPS_LOW_VOL
            vol_label = "LOW"

        # 2. Выбираем TP по уровню DCA (safety_count)
        dca_idx = min(getattr(self, 'safety_count', 0), len(tp_steps) - 1)
        base_tp = tp_steps[dca_idx]

        # 3. ATR микро-подстройка (±15% от базового)
        atr_adjust = 0.0
        if vol > 0:
            BASE_ATR = 0.0020
            atr_ratio = vol / BASE_ATR
            atr_adjust = base_tp * (atr_ratio - 1.0) * 0.15
            atr_adjust = max(-base_tp * 0.15, min(atr_adjust, base_tp * 0.15))

        dynamic_tp = base_tp + atr_adjust

        # 4. Для flip-позиций: расширенный TP (едем по тренду)
        if getattr(self, 'is_flip_position', False):
            try:
                from config import FLIP_TP_MULTIPLIER
                dynamic_tp *= FLIP_TP_MULTIPLIER
            except ImportError:
                dynamic_tp *= 1.5

        # 5. Ограничения: минимум 0.20%, максимум 1.0%
        dynamic_tp = max(0.0020, min(dynamic_tp, 0.010))

        self.log(f"🎯 TP: {dynamic_tp*100:.2f}% (Vol:{vol_label}, DCA:{dca_idx}, Base:{base_tp*100:.2f}%)", Col.GRAY)

        return float(dynamic_tp)
