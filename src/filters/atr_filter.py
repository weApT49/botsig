"""
ATR Volatility Filter
Filters signals based on ATR volatility conditions
"""

import logging
from typing import Optional
import pandas as pd
import numpy as np


class ATRFilter:
    """
    ATR-based volatility filter

    Blocks signals when:
    - ATR too low (market too quiet, likely chop)
    - ATR too high (excessive volatility, dangerous)
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("ATRFilter")

        # Settings
        self.period = config.get("atr.period", 14)
        self.min_multiplier = config.get("atr.min_atr_multiplier", 0.5)
        self.max_multiplier = config.get("atr.max_atr_multiplier", 3.0)

        # Cache for average ATR
        self._avg_atr_cache = {}

    def calculate_atr(self, df: pd.DataFrame, period: int = None) -> pd.Series:
        """Calculate ATR (Average True Range)"""
        if period is None:
            period = self.period

        high = df["high"]
        low = df["low"]
        close = df["close"]

        # True Range calculation
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR = EMA of TR
        atr = tr.ewm(span=period, adjust=False).mean()

        return atr

    def is_valid(self, df: pd.DataFrame, symbol: str = None) -> bool:
        """
        Check if current ATR is within acceptable range

        Args:
            df: OHLCV DataFrame
            symbol: Symbol name for caching

        Returns:
            True if ATR filter passes
        """
        if len(df) < self.period + 10:
            self.logger.warning("Not enough data for ATR calculation")
            return True  # Pass if not enough data

        # Calculate ATR
        atr = self.calculate_atr(df, self.period)
        current_atr = atr.iloc[-1]

        # Get historical average (last 100 bars)
        lookback = min(100, len(atr) - 1)
        avg_atr = atr.iloc[-lookback:-1].mean()

        if avg_atr == 0 or pd.isna(avg_atr):
            return True

        # Calculate ratio
        atr_ratio = current_atr / avg_atr

        # Check bounds
        if atr_ratio < self.min_multiplier:
            self.logger.info(
                f"ATR filter failed: ATR too low ({atr_ratio:.2f}x avg, min {self.min_multiplier}x)"
            )
            return False

        if atr_ratio > self.max_multiplier:
            self.logger.info(
                f"ATR filter failed: ATR too high ({atr_ratio:.2f}x avg, max {self.max_multiplier}x)"
            )
            return False

        self.logger.debug(f"ATR filter passed: {atr_ratio:.2f}x average")
        return True

    def get_atr_value(self, df: pd.DataFrame) -> Optional[float]:
        """Get current ATR value"""
        atr = self.calculate_atr(df, self.period)
        if len(atr) > 0:
            return atr.iloc[-1]
        return None

    def get_stop_loss_distance(self, df: pd.DataFrame, multiplier: float = 1.5) -> Optional[float]:
        """
        Get suggested stop loss distance based on ATR

        Args:
            df: OHLCV DataFrame
            multiplier: ATR multiplier for SL distance

        Returns:
            Suggested SL distance in price units
        """
        atr = self.get_atr_value(df)
        if atr is not None:
            return atr * multiplier
        return None
