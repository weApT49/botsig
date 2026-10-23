"""
Circuit Breaker
Locks trading after hitting daily loss/drawdown limits
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
from pathlib import Path


class CircuitBreaker:
    """
    Daily circuit breaker to prevent ruin

    Triggers when:
    - Max daily losses reached
    - Max daily drawdown reached

    Locks until next trading day
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("CircuitBreaker")

        # Settings
        self.max_losses = config.get("risk.max_daily_losses", 2)
        self.max_drawdown_pct = config.get("risk.max_daily_drawdown_pct", 3.0)
        self.capital = config.get("risk.capital_usc", 5500)

        # State
        self._locked = False
        self._lock_reason: Optional[str] = None
        self._lock_until: Optional[datetime] = None
        self._daily_losses = 0
        self._daily_pnl = 0.0
        self._last_reset: Optional[datetime] = None

        # History file
        self._history_file = Path("logs/circuit_breaker_state.json")
        self._load_state()

    def _load_state(self):
        """Load state from file"""
        if self._history_file.exists():
            try:
                with open(self._history_file, "r") as f:
                    state = json.load(f)
                    self._daily_losses = state.get("daily_losses", 0)
                    self._daily_pnl = state.get("daily_pnl", 0.0)
                    self._locked = state.get("locked", False)
                    self._lock_reason = state.get("lock_reason")

                    if state.get("last_reset"):
                        self._last_reset = datetime.fromisoformat(state["last_reset"])
                    if state.get("lock_until"):
                        self._lock_until = datetime.fromisoformat(state["lock_until"])

            except Exception as e:
                self.logger.warning(f"Failed to load circuit breaker state: {e}")

    def _save_state(self):
        """Save state to file"""
        self._history_file.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "daily_losses": self._daily_losses,
            "daily_pnl": self._daily_pnl,
            "locked": self._locked,
            "lock_reason": self._lock_reason,
            "lock_until": self._lock_until.isoformat() if self._lock_until else None,
            "last_reset": self._last_reset.isoformat() if self._last_reset else None,
        }

        with open(self._history_file, "w") as f:
            json.dump(state, f, indent=2)

    def _check_new_day(self) -> bool:
        """Check if it's a new trading day and reset if needed"""
        now = datetime.now()
        today = now.date()

        if self._last_reset is None or self._last_reset.date() < today:
            # Reset for new day
            self._daily_losses = 0
            self._daily_pnl = 0.0
            self._locked = False
            self._lock_reason = None
            self._lock_until = None
            self._last_reset = now

            self.logger.info("Circuit breaker reset for new trading day")
            self._save_state()
            return True

        return False

    def _check_lock_expired(self) -> bool:
        """Check if lock has expired"""
        if self._locked and self._lock_until:
            if datetime.now() >= self._lock_until:
                self._locked = False
                self._lock_reason = None
                self._lock_until = None
                self.logger.info("Circuit breaker lock expired")
                self._save_state()
                return True
        return False

    def is_locked(self) -> bool:
        """Check if circuit breaker is currently locked"""
        self._check_new_day()
        self._check_lock_expired()

        return self._locked

    def get_lock_reason(self) -> Optional[str]:
        """Get reason for current lock"""
        return self._lock_reason

    def record_trade(self, pnl_usc: float, is_loss: bool) -> None:
        """
        Record trade result for circuit breaker

        Args:
            pnl_usc: Profit/Loss in USC (positive = profit, negative = loss)
            is_loss: Whether this trade was a loss
        """
        self._check_new_day()

        # Update daily P&L
        self._daily_pnl += pnl_usc

        # Count losses
        if is_loss:
            self._daily_losses += 1

        # Check triggers
        self._check_triggers()

        self._save_state()

    def _check_triggers(self):
        """Check if any trigger conditions are met"""
        # Max losses trigger
        if self._daily_losses >= self.max_losses:
            self._lock(
                reason=f"Max daily losses reached ({self._daily_losses}/{self.max_losses})"
            )
            return

        # Max drawdown trigger
        drawdown_pct = abs(min(self._daily_pnl, 0)) / self.capital * 100
        if drawdown_pct >= self.max_drawdown_pct:
            self._lock(
                reason=f"Max daily drawdown reached ({drawdown_pct:.1f}%/{self.max_drawdown_pct}%)"
            )
            return

    def _lock(self, reason: str):
        """Lock circuit breaker"""
        self._locked = True
        self._lock_reason = reason
        # Lock until midnight
        tomorrow = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        self._lock_until = tomorrow

        self.logger.warning(f"🔴 CIRCUIT BREAKER LOCKED: {reason}")
        self.logger.warning(f"Trading locked until: {self._lock_until}")

    def force_unlock(self):
        """Manually unlock (use with caution)"""
        self._locked = False
        self._lock_reason = None
        self._lock_until = None
        self.logger.info("Circuit breaker manually unlocked")
        self._save_state()

    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        return {
            "locked": self._locked,
            "lock_reason": self._lock_reason,
            "lock_until": self._lock_until.isoformat() if self._lock_until else None,
            "daily_losses": self._daily_losses,
            "max_losses": self.max_losses,
            "daily_pnl": self._daily_pnl,
            "daily_drawdown_pct": abs(min(self._daily_pnl, 0)) / self.capital * 100,
            "max_drawdown_pct": self.max_drawdown_pct,
        }
