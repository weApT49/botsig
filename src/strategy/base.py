"""
Strategy Base Class
Abstract interface for trading strategies
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for trading strategies"""

    def __init__(self, config):
        self.config = config
        self.logger = None  # Set by subclass

    @abstractmethod
    def analyze(self, symbol: str, df: pd.DataFrame, config: Dict) -> Optional[Dict]:
        """
        Analyze market data and generate signal

        Args:
            symbol: Trading symbol
            df: OHLCV DataFrame
            config: Symbol configuration

        Returns:
            Signal dict with keys:
            - symbol: str
            - direction: "BUY" or "SELL"
            - mode: "limit" or "market"
            - entry: float
            - sl: float
            - tp: float
            - rr_ratio: float
            - strategy: str
            - timeframe: str

            Or None if no signal
        """
        pass

    def validate_signal(self, signal: Dict) -> bool:
        """Validate generated signal"""
        required_keys = ["symbol", "direction", "entry", "sl", "tp"]

        for key in required_keys:
            if key not in signal:
                return False

        # Check directional logic
        if signal["direction"] == "BUY":
            if signal["sl"] >= signal["entry"]:
                return False
            if signal["tp"] <= signal["entry"]:
                return False
        elif signal["direction"] == "SELL":
            if signal["sl"] <= signal["entry"]:
                return False
            if signal["tp"] >= signal["entry"]:
                return False
        else:
            return False

        return True
