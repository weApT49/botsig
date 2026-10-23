"""
Telegram Alerter
Sends trading signals to Telegram with iOS one-tap copy format
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import requests


class TelegramAlerter:
    """
    Telegram notification service

    Formats signals for easy one-tap copy on iOS:
    - Inline code blocks for prices
    - Clear structure
    - TTL and invalidation info
    """

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("TelegramAlerter")

        # Settings
        self.bot_token = config.get("telegram.bot_token")
        self.chat_id = config.get("telegram.chat_id")
        self.parse_mode = config.get("telegram.parse_mode", "MarkdownV2")

        # Validate
        if not self.bot_token or not self.chat_id:
            self.logger.error("Telegram bot_token or chat_id not configured")

    def send(self, signal: Dict) -> bool:
        """
        Send signal alert to Telegram

        Args:
            signal: Signal dictionary with entry, sl, tp, lot, etc.

        Returns:
            True if sent successfully
        """
        if not self.bot_token or not self.chat_id:
            self.logger.error("Cannot send: Telegram not configured")
            return False

        # Format message
        message = self._format_signal(signal)

        # Send via API
        return self._send_message(message)

    def _escape(self, text) -> str:
        """Escape special characters for MarkdownV2"""
        text = str(text)
        special = "_*[]()~`>#+-=|{}.!"
        for char in special:
            text = text.replace(char, "\\" + char)
        return text

    def _format_signal(self, signal: Dict) -> str:
        """
        Format signal for Telegram
        """
        # Direction emoji and text
        direction = signal.get("direction", "BUY")
        if direction == "BUY":
            emoji = "\U0001F7E2"  # Green circle
        else:
            emoji = "\U0001F534"  # Red circle

        # Mode
        mode = signal.get("mode", "limit").upper()
        mode_text = "LIMIT ORDER" if mode == "LIMIT" else "MARKET ORDER"

        # Format expiration
        expiration = signal.get("expiration")
        if expiration:
            if isinstance(expiration, datetime):
                exp_str = expiration.strftime("%H:%M")
            else:
                exp_str = str(expiration)
        else:
            exp_str = "N/A"

        # Format values
        symbol = self._escape(signal.get("symbol", "UNKNOWN"))
        entry = self._escape(str(signal.get("entry", 0)))
        sl = self._escape(str(signal.get("sl", 0)))
        tp = self._escape(str(signal.get("tp", 0)))
        lot = self._escape(str(signal.get("lot", 0.01)))
        risk_usc = signal.get("risk_usc", 0)
        risk_pct = signal.get("risk_pct", 0)
        rr = self._escape(str(round(signal.get("rr_ratio", 0), 2)))
        inv_price = self._escape(str(round(signal.get("invalidation_price", 0), 5)))
        strategy = self._escape(signal.get("strategy", "N/A"))
        timeframe = self._escape(signal.get("timeframe", "N/A"))

        # Build message
        lines = [
            f"{emoji} *{self._escape(direction)} {symbol}*",
            "",
            f"\U0001F4CA *{self._escape(mode_text)}*",
            "",
            f"\U0001F4CD *Entry:* `{entry}`",
            f"\U0001F6D1 *Stop Loss:* `{sl}`",
            f"\U0001F3AF *Take Profit:* `{tp}`",
            "",
            f"\U0001F4CF *Lot Size:* `{lot}`",
            f"\U0001F4B0 *Risk:* {risk_usc:.1f} USC \\({risk_pct:.1f}%\\)",
            f"\U0001F4C8 *R:R:* `{rr}`",
            "",
            f"⏰ *TTL:* {self._escape(exp_str)}",
            f"⚠️ *Invalidate:* `{inv_price}`",
            "",
            f"_Strategy: {strategy} | TF: {timeframe}_",
        ]

        message = "\n".join(lines)
        return message

    def _send_message(self, text: str) -> bool:
        """Send message via Telegram Bot API"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": self.parse_mode,
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                self.logger.info("Signal sent to Telegram successfully")
                return True
            else:
                self.logger.error(f"Telegram API error: {result.get('description')}")
                return False

        except requests.RequestException as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False

    def send_test(self) -> bool:
        """Send test message to verify connection"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message = (
            "✅ *Signal Engine Connected*\n\n"
            "Your Telegram bot is configured correctly\\.\n\n"
            f"_Time: {self._escape(now)}_"
        )
        return self._send_message(message)

    def send_status(self, status: Dict) -> bool:
        """Send engine status update"""
        cb = status.get("circuit_breaker", {})
        locked = cb.get("locked", False)

        if locked:
            status_emoji = "\U0001F534"
            status_text = "LOCKED"
        else:
            status_emoji = "\U0001F7E2"
            status_text = "ACTIVE"

        total_signals = status.get("total_signals", 0)
        trades_per_symbol = str(status.get("trades_per_symbol", {}))
        daily_losses = cb.get("daily_losses", 0)
        max_losses = cb.get("max_losses", 2)
        daily_dd = cb.get("daily_drawdown_pct", 0)
        max_dd = cb.get("max_drawdown_pct", 3)

        lines = [
            f"{status_emoji} *Engine Status: {self._escape(status_text)}*",
            "",
            f"\U0001F4CA *Daily Stats:*",
            f"  • Signals: {total_signals}",
            f"  • Trades/Symbol: {self._escape(trades_per_symbol)}",
            "",
            f"⚡ *Circuit Breaker:*",
            f"  • Status: {self._escape('LOCKED' if locked else 'OK')}",
            f"  • Daily Losses: {daily_losses}/{max_losses}",
            f"  • Daily DD: {daily_dd:.2f}%/{max_dd}%",
        ]

        if locked and cb.get("lock_reason"):
            lines.append(f"  • Reason: {self._escape(cb.get('lock_reason'))}")

        message = "\n".join(lines)
        return self._send_message(message)

    def send_warning(self, title: str, message: str) -> bool:
        """Send warning notification"""
        full_message = f"⚠️ *{self._escape(title)}*\n\n{self._escape(message)}"
        return self._send_message(full_message)
