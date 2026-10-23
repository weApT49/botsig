"""
Risk Manager
Orchestrates position sizing and risk controls
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .position_sizer import PositionSizer
from .circuit_breaker import CircuitBreaker


class RiskManager:
    """
    Risk management orchestrator

    Responsibilities:
    - Position sizing
    - Daily risk limits
    - Signal validation
    - Trade logging
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("RiskManager")

        # Components
        self.position_sizer = PositionSizer(config)
        self.circuit_breaker = CircuitBreaker(config)

        # State
        self._daily_trades: Dict[str, int] = {}  # symbol -> count
        self._signal_history: list = []

    def apply(self, signal: Dict, symbol_config: Dict) -> Optional[Dict]:
        """
        Apply risk management to signal

        Args:
            signal: Raw signal with entry, sl, tp, direction
            symbol_config: Symbol configuration

        Returns:
            Signal with lot size and risk parameters, or None if rejected
        """
        # Check circuit breaker
        if self.circuit_breaker.is_locked():
            self.logger.warning(
                f"Signal rejected: Circuit breaker locked - {self.circuit_breaker.get_lock_reason()}"
            )
            return None

        # Check daily trade limit per symbol
        symbol = signal.get("symbol", symbol_config.get("name"))
        max_trades_per_symbol = self.config.get("risk.max_trades_per_symbol_per_day", 3)

        if self._daily_trades.get(symbol, 0) >= max_trades_per_symbol:
            self.logger.warning(f"Signal rejected: Max trades reached for {symbol}")
            return None

        # Validate signal values
        if not self._validate_signal(signal):
            return None

        # Calculate lot size
        # Note: symbol_info should come from data feed, using config as fallback
        symbol_info = self._get_symbol_info(symbol_config)

        lot = self.position_sizer.calculate(
            entry=signal["entry"],
            sl=signal["sl"],
            symbol_info=symbol_info,
            risk_pct=self.config.get("risk.risk_per_trade_pct")
        )

        signal["lot"] = lot

        # Calculate risk metrics
        risk_usc = self.position_sizer.calculate_risk_usc(
            lot=lot,
            entry=signal["entry"],
            sl=signal["sl"],
            symbol_info=symbol_info
        )
        signal["risk_usc"] = risk_usc
        signal["risk_pct"] = (risk_usc / self.config.get("risk.capital_usc", 5500)) * 100

        # Validate risk
        max_risk_pct = self.config.get("risk.max_risk_per_trade_pct", 1.5)
        if signal["risk_pct"] > max_risk_pct:
            self.logger.warning(
                f"Signal rejected: Risk {signal['risk_pct']:.2f}% exceeds max {max_risk_pct}%"
            )
            return None

        # Add timestamp
        signal["generated_at"] = datetime.now()

        # Log signal
        self._log_signal(signal)

        return signal

    def _validate_signal(self, signal: Dict) -> bool:
        """Validate signal has required fields and sensible values"""
        required = ["symbol", "direction", "entry", "sl", "tp"]

        for field in required:
            if field not in signal or signal[field] is None:
                self.logger.error(f"Signal missing required field: {field}")
                return False

        # Check SL is reasonable
        if signal["direction"] == "BUY":
            if signal["sl"] >= signal["entry"]:
                self.logger.error("BUY signal: SL must be below entry")
                return False
            if signal["tp"] <= signal["entry"]:
                self.logger.error("BUY signal: TP must be above entry")
                return False
        else:  # SELL
            if signal["sl"] <= signal["entry"]:
                self.logger.error("SELL signal: SL must be above entry")
                return False
            if signal["tp"] >= signal["entry"]:
                self.logger.error("SELL signal: TP must be below entry")
                return False

        # Check risk/reward ratio
        sl_distance = abs(signal["entry"] - signal["sl"])
        tp_distance = abs(signal["tp"] - signal["entry"])
        rr_ratio = tp_distance / sl_distance if sl_distance > 0 else 0

        min_rr = self.config.get("risk.min_risk_reward", 1.0)
        if rr_ratio < min_rr:
            self.logger.warning(
                f"Signal R:R {rr_ratio:.2f} below minimum {min_rr}"
            )
            # Don't reject, just warn

        signal["rr_ratio"] = rr_ratio
        return True

    def _get_symbol_info(self, symbol_config: Dict) -> Dict[str, Any]:
        """Get symbol info from config (fallback if MT5 not available)"""
        return {
            "point": symbol_config.get("pip_value", 0.00001) / 10,  # Point = pip/10 for 5-digit
            "trade_contract_size": self.config.get("broker.contract_size", 1000),
            "min_lot": symbol_config.get("min_lot", 0.01),
            "max_lot": symbol_config.get("max_lot", 0.5),
            "lot_step": 0.01,
        }

    def _log_signal(self, signal: Dict):
        """Log signal to history"""
        self._signal_history.append(signal.copy())

        # Update daily trade count
        symbol = signal.get("symbol")
        self._daily_trades[symbol] = self._daily_trades.get(symbol, 0) + 1

        # Write to CSV
        self._write_signal_to_csv(signal)

    def _write_signal_to_csv(self, signal: Dict):
        """Write signal to CSV log file"""
        import csv
        from pathlib import Path

        log_file = Path(self.config.get("logging.signal_history", "logs/signal_history.csv"))
        log_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists to write header
        write_header = not log_file.exists()

        with open(log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            if write_header:
                writer.writerow([
                    "timestamp", "symbol", "direction", "mode",
                    "entry", "sl", "tp", "lot", "risk_usc", "risk_pct",
                    "rr_ratio", "status"
                ])

            writer.writerow([
                signal.get("generated_at", datetime.now()).isoformat(),
                signal.get("symbol"),
                signal.get("direction"),
                signal.get("mode", "limit"),
                signal.get("entry"),
                signal.get("sl"),
                signal.get("tp"),
                signal.get("lot"),
                signal.get("risk_usc"),
                signal.get("risk_pct"),
                signal.get("rr_ratio"),
                "pending"
            ])

    def record_trade_result(self, symbol: str, pnl_usc: float, is_loss: bool):
        """Record trade result for circuit breaker"""
        self.circuit_breaker.record_trade(pnl_usc, is_loss)

    def get_daily_stats(self) -> Dict:
        """Get daily trading statistics"""
        return {
            "trades_per_symbol": self._daily_trades.copy(),
            "total_signals": len(self._signal_history),
            "circuit_breaker": self.circuit_breaker.get_status(),
        }
