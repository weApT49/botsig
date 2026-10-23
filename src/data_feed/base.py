"""
Data Feed Base Class
Abstract interface for market data providers
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class BaseDataFeed(ABC):
    """Abstract base class for data feeds"""

    def __init__(self, config):
        self.config = config
        self.logger = None  # Set by subclass

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to data source"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to data source"""
        pass

    @abstractmethod
    def get_data(self, symbol: str, timeframe: str = "M15", bars: int = 200) -> Optional[pd.DataFrame]:
        """
        Get historical price data

        Args:
            symbol: Trading symbol (e.g., "XAUUSD")
            timeframe: Timeframe string ("M1", "M15", "H1", etc.)
            bars: Number of bars to retrieve

        Returns:
            DataFrame with columns: open, high, low, close, volume, time
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        Get current bid/ask prices

        Returns:
            Dict with 'bid', 'ask', 'spread' keys
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if data feed is connected"""
        pass

    def get_spread(self, symbol: str) -> float:
        """Get current spread for symbol"""
        prices = self.get_current_price(symbol)
        if prices:
            return prices.get("spread", 0)
        return 0

    def calculate_spread_pips(self, symbol: str, pip_value: float) -> float:
        """Calculate spread in pips"""
        spread = self.get_spread(symbol)
        if spread > 0 and pip_value > 0:
            return spread / pip_value
        return 0
