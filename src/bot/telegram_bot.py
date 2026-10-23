"""
Telegram Bot Handler
Interactive bot with commands and inline buttons
Supports Thai and English languages
"""

import logging
import threading
from datetime import datetime
from typing import Dict, Optional, Callable
import requests

# Import settings handler
from .settings_handler import extend_telegram_bot


class TelegramBot:
    """
    Interactive Telegram Bot with:
    - Command handlers (/start, /status, /backtest, etc.)
    - Inline button callbacks
    - Background polling
    - Thai/English language support
    """

    # Language texts
    TEXTS = {
        "th": {
            # Commands
            "welcome": "*Signal Engine Bot*\n\n"
                       "สวัสดี! Bot นี้จะส่งสัญญาณเทรดสำหรับ XAUUSD และ EURUSD\n\n"
                       "*คำสั่งที่ใช้ได้:*\n"
                       "/start - แสดงข้อความนี้\n"
                       "/help - วิธีใช้งาน\n"
                       "/status - สถานะ Engine\n"
                       "/backtest - รัน Backtest\n"
                       "/settings - ดูการตั้งค่า\n"
                       "/pause - หยุดส่งสัญญาณ\n"
                       "/resume - เปิดส่งสัญญาณ\n"
                       "/force - บังคับตรวจสอบ\n"
                       "/lang - เปลี่ยนภาษา\n\n"
                       "เลือกการกระทำด้านล่าง:",

            "help": "*วิธีใช้งาน - Signal Engine*\n\n"
                    "*ระบบทำงานอย่างไร:*\n"
                    "1. Engine ติดตาม XAUUSD และ EURUSD\n"
                    "2. สร้างสัญญาณพร้อม Entry, SL, TP\n"
                    "3. ส่งแจ้งเตือนมาที่แชทนี้\n"
                    "4. สัญญาณมี TTL (เวลาหมดอายุ)\n\n"
                    "*Risk Management:*\n"
                    "- Risk สูงสุด 1-1.5% ต่อเทรด\n"
                    "- ขาดสูงสุด 2 ครั้งต่อวัน\n"
                    "- Drawdown สูงสุด 3% ต่อวัน\n\n"
                    "*Circuit Breaker:*\n"
                    "ล็อคการเทรดเมื่อถึงขีดจำกัด\n"
                    "รีเซ็ตเวลาเที่ยงคืน",

            "status_active": "🟢 *สถานะ: ทำงานปกติ*",
            "status_paused": "⏸️ *สถานะ: หยุดชั่วคราว*",
            "status_locked": "🔴 *สถานะ: ล็อค (Circuit Breaker)*",

            "status_stats": "📊 *สถิติวันนี้:*\n"
                           "  • สัญญาณทั้งหมด: {signals}\n"
                           "  • เทรด: {trades}\n\n"
                           "⚡ *Circuit Breaker:*\n"
                           "  • ขาด: {losses}/{max_losses}\n"
                           "  • DD: {dd:.2f}%/{max_dd}%\n\n"
                           "🕐 *ตรวจสอบล่าสุด:* {last_check}",

            "settings": "⚙️ *การตั้งค่าปัจจุบัน*\n\n"
                       "💰 *เงินทุน:* {capital} USC\n"
                       "📈 *Risk/เทรด:* {risk_pct}%\n"
                       "🛑 *ขาดสูงสุด/วัน:* {max_losses}\n"
                       "📉 *DD สูงสุด:* {max_dd}%\n\n"
                       "📊 *คู่เงิน:* {symbols}\n"
                       "⏰ *TTL:* {ttl} นาที\n"
                       "🕐 *Cooldown:* {cooldown} นาที\n"
                       "📱 *โหมด:* API (Yahoo Finance)",

            "backtest_running": "⏳ กำลังรัน Backtest... กรุณารอสักครู่",
            "backtest_results": "📊 *ผล Backtest*\n\n{results}",
            "backtest_failed": "❌ Backtest ล้มเหลว: {error}",

            "paused": "⏸️ *Engine หยุดชั่วคราว*\n\nกด /resume หรือปุ่ม ▶️ เพื่อเปิดทำงานต่อ",
            "resumed": "▶️ *Engine กลับมาทำงาน*\n\nสัญญาณจะถูกส่งตามปกติ",
            "forced": "🔄 บังคับตรวจสอบสัญญาณแล้ว...",
            "engine_not_running": "⚠️ Engine ยังไม่ทำงาน",

            "signal_buy": "🟢 *BUY {symbol}*",
            "signal_sell": "🔴 *SELL {symbol}*",
            "signal_limit": "📊 *LIMIT ORDER*",
            "signal_market": "📊 *MARKET ORDER*",
            "signal_entry": "📍 *Entry:* `{entry}`",
            "signal_sl": "🛑 *SL:* `{sl}`",
            "signal_tp": "🎯 *TP:* `{tp}`",
            "signal_lot": "📏 *Lot:* `{lot}`",
            "signal_risk": "💰 *Risk:* {risk_usc:.1f} USC ({risk_pct:.1f}%)",
            "signal_rr": "📈 *R:R:* `{rr:.2f}`",
            "signal_ttl": "⏰ *หมดอายุ:* {exp}",
            "signal_invalidate": "⚠️ *ยกเลิกถ้าถึง:* `{inv_price:.5f}`",
            "signal_strategy": "_Strategy: {strategy} | TF: {tf}_",

            "startup": "🚀 *Signal Engine เริ่มทำงานแล้ว*\n\n"
                      "📊 *คู่เงิน:* {symbols}\n"
                      "💰 *เงินทุน:* {capital} USC\n"
                      "📈 *Risk:* {risk_pct}% ต่อเทรด\n\n"
                      "ใช้ /help ดูวิธีใช้งาน หรือกดปุ่มด้านล่าง",

            "select_action": "เลือกการกระทำ:",
            "btn_status": "📊 สถานะ",
            "btn_backtest": "🔄 Backtest",
            "btn_pause": "⏸️ หยุด",
            "btn_resume": "▶️ เปิด",
            "btn_settings": "⚙️ ตั้งค่า",
            "btn_lang_th": "🇹🇭 ไทย",
            "btn_lang_en": "🇬🇧 English",

            "lang_changed": "✅ เปลี่ยนภาษาเป็น {lang} แล้ว",
        },

        "en": {
            # Commands
            "welcome": "*Signal Engine Bot*\n\n"
                       "Welcome! This bot sends trading signals for XAUUSD and EURUSD.\n\n"
                       "*Available Commands:*\n"
                       "/start - Show this message\n"
                       "/help - Show help\n"
                       "/status - Engine status\n"
                       "/backtest - Run backtest\n"
                       "/settings - Show settings\n"
                       "/pause - Pause signals\n"
                       "/resume - Resume signals\n"
                       "/force - Force signal check\n"
                       "/lang - Change language\n\n"
                       "Select an action below:",

            "help": "*Help - Signal Engine*\n\n"
                    "*How it works:*\n"
                    "1. Engine monitors XAUUSD and EURUSD\n"
                    "2. Generates signals with Entry, SL, TP\n"
                    "3. Sends alerts to this chat\n"
                    "4. Signal includes TTL (time-to-live)\n\n"
                    "*Risk Management:*\n"
                    "- Max 1-1.5% risk per trade\n"
                    "- Max 2 losses per day\n"
                    "- Max 3% daily drawdown\n\n"
                    "*Circuit Breaker:*\n"
                    "Locks trading when daily limits hit.\n"
                    "Resets at midnight.",

            "status_active": "🟢 *Status: ACTIVE*",
            "status_paused": "⏸️ *Status: PAUSED*",
            "status_locked": "🔴 *Status: LOCKED (Circuit Breaker)*",

            "status_stats": "📊 *Daily Stats:*\n"
                           "  • Signals: {signals}\n"
                           "  • Trades: {trades}\n\n"
                           "⚡ *Circuit Breaker:*\n"
                           "  • Losses: {losses}/{max_losses}\n"
                           "  • DD: {dd:.2f}%/{max_dd}%\n\n"
                           "🕐 *Last Check:* {last_check}",

            "settings": "⚙️ *Current Settings*\n\n"
                       "💰 *Capital:* {capital} USC\n"
                       "📈 *Risk/Trade:* {risk_pct}%\n"
                       "🛑 *Max Losses/Day:* {max_losses}\n"
                       "📉 *Max DD:* {max_dd}%\n\n"
                       "📊 *Symbols:* {symbols}\n"
                       "⏰ *TTL:* {ttl} min\n"
                       "🕐 *Cooldown:* {cooldown} min\n"
                       "📱 *Mode:* API (Yahoo Finance)",

            "backtest_running": "⏳ Running backtest... Please wait.",
            "backtest_results": "📊 *Backtest Results*\n\n{results}",
            "backtest_failed": "❌ Backtest failed: {error}",

            "paused": "⏸️ *Engine PAUSED*\n\nUse /resume or ▶️ button to continue.",
            "resumed": "▶️ *Engine RESUMED*\n\nSignals will be sent normally.",
            "forced": "🔄 Forcing signal check...",
            "engine_not_running": "⚠️ Engine not running.",

            "signal_buy": "🟢 *BUY {symbol}*",
            "signal_sell": "🔴 *SELL {symbol}*",
            "signal_limit": "📊 *LIMIT ORDER*",
            "signal_market": "📊 *MARKET ORDER*",
            "signal_entry": "📍 *Entry:* `{entry}`",
            "signal_sl": "🛑 *SL:* `{sl}`",
            "signal_tp": "🎯 *TP:* `{tp}`",
            "signal_lot": "📏 *Lot:* `{lot}`",
            "signal_risk": "💰 *Risk:* {risk_usc:.1f} USC ({risk_pct:.1f}%)",
            "signal_rr": "📈 *R:R:* `{rr:.2f}`",
            "signal_ttl": "⏰ *Expires:* {exp}",
            "signal_invalidate": "⚠️ *Invalidate at:* `{inv_price:.5f}`",
            "signal_strategy": "_Strategy: {strategy} | TF: {tf}_",

            "startup": "🚀 *Signal Engine Started*\n\n"
                      "📊 *Symbols:* {symbols}\n"
                      "💰 *Capital:* {capital} USC\n"
                      "📈 *Risk:* {risk_pct}% per trade\n\n"
                      "Use /help for commands or buttons below.",

            "select_action": "Select an action:",
            "btn_status": "📊 Status",
            "btn_backtest": "🔄 Backtest",
            "btn_pause": "⏸️ Pause",
            "btn_resume": "▶️ Resume",
            "btn_settings": "⚙️ Settings",
            "btn_lang_th": "🇹🇭 ไทย",
            "btn_lang_en": "🇬🇧 English",

            "lang_changed": "✅ Language changed to {lang}",
        }
    }

    def __init__(self, config, engine=None):
        self.config = config
        self.engine = engine
        self.logger = logging.getLogger("TelegramBot")

        # Settings
        self.bot_token = config.get("telegram.bot_token")
        self.chat_id = config.get("telegram.chat_id")

        # Language state (default: Thai)
        self._language = "th"

        # State
        self._running = False
        self._last_update_id = 0
        self._poll_thread: Optional[threading.Thread] = None

        # Command handlers
        self._commands: Dict[str, Callable] = {
            "start": self._cmd_start,
            "help": self._cmd_help,
            "status": self._cmd_status,
            "backtest": self._cmd_backtest,
            "settings": self._cmd_settings,
            "pause": self._cmd_pause,
            "resume": self._cmd_resume,
            "force": self._cmd_force_signal,
            "lang": self._cmd_lang,
        }

        # Callback handlers for buttons
        self._callbacks: Dict[str, Callable] = {
            "btn_status": self._cb_status,
            "btn_backtest": self._cb_backtest,
            "btn_pause": self._cb_pause,
            "btn_resume": self._cb_resume,
            "btn_settings": self._cb_settings,
            "btn_lang_th": self._cb_lang_th,
            "btn_lang_en": self._cb_lang_en,
        }

        # Extend with settings handler
        extend_telegram_bot(self)

    def _t(self, key: str, **kwargs) -> str:
        """Get text in current language"""
        text = self.TEXTS.get(self._language, self.TEXTS["th"]).get(key, key)
        if kwargs:
            text = text.format(**kwargs)
        return text

    def start(self):
        """Start polling for updates"""
        if self._running:
            return

        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

        self.logger.info("Telegram Bot started polling")

    def stop(self):
        """Stop polling"""
        self._running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=5)

        self.logger.info("Telegram Bot stopped")

    def _poll_loop(self):
        """Background polling loop"""
        while self._running:
            try:
                self._get_updates()
            except Exception as e:
                self.logger.error(f"Polling error: {e}")

    def _get_updates(self):
        """Get updates from Telegram API"""
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"

        params = {
            "offset": self._last_update_id + 1,
            "timeout": 30,
            "allowed_updates": ["message", "callback_query"]
        }

        try:
            response = requests.get(url, params=params, timeout=35)
            response.raise_for_status()

            data = response.json()
            if not data.get("ok"):
                return

            updates = data.get("result", [])

            for update in updates:
                self._last_update_id = update.get("update_id", 0)

                # Handle message
                if "message" in update:
                    self._handle_message(update["message"])

                # Handle callback query (button press)
                if "callback_query" in update:
                    self._handle_callback(update["callback_query"])

        except requests.RequestException as e:
            self.logger.error(f"Failed to get updates: {e}")

    def _handle_message(self, message: Dict):
        """Handle incoming message"""
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")

        # Only respond to configured chat
        if chat_id != self.chat_id:
            return

        # Check for command
        if text.startswith("/"):
            parts = text[1:].split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            handler = self._commands.get(command)
            if handler:
                handler(chat_id, args)
            else:
                self._send_message(chat_id, f"Unknown command: /{command}\n\nUse /help for available commands.")

    def _handle_callback(self, callback: Dict):
        """Handle button callback"""
        chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
        data = callback.get("data", "")
        callback_id = callback.get("id")

        # Only respond to configured chat
        if chat_id != self.chat_id:
            return

        # Answer callback (remove loading state)
        self._answer_callback(callback_id)

        # Execute callback handler
        handler = self._callbacks.get(data)
        if handler:
            handler(chat_id)

    def _answer_callback(self, callback_id: str):
        """Answer callback query to remove loading state"""
        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        requests.post(url, json={"callback_query_id": callback_id}, timeout=10)

    # ==================== COMMAND HANDLERS ====================

    def _cmd_start(self, chat_id: str, args: list):
        """Handle /start command"""
        self._send_message_with_buttons(chat_id, self._t("welcome"), self._get_main_buttons())

    def _cmd_help(self, chat_id: str, args: list):
        """Handle /help command"""
        self._send_message(chat_id, self._t("help"))

    def _cmd_status(self, chat_id: str, args: list):
        """Handle /status command"""
        self._send_status(chat_id)

    def _cmd_backtest(self, chat_id: str, args: list):
        """Handle /backtest command"""
        self._send_message(chat_id, self._t("backtest_running"))

        # Run backtest in background
        threading.Thread(
            target=self._run_backtest_background,
            args=(chat_id,),
            daemon=True
        ).start()

    def _cmd_settings(self, chat_id: str, args: list):
        """Handle /settings command"""
        self._send_settings(chat_id)

    def _cmd_pause(self, chat_id: str, args: list):
        """Handle /pause command"""
        if self.engine:
            self.engine.pause()
            self._send_message(chat_id, self._t("paused"))
        else:
            self._send_message(chat_id, self._t("engine_not_running"))

    def _cmd_resume(self, chat_id: str, args: list):
        """Handle /resume command"""
        if self.engine:
            self.engine.resume()
            self._send_message(chat_id, self._t("resumed"))
        else:
            self._send_message(chat_id, self._t("engine_not_running"))

    def _cmd_force_signal(self, chat_id: str, args: list):
        """Handle /force command"""
        if self.engine:
            self._send_message(chat_id, self._t("forced"))
            self.engine.force_check()
        else:
            self._send_message(chat_id, self._t("engine_not_running"))

    def _cmd_lang(self, chat_id: str, args: list):
        """Handle /lang command"""
        self._send_message_with_buttons(chat_id, "เลือกภาษา / Select language:", self._get_lang_buttons())

    # ==================== CALLBACK HANDLERS ====================

    def _cb_status(self, chat_id: str):
        """Status button callback"""
        self._send_status(chat_id)

    def _cb_backtest(self, chat_id: str):
        """Backtest button callback"""
        self._cmd_backtest(chat_id, [])

    def _cb_pause(self, chat_id: str):
        """Pause button callback"""
        self._cmd_pause(chat_id, [])

    def _cb_resume(self, chat_id: str):
        """Resume button callback"""
        self._cmd_resume(chat_id, [])

    def _cb_settings(self, chat_id: str):
        """Settings button callback"""
        self._send_settings(chat_id)

    def _cb_lang_th(self, chat_id: str):
        """Thai language button callback"""
        self._language = "th"
        self._send_message(chat_id, self._t("lang_changed", lang="ไทย"))

    def _cb_lang_en(self, chat_id: str):
        """English language button callback"""
        self._language = "en"
        self._send_message(chat_id, self._t("lang_changed", lang="English"))

    # ==================== HELPER METHODS ====================

    def _get_main_buttons(self) -> Dict:
        """Get main menu inline buttons"""
        return {
            "inline_keyboard": [
                [
                    {"text": self._t("btn_status"), "callback_data": "btn_status"},
                    {"text": self._t("btn_backtest"), "callback_data": "btn_backtest"}
                ],
                [
                    {"text": self._t("btn_pause"), "callback_data": "btn_pause"},
                    {"text": self._t("btn_resume"), "callback_data": "btn_resume"}
                ],
                [
                    {"text": self._t("btn_settings"), "callback_data": "btn_settings"},
                ],
                [
                    {"text": self._t("btn_lang_th"), "callback_data": "btn_lang_th"},
                    {"text": self._t("btn_lang_en"), "callback_data": "btn_lang_en"}
                ]
            ]
        }

    def _get_lang_buttons(self) -> Dict:
        """Get language selection buttons"""
        return {
            "inline_keyboard": [
                [
                    {"text": "🇹🇭 ไทย", "callback_data": "btn_lang_th"},
                    {"text": "🇬🇧 English", "callback_data": "btn_lang_en"}
                ]
            ]
        }

    def _send_message(self, chat_id: str, text: str, parse_mode: str = "Markdown"):
        """Send text message"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        try:
            requests.post(url, json=payload, timeout=30)
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")

    def _send_message_with_buttons(self, chat_id: str, text: str, buttons: Dict, parse_mode: str = "Markdown"):
        """Send message with inline buttons"""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "reply_markup": buttons
        }

        try:
            requests.post(url, json=payload, timeout=30)
        except Exception as e:
            self.logger.error(f"Failed to send message with buttons: {e}")

    def _send_status(self, chat_id: str):
        """Send engine status"""
        if self.engine:
            status = self.engine.get_status()
            cb = status.get("circuit_breaker", {})
            locked = cb.get("locked", False)
            paused = status.get("paused", False)

            if locked:
                status_text = self._t("status_locked")
            elif paused:
                status_text = self._t("status_paused")
            else:
                status_text = self._t("status_active")

            stats_text = self._t(
                "status_stats",
                signals=status.get('total_signals', 0),
                trades=str(status.get('trades_per_symbol', {})),
                losses=cb.get('daily_losses', 0),
                max_losses=cb.get('max_losses', 2),
                dd=cb.get('daily_drawdown_pct', 0),
                max_dd=cb.get('max_drawdown_pct', 3),
                last_check=status.get('last_check', 'N/A')
            )

            text = f"{status_text}\n\n{stats_text}"
        else:
            text = self._t("engine_not_running")

        self._send_message_with_buttons(chat_id, text, self._get_main_buttons())

    def _send_settings(self, chat_id: str):
        """Send current settings"""
        risk = self.config.get("risk", {})
        signal = self.config.get("signal", {})
        symbols = self.config.get("symbols", [])

        symbol_names = [s.get("name") for s in symbols]

        text = self._t(
            "settings",
            capital=risk.get('capital_usc', 5500),
            risk_pct=risk.get('risk_per_trade_pct', 1.0),
            max_losses=risk.get('max_daily_losses', 2),
            max_dd=risk.get('max_daily_drawdown_pct', 3.0),
            symbols=', '.join(symbol_names),
            ttl=signal.get('ttl_minutes', 60),
            cooldown=signal.get('cooldown_minutes', 15)
        )

        self._send_message(chat_id, text)

    def _run_backtest_background(self, chat_id: str):
        """Run backtest in background and send result"""
        try:
            from src.data_feed import DataFeedFactory
            from src.strategy import StrategyFactory
            from src.backtest import BacktestSanityCheck

            feed = DataFeedFactory.create(self.config, mode="api")
            strategy = StrategyFactory.create(self.config)
            backtest = BacktestSanityCheck(self.config)

            symbols = self.config.get("symbols")
            results = []

            for symbol_config in symbols:
                symbol = symbol_config["name"]

                # Try to fetch data
                df = feed.get_data(symbol, "M15", 500)

                if df is None or df.empty:
                    if self._language == "th":
                        results.append(f"❌ {symbol}: ดึงข้อมูลไม่สำเร็จ (API rate limit)")
                    else:
                        results.append(f"❌ {symbol}: Could not fetch data (API rate limit)")
                    continue

                # Run backtest
                backtest_result = backtest.run(df, symbol, symbol_config, strategy)

                passed = "✅" if backtest_result.get("passed") else "❌"
                if self._language == "th":
                    results.append(
                        f"{passed} {symbol}: {backtest_result.get('total_trades', 0)} เทรด, "
                        f"ชนะ {backtest_result.get('win_rate', 0)*100:.1f}%, "
                        f"Expectancy {backtest_result.get('expectancy', 0):.2f}R"
                    )
                else:
                    results.append(
                        f"{passed} {symbol}: {backtest_result.get('total_trades', 0)} trades, "
                        f"Win {backtest_result.get('win_rate', 0)*100:.1f}%, "
                        f"Expectancy {backtest_result.get('expectancy', 0):.2f}R"
                    )

            # Send results
            result_text = self._t("backtest_results", results="\n".join(results))
            self._send_message(chat_id, result_text)

        except Exception as e:
            self.logger.error(f"Backtest error: {e}")
            self._send_message(chat_id, self._t("backtest_failed", error=str(e)))

    def send_signal(self, signal: Dict) -> bool:
        """Send trading signal alert"""
        return self._send_signal_alert(self.chat_id, signal)

    def _send_signal_alert(self, chat_id: str, signal: Dict) -> bool:
        """Format and send signal alert"""
        direction = signal.get("direction", "BUY")
        symbol = signal.get("symbol", "UNKNOWN")

        if direction == "BUY":
            header = self._t("signal_buy", symbol=symbol)
        else:
            header = self._t("signal_sell", symbol=symbol)

        mode = signal.get("mode", "limit").upper()
        mode_text = self._t("signal_limit") if mode == "LIMIT" else self._t("signal_market")

        expiration = signal.get("expiration")
        if expiration:
            if isinstance(expiration, datetime):
                exp_str = expiration.strftime("%H:%M")
            else:
                exp_str = str(expiration)
        else:
            exp_str = "N/A"

        lines = [
            header,
            "",
            mode_text,
            "",
            self._t("signal_entry", entry=signal.get('entry', 0)),
            self._t("signal_sl", sl=signal.get('sl', 0)),
            self._t("signal_tp", tp=signal.get('tp', 0)),
            "",
            self._t("signal_lot", lot=signal.get('lot', 0.01)),
            self._t("signal_risk", risk_usc=signal.get('risk_usc', 0), risk_pct=signal.get('risk_pct', 0)),
            self._t("signal_rr", rr=signal.get('rr_ratio', 0)),
            "",
            self._t("signal_ttl", exp=exp_str),
            self._t("signal_invalidate", inv_price=signal.get('invalidation_price', 0)),
            "",
            self._t("signal_strategy", strategy=signal.get('strategy', 'N/A'), tf=signal.get('timeframe', 'N/A')),
        ]

        text = "\n".join(lines)
        return self._send_message(chat_id, text)

    def send_startup_message(self):
        """Send startup notification"""
        symbols = [s.get("name") for s in self.config.get("symbols", [])]
        risk = self.config.get("risk", {})

        text = self._t(
            "startup",
            symbols=', '.join(symbols),
            capital=risk.get('capital_usc', 5500),
            risk_pct=risk.get('risk_per_trade_pct', 1.0)
        )

        self._send_message(self.chat_id, text)
        self._send_message_with_buttons(self.chat_id, self._t("select_action"), self._get_main_buttons())
