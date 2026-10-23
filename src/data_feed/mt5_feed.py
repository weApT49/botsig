"""
MT5 Data Feed
Market data from MetaTrader 5 terminal via Python API
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd

from .base import BaseDataFeed

# MT5 imports - handle gracefully if not installed
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False
    mt5 = None


class MT5Feed(BaseDataFeed):
    """Data feed using MetaTrader 5 Python API"""

    # MT5 timeframe constants
    TIMEFRAMES = {
        "M1": 1,    # mt5.TIMEFRAME_M1
        "M5": 5,    # mt5.TIMEFRAME_M5
        "M15": 15,  # mt5.TIMEFRAME_M15
        "M30": 30,  # mt5.TIMEFRAME_M30
        "H1": 60,   # mt5.TIMEFRAME_H1
        "H4": 240,  # mt5.TIMEFRAME_H4
        "D1": 1440, # mt5.TIMEFRAME_D1
    }

    def __init__(self, config):
        super().__init__(config)
        self.logger = logging.getLogger("MT5Feed")
        self._connected = False
        self._terminal_path = config.get("data_feed.mt5.terminal_path")

    def connect(self) -> bool:
        """Initialize MT5 connection"""
        if not MT5_AVAILABLE:
            self.logger.error("MetaTrader5 package not installed. Run: pip install MetaTrader5")
            return False

        # Initialize MT5
        if self._terminal_path:
            init_result = mt5.initialize(self._terminal_path)
        else:
            init_result = mt5.initialize()

        if not init_result:
            self.logger.error(f"MT5 initialize() failed: {mt5.last_error()}")
            return False

        # Login if credentials provided
        account = self.config.get("broker.account_number")
        password = self.config.get("broker.password")
        server = self.config.get("broker.server")

        if account and password and server:
            if not mt5.login(account, password, server):
                self.logger.error(f"MT5 login failed: {mt5.last_error()}")
                mt5.shutdown()
                return False
            self.logger.info(f"Logged in to MT5: {server} / {account}")

        self._connected = True
        self.logger.info("MT5 connected successfully")
        return True

    def disconnect(self) -> None:
        """Shutdown MT5 connection"""
        if MT5_AVAILABLE and self._connected:
            mt5.shutdown()
            self._connected = False
            self.logger.info("MT5 disconnected")

    def is_connected(self) -> bool:
        """Check MT5 connection status"""
        if not MT5_AVAILABLE:
            return False
        return mt5.terminal_info() is not None if self._connected else False

    def get_data(self, symbol: str, timeframe: str = "M15", bars: int = 200) -> Optional[pd.DataFrame]:
        """Get historical OHLCV data from MT5"""
        if not self._connected:
            self.logger.error("MT5 not connected")
            return None

        # Get timeframe constant
        tf_minutes = self.TIMEFRAMES.get(timeframe, 15)

        # Use mt5.TIMEFRAME_* constants
        tf_map = {
            1: mt5.TIMEFRAME_M1,
            5: mt5.TIMEFRAME_M5,
            15: mt5.TIMEFRAME_M15,
            30: mt5.TIMEFRAME_M30,
            60: mt5.TIMEFRAME_H1,
            240: mt5.TIMEFRAME_H4,
            1440: mt5.TIMEFRAME_D1,
        }
        mt5_tf = tf_map.get(tf_minutes, mt5.TIMEFRAME_M15)

        # Fetch rates
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)

        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to get data for {symbol}: {mt5.last_error()}")
            return None

        # Convert to DataFrame
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={
            "open": "open",
            "high": "high",
            "low": "low",
            "close": "close",
            "tick_volume": "volume",
            "spread": "spread"
        })

        return df[["time", "open", "high", "low", "close", "volume"]]

    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get current bid/ask from MT5"""
        if not self._connected:
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get tick for {symbol}")
            return None

        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "spread": tick.ask - tick.bid,
            "time": datetime.fromtimestamp(tick.time)
        }

    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol specifications"""
        if not self._connected:
            return None

        info = mt5.symbol_info(symbol)
        if info is None:
            return None

        return {
            "point": info.point,
            "digits": info.digits,
            "spread": info.spread,
            "trade_contract_size": info.trade_contract_size,
            "min_lot": info.volume_min,
            "max_lot": info.volume_max,
            "lot_step": info.volume_step,
        }

    def calculate_lot_size(self, symbol: str, entry: float, sl: float, risk_usc: float) -> float:
        """Calculate lot size based on risk"""
        if not self._connected:
            return 0.01

        info = self.get_symbol_info(symbol)
        if not info:
            return 0.01

        # Calculate pip value and lot
        point = info["point"]
        contract_size = info["trade_contract_size"]

        # Distance to SL in points
        sl_distance = abs(entry - sl)
        sl_points = sl_distance / point

        # For cent account: 1 lot = 1000 units
        # Risk = lot_size * sl_points * point * contract_size
        # lot_size = risk / (sl_points * point * contract_size)

        pip_value = point * contract_size  # Value per pip per lot

        if sl_points > 0 and pip_value > 0:
            lot = risk_usc / (sl_points * pip_value)
            lot = round(lot / info["lot_step"]) * info["lot_step"]
            lot = max(info["min_lot"], min(lot, info["max_lot"]))
            return lot

        return info["min_lot"]
