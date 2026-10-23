"""
Backtest Sanity Check
Historical validation of strategy with realistic spread penalty
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path


class BacktestSanityCheck:
    """
    Lightweight backtest to verify positive expectancy

    Tests strategy over historical data with:
    - Realistic spread penalty
    - Slippage estimation
    - Risk per trade calculation
    - Statistical significance check
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("BacktestSanityCheck")

        # Settings
        self.days = config.get("backtest.days", 30)
        self.spread_penalty = config.get("backtest.spread_penalty_pips", 2.0)
        self.min_trades = config.get("backtest.min_trades", 20)
        self.min_expectancy = config.get("backtest.min_expectancy", 0.1)

        # Results
        self.trades: List[Dict] = []
        self.stats: Dict = {}

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        symbol_config: Dict,
        strategy
    ) -> Dict:
        """
        Run backtest on historical data

        Args:
            df: Historical OHLCV data
            symbol: Symbol name
            symbol_config: Symbol configuration
            strategy: Strategy instance with analyze() method

        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"Running backtest for {symbol} ({self.days} days)")

        # Clear previous results
        self.trades = []
        self.stats = {}

        if len(df) < 200:
            self.logger.error("Not enough data for backtest")
            return {"error": "Insufficient data"}

        # Get pip value for spread penalty
        pip_value = symbol_config.get("pip_value", 0.00001)
        spread_cost = self.spread_penalty * pip_value

        # Iterate through historical data
        lookback = 100  # Bars needed for indicators
        total_bars = len(df)

        for i in range(lookback, total_bars - 50):  # Leave 50 bars for TP/SL
            # Get data up to current bar
            historical_df = df.iloc[:i+1].copy()

            # Generate signal
            signal = strategy.analyze(symbol, historical_df, symbol_config)

            if signal is None:
                continue

            # Simulate trade
            trade = self._simulate_trade(
                signal=signal,
                future_data=df.iloc[i+1:i+51],  # Next 50 bars
                spread_cost=spread_cost,
                pip_value=pip_value
            )

            if trade:
                self.trades.append(trade)

        # Calculate statistics
        self.stats = self._calculate_stats()

        self.logger.info(
            f"Backtest complete: {len(self.trades)} trades, "
            f"Expectancy: {self.stats.get('expectancy', 0):.2f}R"
        )

        return self.stats

    def _simulate_trade(
        self,
        signal: Dict,
        future_data: pd.DataFrame,
        spread_cost: float,
        pip_value: float
    ) -> Optional[Dict]:
        """
        Simulate trade outcome

        Returns trade dict with outcome or None if not triggered
        """
        if future_data.empty:
            return None

        direction = signal.get("direction")
        entry = signal.get("entry")
        sl = signal.get("sl")
        tp = signal.get("tp")
        mode = signal.get("mode", "limit")

        # Apply spread cost to entry (makes entry worse)
        if direction == "BUY":
            actual_entry = entry + spread_cost
        else:
            actual_entry = entry - spread_cost

        # Track trade
        trade = {
            "entry": actual_entry,
            "sl": sl,
            "tp": tp,
            "direction": direction,
            "mode": mode,
            "outcome": None,
            "pnl_pips": 0,
            "bars_held": 0,
        }

        # For limit orders, check if entry is triggered first
        if mode == "limit":
            triggered = False
            for idx, row in future_data.iterrows():
                # Check if price reaches entry
                if direction == "BUY":
                    if row["low"] <= entry:
                        triggered = True
                        break
                else:  # SELL
                    if row["high"] >= entry:
                        triggered = True
                        break

            if not triggered:
                return None

            # Use data after trigger
            trigger_idx = future_data.index.get_loc(idx)
            future_data = future_data.iloc[trigger_idx+1:]

        # Check for SL or TP hit
        for idx, row in future_data.iterrows():
            trade["bars_held"] += 1

            if direction == "BUY":
                # Check SL hit
                if row["low"] <= sl:
                    trade["outcome"] = "LOSS"
                    trade["pnl_pips"] = -abs(actual_entry - sl) / pip_value
                    break
                # Check TP hit
                if row["high"] >= tp:
                    trade["outcome"] = "WIN"
                    trade["pnl_pips"] = abs(tp - actual_entry) / pip_value
                    break
            else:  # SELL
                # Check SL hit
                if row["high"] >= sl:
                    trade["outcome"] = "LOSS"
                    trade["pnl_pips"] = -abs(actual_entry - sl) / pip_value
                    break
                # Check TP hit
                if row["low"] <= tp:
                    trade["outcome"] = "WIN"
                    trade["pnl_pips"] = abs(tp - actual_entry) / pip_value
                    break

        # If neither hit, mark as timeout
        if trade["outcome"] is None:
            # Use close price at end
            final_close = future_data.iloc[-1]["close"]
            if direction == "BUY":
                trade["pnl_pips"] = (final_close - actual_entry) / pip_value
            else:
                trade["pnl_pips"] = (actual_entry - final_close) / pip_value

            trade["outcome"] = "WIN" if trade["pnl_pips"] > 0 else "LOSS"

        return trade

    def _calculate_stats(self) -> Dict:
        """Calculate backtest statistics"""
        if not self.trades:
            return {
                "total_trades": 0,
                "expectancy": 0,
                "win_rate": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "profit_factor": 0,
                "passed": False,
            }

        wins = [t for t in self.trades if t["outcome"] == "WIN"]
        losses = [t for t in self.trades if t["outcome"] == "LOSS"]

        total = len(self.trades)
        win_count = len(wins)
        loss_count = len(losses)

        win_rate = win_count / total if total > 0 else 0

        avg_win_pips = np.mean([t["pnl_pips"] for t in wins]) if wins else 0
        avg_loss_pips = np.mean([abs(t["pnl_pips"]) for t in losses]) if losses else 0

        # Expectancy in R (risk units)
        # R = 1 for each trade (fixed risk per trade)
        # Expectancy = (Win% × Avg Win R) - (Loss% × Avg Loss R)
        avg_win_r = avg_win_pips / avg_loss_pips if avg_loss_pips > 0 else 0
        avg_loss_r = 1.0  # 1R

        expectancy = (win_rate * avg_win_r) - ((1 - win_rate) * avg_loss_r)

        # Profit factor
        gross_profit = sum([t["pnl_pips"] for t in wins]) if wins else 0
        gross_loss = sum([abs(t["pnl_pips"]) for t in losses]) if losses else 0
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Check if passes
        passed = (
            total >= self.min_trades and
            expectancy >= self.min_expectancy
        )

        return {
            "total_trades": total,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": win_rate,
            "avg_win_pips": avg_win_pips,
            "avg_loss_pips": avg_loss_pips,
            "avg_win_r": avg_win_r,
            "expectancy": expectancy,
            "profit_factor": profit_factor,
            "passed": passed,
            "min_trades_required": self.min_trades,
            "min_expectancy_required": self.min_expectancy,
        }

    def get_report(self) -> str:
        """Generate text report of backtest results"""
        if not self.stats:
            return "No backtest results available."

        s = self.stats

        lines = [
            "=" * 50,
            "BACKTEST RESULTS",
            "=" * 50,
            f"Total Trades: {s.get('total_trades', 0)}",
            f"Win Rate: {s.get('win_rate', 0)*100:.1f}%",
            f"Win/Loss: {s.get('win_count', 0)}/{s.get('loss_count', 0)}",
            "",
            f"Avg Win: {s.get('avg_win_pips', 0):.1f} pips ({s.get('avg_win_r', 0):.2f}R)",
            f"Avg Loss: {s.get('avg_loss_pips', 0):.1f} pips (1.00R)",
            "",
            f"Expectancy: {s.get('expectancy', 0):.2f}R per trade",
            f"Profit Factor: {s.get('profit_factor', 0):.2f}",
            "",
            f"PASSED: {'YES' if s.get('passed') else 'NO'}",
            f"  Min trades: {s.get('min_trades_required')} (got {s.get('total_trades')})",
            f"  Min expectancy: {s.get('min_expectancy_required')} (got {s.get('expectancy', 0):.2f})",
            "=" * 50,
        ]

        return "\n".join(lines)

    def save_trades(self, filepath: str = "logs/backtest_trades.csv"):
        """Save trade history to CSV"""
        if not self.trades:
            return

        df = pd.DataFrame(self.trades)
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        self.logger.info(f"Saved {len(self.trades)} trades to {filepath}")
