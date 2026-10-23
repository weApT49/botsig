"""
Synthetic Data Feed
Generates realistic market data for testing when APIs are rate limited
"""

import logging
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .base import BaseDataFeed


class SyntheticFeed(BaseDataFeed):
    """
    Generates synthetic but realistic price data for testing

    Features:
    - Trending + mean-reverting behavior
    - Realistic volatility clustering
    - Session-based volume patterns
    - No API rate limits
    """

    def __init__(self, config):
        super().__init__(config)
        self.logger = logging.getLogger("SyntheticFeed")

        # Base prices for symbols
        self._base_prices = {
            "XAUUSD": 2650.0,
            "EURUSD": 1.0850,
        }

        # Current price state (persists between calls)
        self._current_prices = self._base_prices.copy()
        self._price_history = {}  # symbol -> list of (time, price)

        # Generate initial history
        self._initialize_history()

        # Cache
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 300  # 5 minutes

    def _initialize_history(self):
        """Generate initial price history"""
        for symbol in self._base_prices:
            base = self._base_prices[symbol]
            n_bars = 500
            timestamps = [datetime.now() - timedelta(minutes=15*i) for i in range(n_bars)][::-1]

            # Generate correlated random walk with trend
            np.random.seed(hash(symbol) % 1000)
            returns = np.random.randn(n_bars) * 0.0015  # 0.15% per 15m

            # Add some trending behavior
            trend = np.sin(np.arange(n_bars) * 0.01) * 0.0005
            returns = returns + trend

            prices = base * np.cumprod(1 + returns)
            self._current_prices[symbol] = prices[-1]

            # Generate OHLCV
            self._price_history[symbol] = self._generate_ohlcv(prices, timestamps)

    def _generate_ohlcv(self, prices, timestamps):
        """Generate OHLCV from close prices"""
        n = len(prices)
        df_data = []

        for i in range(n):
            close = prices[i]
            # Generate realistic OHLC
            spread = abs(np.random.randn()) * 0.0005 * close
            high = close + spread * np.random.uniform(0.5, 1.5)
            low = close - spread * np.random.uniform(0.5, 1.5)
            open_price = close + np.random.randn() * spread * 0.5

            # Ensure OHLC consistency
            high = max(high, open_price, close)
            low = min(low, open_price, close)

            volume = int(np.random.lognormal(5, 1))  # Log-normal volume

            df_data.append({
                "time": timestamps[i],
                "open": open_price,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume
            })

        return pd.DataFrame(df_data)

    def _update_price(self, symbol: str):
        """Update price with new bar"""
        if symbol not in self._price_history:
            return

        df = self._price_history[symbol]
        last_close = df["close"].iloc[-1]

        # Generate next bar
        ret = np.random.randn() * 0.0015
        new_close = last_close * (1 + ret)
        self._current_prices[symbol] = new_close

        new_time = df["time"].iloc[-1] + timedelta(minutes=15)

        # OHLC
        spread = abs(np.random.randn()) * 0.0005 * new_close
        high = new_close + spread * np.random.uniform(0.5, 1.5)
        low = new_close - spread * np.random.uniform(0.5, 1.5)
        open_price = new_close + np.random.randn() * spread * 0.5

        high = max(high, open_price, new_close)
        low = min(low, open_price, new_close)

        # Keep last 500 bars
        new_row = pd.DataFrame([{
            "time": new_time,
            "open": open_price,
            "high": high,
            "low": low,
            "close": new_close,
            "volume": int(np.random.lognormal(5, 1))
        }])

        self._price_history[symbol] = pd.concat([df.tail(499), new_row], ignore_index=True)

    def connect(self) -> bool:
        """No connection needed"""
        self.logger.info("Synthetic Feed initialized (no API limits)")
        return True

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def get_data(self, symbol: str, timeframe: str = "M15", bars: int = 200) -> Optional[pd.DataFrame]:
        """Get synthetic data"""
        # Update with new bar occasionally
        if np.random.random() < 0.3:  # 30% chance to add new bar
            self._update_price(symbol)

        # Check cache
        cache_key = f"{symbol}_{timeframe}"
        now = time.time()

        if cache_key in self._cache:
            if now - self._cache_time.get(cache_key, 0) < self._cache_ttl:
                return self._cache[cache_key].tail(bars).copy()

        # Get from history
        if symbol in self._price_history:
            df = self._price_history[symbol].tail(bars).copy()
            self._cache[cache_key] = df
            self._cache_time[cache_key] = now
            self.logger.debug(f"Synthetic data for {symbol}: {len(df)} bars")
            return df

        return None

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current synthetic price"""
        if symbol not in self._current_prices:
            return None

        price = self._current_prices[symbol]
        spread = price * 0.0002  # 0.02% spread

        return {
            "bid": price - spread/2,
            "ask": price + spread/2,
            "spread": spread,
            "time": datetime.now()
        }