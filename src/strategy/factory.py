"""
Strategy Factory
Creates strategy instances based on configuration
"""

from typing import Optional
from .base import BaseStrategy
from .trend_momentum import TrendMomentumStrategy


class StrategyFactory:
    """Factory for creating strategy instances"""

    # Available strategies
    STRATEGIES = {
        "trend_momentum": TrendMomentumStrategy,
        "default": TrendMomentumStrategy,
    }

    @staticmethod
    def create(config, strategy_name: Optional[str] = None) -> BaseStrategy:
        """
        Create strategy instance

        Args:
            config: Configuration object
            strategy_name: Strategy name (uses config default if None)

        Returns:
            Strategy instance
        """
        if strategy_name is None:
            strategy_name = config.get("strategy.name", "default")

        strategy_class = StrategyFactory.STRATEGIES.get(strategy_name)

        if strategy_class is None:
            raise ValueError(f"Unknown strategy: {strategy_name}")

        return strategy_class(config)
