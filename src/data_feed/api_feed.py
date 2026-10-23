"""
External API Data Feed
Market data from Yahoo Finance / Twelve Data APIs (free tiers)
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import requests

from .base import BaseDataFeed


class APIFeed(BaseDataFeed):
    """Data feed using external free APIs"""

    # Yahoo Finance symbol mapping
    SYMBOL_MAP = {
        "XAUUSD": "GC=F",      # Gold futures
        "EURUSD": "EURUSD=X",  # EUR/USD
        "GBPUSD": "GBPUSD=X",  # GBP/USD
        "USDJPY": "USDJPY=X",  # USD/JPY
    }

    # Twelve Data symbol mapping (direct)
    TWELVE_SYMBOL_MAP = {
        "XAUUSD": "XAU/USD",
        "EURUSD": "EUR/USD",
        "GBPUSD": "GBP/USD",
    }

    # Timeframe mapping for APIs
    YAHOO_INTERVALS = {
        "M1": "1m",
        "M5": "5m",
        "M15": "15m",
        "M30": "30m",
        "H1": "1h",
        "H4": "1h",  # Yahoo doesn't have 4h
        "D1": "1d",
    }

    TWELVE_INTERVALS = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min",
        "M30": "30min",
        "H1": "1h",
        "H4": "4h",
        "D1": "1day",
    }

    def __init__(self, config):
        super().__init__(config)
        self.logger = logging.getLogger("APIFeed")
        self._provider = config.get("data_feed.api.provider", "yahoo")
        self._twelvedata_key = config.get("data_feed.api.twelvedata_api_key")
        self._rate_limit_delay = 5.0  # 5 seconds between requests (avoid rate limit)
        self._last_request_time = 0
        # Cache for data (refresh every 5 minutes)
        self._cache = {}
        self._cache_time = {}
        self._cache_ttl = 300  # 5 minutes

    def connect(self) -> bool:
        """API doesn't need persistent connection"""
        self.logger.info(f"API Feed initialized with provider: {self._provider}")
        return True

    def disconnect(self) -> None:
        """No disconnection needed for REST API"""
        pass

    def is_connected(self) -> bool:
        """Always connected for REST API"""
        return True

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def get_data(self, symbol: str, timeframe: str = "M15", bars: int = 200) -> Optional[pd.DataFrame]:
        """Get historical data from API with caching"""
        # Check cache first
        cache_key = f"{symbol}_{timeframe}"
        now = time.time()

        if cache_key in self._cache:
            if now - self._cache_time.get(cache_key, 0) < self._cache_ttl:
                self.logger.debug(f"Using cached data for {symbol}")
                return self._cache[cache_key]

        # Fetch fresh data
        self._rate_limit()

        if self._provider == "twelvedata" and self._twelvedata_key:
            df = self._get_twelvedata(symbol, timeframe, bars)
        else:
            df = self._get_yahoo(symbol, timeframe, bars)

        # Update cache
        if df is not None and not df.empty:
            self._cache[cache_key] = df
            self._cache_time[cache_key] = now
            self.logger.info(f"Cached fresh data for {symbol} ({len(df)} bars)")

        return df

    def _get_yahoo(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch from Yahoo Finance"""
        yahoo_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        interval = self.YAHOO_INTERVALS.get(timeframe, "15m")

        # Calculate date range
        end_date = datetime.now()

        # Yahoo has limits on intraday data range
        if timeframe in ["M1", "M5", "M15", "M30"]:
            # Intraday only available for last 7 days
            start_date = end_date - timedelta(days=7)
        elif timeframe == "H1":
            start_date = end_date - timedelta(days=60)
        else:
            start_date = end_date - timedelta(days=bars)

        url = "https://query1.finance.yahoo.com/v8/finance/chart/{}".format(yahoo_symbol)
        params = {
            "period1": int(start_date.timestamp()),
            "period2": int(end_date.timestamp()),
            "interval": interval,
            "includePrePost": "false",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            result = data.get("chart", {}).get("result", [])
            if not result:
                self.logger.error(f"No data from Yahoo for {symbol}")
                return None

            quote = result[0]
            timestamps = quote.get("timestamp", [])
            indicators = quote.get("indicators", {}).get("quote", [{}])[0]

            if not timestamps or not indicators:
                return None

            df = pd.DataFrame({
                "time": pd.to_datetime(timestamps, unit="s"),
                "open": indicators.get("open", []),
                "high": indicators.get("high", []),
                "low": indicators.get("low", []),
                "close": indicators.get("close", []),
                "volume": indicators.get("volume", []),
            })

            # Remove NaN rows
            df = df.dropna()

            # Get last 'bars' rows
            df = df.tail(bars).reset_index(drop=True)

            return df

        except requests.RequestException as e:
            self.logger.error(f"Yahoo API error for {symbol}: {e}")
            return None

    def _get_twelvedata(self, symbol: str, timeframe: str, bars: int) -> Optional[pd.DataFrame]:
        """Fetch from Twelve Data API"""
        if not self._twelvedata_key:
            return self._get_yahoo(symbol, timeframe, bars)

        twelve_symbol = self.TWELVE_SYMBOL_MAP.get(symbol, symbol)
        interval = self.TWELVE_INTERVALS.get(timeframe, "15min")

        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": twelve_symbol,
            "interval": interval,
            "outputsize": bars,
            "apikey": self._twelvedata_key,
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "status" in data and data["status"] == "error":
                self.logger.error(f"Twelve Data error: {data.get('message')}")
                return self._get_yahoo(symbol, timeframe, bars)

            values = data.get("values", [])
            if not values:
                return None

            df = pd.DataFrame(values)
            df = df.rename(columns={
                "datetime": "time",
                "o": "open",
                "h": "high",
                "l": "low",
                "c": "close",
                "v": "volume",
            })
            df["time"] = pd.to_datetime(df["time"])
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
            df = df.sort_values("time").reset_index(drop=True)

            return df[["time", "open", "high", "low", "close", "volume"]]

        except requests.RequestException as e:
            self.logger.error(f"Twelve Data API error: {e}")
            return self._get_yahoo(symbol, timeframe, bars)

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current price - use latest bar as approximation"""
        # Get latest 1-min bar
        df = self.get_data(symbol, "M1", 1)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1]
            # Estimate spread (can't get real spread from free API)
            return {
                "bid": float(latest["close"]),
                "ask": float(latest["close"]),
                "spread": 0,  # Unknown - will use config spread buffer
            }
        return None
