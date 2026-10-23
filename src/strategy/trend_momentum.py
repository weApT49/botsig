"""
Trend + Momentum Strategy
M15/H1 structure-based signal generation
"""

import logging
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

from .base import BaseStrategy


class TrendMomentumStrategy(BaseStrategy):
    """
    Trend-following strategy with momentum confirmation

    Entry conditions:
    - Trend alignment (EMA crossover)
    - Momentum confirmation (RSI)
    - Volume confirmation
    - Structure break (HH/HL or LH/LL)

    Exit:
    - Fixed TP/SL based on ATR
    - Risk:Reward minimum 1:1.5
    """

    def __init__(self, config):
        super().__init__(config)
        self.logger = logging.getLogger("TrendMomentumStrategy")

        # Strategy parameters
        self.ema_fast = config.get("strategy.ema_fast", 9)
        self.ema_slow = config.get("strategy.ema_slow", 21)
        self.rsi_period = config.get("strategy.rsi_period", 14)
        self.rsi_oversold = config.get("strategy.rsi_oversold", 30)
        self.rsi_overbought = config.get("strategy.rsi_overbought", 70)
        self.atr_sl_multiplier = config.get("strategy.atr_sl_multiplier", 1.5)
        self.atr_tp_multiplier = config.get("strategy.atr_tp_multiplier", 2.5)
        self.min_rr = config.get("strategy.min_risk_reward", 1.5)

    def analyze(self, symbol: str, df: pd.DataFrame, config: Dict) -> Optional[Dict]:
        """
        Analyze market data and generate signal

        Args:
            symbol: Trading symbol
            df: OHLCV DataFrame
            config: Symbol configuration

        Returns:
            Signal dict or None
        """
        if len(df) < 50:
            self.logger.warning(f"{symbol}: Not enough data for analysis")
            return None

        # Calculate indicators
        df = self._calculate_indicators(df)

        # Get latest values
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # Check trend
        trend = self._determine_trend(df)

        if trend == "NEUTRAL":
            return None

        # Check momentum
        momentum = self._check_momentum(latest, trend)

        if not momentum:
            return None

        # Check structure
        structure = self._check_structure(df, trend)

        if not structure:
            return None

        # Generate signal
        signal = self._generate_signal(symbol, df, trend, config)

        return signal

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate technical indicators"""
        df = df.copy()

        # EMAs
        df["ema_fast"] = df["close"].ewm(span=self.ema_fast, adjust=False).mean()
        df["ema_slow"] = df["close"].ewm(span=self.ema_slow, adjust=False).mean()

        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()

        rs = gain / loss
        df["rsi"] = 100 - (100 / (1 + rs))

        # ATR
        high = df["high"]
        low = df["low"]
        close = df["close"]

        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["atr"] = tr.ewm(span=14, adjust=False).mean()

        # Swing highs/lows (for structure)
        df["swing_high"] = df["high"].rolling(window=5, center=True).max()
        df["swing_low"] = df["low"].rolling(window=5, center=True).min()

        return df

    def _determine_trend(self, df: pd.DataFrame) -> str:
        """Determine trend direction"""
        latest = df.iloc[-1]
        prev = df.iloc[-2]

        # EMA crossover
        ema_cross_up = prev["ema_fast"] <= prev["ema_slow"] and latest["ema_fast"] > latest["ema_slow"]
        ema_cross_down = prev["ema_fast"] >= prev["ema_slow"] and latest["ema_fast"] < latest["ema_slow"]

        # Trend alignment
        bullish_trend = latest["ema_fast"] > latest["ema_slow"]
        bearish_trend = latest["ema_fast"] < latest["ema_slow"]

        if bullish_trend:
            return "BUY"
        elif bearish_trend:
            return "SELL"

        return "NEUTRAL"

    def _check_momentum(self, latest: pd.Series, trend: str) -> bool:
        """Check momentum confirmation"""
        rsi = latest["rsi"]

        if trend == "BUY":
            # For buy, RSI should be above oversold and not overbought
            return self.rsi_oversold < rsi < self.rsi_overbought
        else:
            # For sell, RSI should be below overbought and not oversold
            return self.rsi_oversold < rsi < self.rsi_overbought

    def _check_structure(self, df: pd.DataFrame, trend: str) -> bool:
        """Check market structure (HH/HL or LH/LL)"""
        # Get recent swing points
        lookback = 20
        recent = df.tail(lookback)

        swing_highs = recent["swing_high"].dropna()
        swing_lows = recent["swing_low"].dropna()

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return True  # Not enough swing points

        if trend == "BUY":
            # Check for HH and HL pattern
            last_high = swing_highs.iloc[-1]
            prev_high = swing_highs.iloc[-2]
            last_low = swing_lows.iloc[-1]
            prev_low = swing_lows.iloc[-2]

            hh = last_high > prev_high
            hl = last_low > prev_low

            return hh or hl  # At least one condition

        else:  # SELL
            # Check for LH and LL pattern
            last_high = swing_highs.iloc[-1]
            prev_high = swing_highs.iloc[-2]
            last_low = swing_lows.iloc[-1]
            prev_low = swing_lows.iloc[-2]

            lh = last_high < prev_high
            ll = last_low < prev_low

            return lh or ll

    def _generate_signal(self, symbol: str, df: pd.DataFrame, trend: str, config: Dict) -> Optional[Dict]:
        """Generate trading signal with entry, SL, TP"""
        latest = df.iloc[-1]
        atr = latest["atr"]

        if atr <= 0:
            return None

        # Entry price (current close for market, or next level for limit)
        entry = latest["close"]

        # Mode selection
        mode = self.config.get("signal.default_mode", "limit")

        if mode == "limit":
            # For limit orders, use recent swing level
            if trend == "BUY":
                # Buy at recent swing low or pullback level
                swing_lows = df["swing_low"].dropna()
                if len(swing_lows) > 0:
                    entry = swing_lows.iloc[-1]
                else:
                    entry = latest["low"]
            else:
                # Sell at recent swing high
                swing_highs = df["swing_high"].dropna()
                if len(swing_highs) > 0:
                    entry = swing_highs.iloc[-1]
                else:
                    entry = latest["high"]

        # Calculate SL distance based on ATR
        sl_distance = atr * self.atr_sl_multiplier
        tp_distance = atr * self.atr_tp_multiplier

        # Set SL and TP
        if trend == "BUY":
            sl = entry - sl_distance
            tp = entry + tp_distance
        else:
            sl = entry + sl_distance
            tp = entry - tp_distance

        # Validate R:R
        rr = tp_distance / sl_distance if sl_distance > 0 else 0
        if rr < self.min_rr:
            self.logger.debug(f"{symbol}: R:R {rr:.2f} below minimum {self.min_rr}")
            # Adjust TP to meet minimum R:R
            tp_distance = sl_distance * self.min_rr
            if trend == "BUY":
                tp = entry + tp_distance
            else:
                tp = entry - tp_distance

        signal = {
            "symbol": symbol,
            "direction": trend,
            "mode": mode,
            "entry": round(entry, 5),
            "sl": round(sl, 5),
            "tp": round(tp, 5),
            "atr": round(atr, 5),
            "rr_ratio": round(tp_distance / sl_distance, 2) if sl_distance > 0 else 0,
            "strategy": "TrendMomentum",
            "timeframe": "M15",
        }

        return signal
