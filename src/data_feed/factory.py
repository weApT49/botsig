"""
Data Feed Factory
Creates appropriate data feed based on configuration
"""

from typing import Optional
from .base import BaseDataFeed
from .mt5_feed import MT5Feed
from .api_feed import APIFeed
from .synthetic_feed import SyntheticFeed


class DataFeedFactory:
    """Factory for creating data feed instances"""

    @staticmethod
    def create(config, mode: Optional[str] = None) -> BaseDataFeed:
        """
        Create data feed based on configuration mode

        Args:
            config: Configuration object
            mode: Override mode ("mt5", "api", or "synthetic"), uses config default if None

        Returns:
            DataFeed instance
        """
        if mode is None:
            mode = config.get("data_feed.default_mode", "api")

        if mode == "mt5":
            return MT5Feed(config)
        elif mode == "api":
            return APIFeed(config)
        elif mode == "synthetic":
            return SyntheticFeed(config)
        else:
            raise ValueError(f"Unknown data feed mode: {mode}")
