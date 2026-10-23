#!/usr/bin/env python3
"""
Signal Engine with Interactive Telegram Bot
Run this to start the engine with bot commands
"""

import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.engine import SignalEngine
from src.bot import TelegramBot


def setup_logging(config: Config):
    """Setup logging configuration"""
    log_config = config.get("logging", {})
    log_file = PROJECT_ROOT / log_config.get("file", "logs/signal_engine.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, log_config.get("level", "INFO")),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger("SignalEngine")


def main():
    """Main entry point"""
    print("=" * 50)
    print("SIGNAL ENGINE WITH TELEGRAM BOT")
    print("=" * 50)

    # Load configuration
    config = Config()

    # Setup logging
    logger = setup_logging(config)

    logger.info("=" * 50)
    logger.info("Signal Engine Starting...")
    logger.info(f"Broker: {config.get('broker.name')}")
    logger.info(f"Symbols: {[s['name'] for s in config.get('symbols')]}")
    logger.info(f"Capital: {config.get('risk.capital_usc')} USC")
    data_mode = config.get("data_feed.default_mode", "api")
    mode_text = {
        "mt5": "MT5 Terminal",
        "api": "Yahoo Finance API",
        "synthetic": "Synthetic Data (Testing)"
    }.get(data_mode, data_mode)
    logger.info(f"Data Mode: {mode_text}")
    logger.info("=" * 50)

    # Initialize engine
    engine = SignalEngine(config)

    # Initialize bot
    bot = TelegramBot(config, engine)
    engine.set_bot(bot)

    # Start bot polling
    bot.start()
    logger.info("Telegram Bot started - send /start to begin")

    # Send startup message
    bot.send_startup_message()

    # Run engine
    try:
        engine.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        bot.stop()
        engine.stop()
        logger.info("Signal Engine stopped")


if __name__ == "__main__":
    main()
