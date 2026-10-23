"""
Signal Engine Core
Main orchestrator for signal generation pipeline
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from src.config import Config
from src.data_feed import DataFeedFactory
from src.risk import RiskManager, CircuitBreaker
from src.filters import NewsGuard, ATRFilter
from src.strategy import StrategyFactory
from src.output import TelegramAlerter


class SignalEngine:
    """Main signal engine orchestrator"""

    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger("SignalEngine")

        # Initialize components
        self._init_components()

        # State
        self.running = False
        self.paused = False
        self.last_signal_time: Dict[str, datetime] = {}
        self.last_check_time: Optional[datetime] = None
        self._signal_count = 0

    def _init_components(self):
        """Initialize all engine components"""
        # Data feed - use config mode
        data_mode = self.config.get("data_feed.default_mode", "api")
        self.data_feed = DataFeedFactory.create(self.config, mode=data_mode)

        # Risk manager
        self.risk_manager = RiskManager(self.config)
        self.circuit_breaker = CircuitBreaker(self.config)

        # Filters
        self.news_guard = NewsGuard(self.config) if self.config.get("news.enabled") else None
        self.atr_filter = ATRFilter(self.config) if self.config.get("atr.enabled") else None

        # Strategy
        self.strategy = StrategyFactory.create(self.config)

        # Output (will be replaced by bot)
        self.alerter = TelegramAlerter(self.config)
        self.bot = None

    def set_bot(self, bot):
        """Set Telegram bot for alerts"""
        self.bot = bot

    def reload_config(self):
        """Reload configuration and reinitialize components"""
        self.logger.info("Reloading configuration...")
        self.config.reload()
        self._init_components()
        self.logger.info("Configuration reloaded")

    def run(self):
        """Main engine loop"""
        self.running = True
        poll_interval = self.config.get("schedule.poll_interval_seconds", 60)

        self.logger.info(f"Engine running. Poll interval: {poll_interval}s")

        while self.running:
            try:
                if not self.paused:
                    self._tick()
            except Exception as e:
                self.logger.error(f"Tick error: {e}", exc_info=True)

            time.sleep(poll_interval)

    def _tick(self):
        """Single iteration of signal check"""
        now = datetime.now()
        self.last_check_time = now

        # Check trading hours
        if not self._is_trading_hours(now):
            self.logger.debug("Outside trading hours, skipping...")
            return

        # Check circuit breaker
        if self.circuit_breaker.is_locked():
            self.logger.warning("Circuit breaker locked - skipping signal check")
            return

        # Process each symbol
        for symbol_config in self.config.get("symbols"):
            self._process_symbol(symbol_config, now)

    def _process_symbol(self, symbol_config: Dict[str, Any], now: datetime):
        """Process single symbol for signals"""
        symbol = symbol_config["name"]

        # Check cooldown
        if not self._check_cooldown(symbol, now):
            return

        # Check news filter
        if self.news_guard and self.news_guard.is_blocked(now):
            self.logger.info(f"{symbol}: News block active, skipping...")
            return

        # Get market data
        try:
            data = self.data_feed.get_data(symbol)
            if data is None or data.empty:
                self.logger.warning(f"{symbol}: No data available")
                return
        except Exception as e:
            self.logger.error(f"{symbol}: Data fetch error: {e}")
            return

        # ATR filter
        if self.atr_filter and not self.atr_filter.is_valid(data):
            self.logger.info(f"{symbol}: ATR filter failed, skipping...")
            return

        # Generate signal
        signal = self.strategy.analyze(symbol, data, symbol_config)
        if signal is None:
            return

        # Apply risk management
        signal = self.risk_manager.apply(signal, symbol_config)
        if signal is None:
            return

        # Add spread buffer
        signal = self._apply_spread_buffer(signal, symbol_config)

        # Add TTL
        ttl = self.config.get("signal.ttl_minutes", 60)
        signal["expiration"] = now + timedelta(minutes=ttl)
        signal["invalidation_price"] = self._calc_invalidation_price(signal)

        # Send alert via bot if available, else via alerter
        if self.bot:
            self.bot.send_signal(signal)
        else:
            self.alerter.send(signal)

        # Update state
        self.last_signal_time[symbol] = now
        self._signal_count += 1
        self.logger.info(f"Signal sent: {symbol} {signal['direction']} @ {signal['entry']}")

    def _is_trading_hours(self, now: datetime) -> bool:
        """Check if within trading hours"""
        start = self.config.get("schedule.trading_hours.start", "00:00")
        end = self.config.get("schedule.trading_hours.end", "23:59")

        start_time = datetime.strptime(start, "%H:%M").time()
        end_time = datetime.strptime(end, "%H:%M").time()

        return start_time <= now.time() <= end_time

    def _check_cooldown(self, symbol: str, now: datetime) -> bool:
        """Check if cooldown period has passed"""
        if symbol not in self.last_signal_time:
            return True

        cooldown = self.config.get("signal.cooldown_minutes", 15)
        elapsed = now - self.last_signal_time[symbol]

        return elapsed >= timedelta(minutes=cooldown)

    def _apply_spread_buffer(self, signal: Dict, symbol_config: Dict) -> Dict:
        """Apply spread buffer to SL/TP"""
        # Use API mode buffer (larger)
        buffer_pips = self.config.get("spread.mode_b_buffer_pips", 5.0)

        pip_value = symbol_config.get("pip_value", 0.00001)
        buffer_price = buffer_pips * pip_value

        # Widen SL by buffer
        if signal["direction"] == "BUY":
            signal["sl"] -= buffer_price
        else:
            signal["sl"] += buffer_price

        signal["spread_buffer_pips"] = buffer_pips
        return signal

    def _calc_invalidation_price(self, signal: Dict) -> float:
        """Calculate price at which signal becomes invalid"""
        # If price moves 50% toward SL without entry, invalidate
        if signal["direction"] == "BUY":
            # For buy, if price drops below this, signal invalid
            return signal["entry"] - abs(signal["entry"] - signal["sl"]) * 0.5
        else:
            # For sell, if price rises above this, signal invalid
            return signal["entry"] + abs(signal["entry"] - signal["sl"]) * 0.5

    def pause(self):
        """Pause signal generation"""
        self.paused = True
        self.logger.info("Engine paused")

    def resume(self):
        """Resume signal generation"""
        self.paused = False
        self.logger.info("Engine resumed")

    def force_check(self):
        """Force immediate signal check"""
        self.logger.info("Force check triggered")
        self._tick()

    def stop(self):
        """Stop the engine"""
        self.running = False
        self.logger.info("Engine stopped")

    def get_status(self) -> Dict:
        """Get engine status"""
        return {
            "running": self.running,
            "paused": self.paused,
            "total_signals": self._signal_count,
            "trades_per_symbol": {
                symbol: 1 if symbol in self.last_signal_time else 0
                for symbol in [s["name"] for s in self.config.get("symbols")]
            },
            "circuit_breaker": self.circuit_breaker.get_status(),
            "last_check": self.last_check_time.strftime("%H:%M:%S") if self.last_check_time else "N/A",
        }
