#!/usr/bin/env python3
"""
Quick Start Script
Run the signal engine with simple command
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.engine import SignalEngine
from src.output import TelegramAlerter


def test_telegram():
    """Test Telegram connection"""
    print("Testing Telegram connection...")
    config = Config()
    alerter = TelegramAlerter(config)

    if alerter.send_test():
        print("✅ Telegram connected successfully!")
        return True
    else:
        print("❌ Telegram connection failed. Check bot_token and chat_id.")
        return False


def run_backtest():
    """Run historical backtest"""
    print("\nRunning backtest...")
    from src.data_feed import DataFeedFactory
    from src.strategy import StrategyFactory
    from src.backtest import BacktestSanityCheck

    config = Config()

    # Use API mode for backtest (doesn't need MT5)
    feed = DataFeedFactory.create(config, mode="api")
    strategy = StrategyFactory.create(config)
    backtest = BacktestSanityCheck(config)

    symbols = config.get("symbols")

    for symbol_config in symbols:
        symbol = symbol_config["name"]
        print(f"\nFetching data for {symbol}...")

        df = feed.get_data(symbol, "M15", 500)

        if df is None:
            print(f"❌ Could not fetch data for {symbol}")
            continue

        print(f"Got {len(df)} bars. Running backtest...")

        results = backtest.run(df, symbol, symbol_config, strategy)
        print(backtest.get_report())


def main():
    """Main entry"""
    print("=" * 50)
    print("SIGNAL ENGINE")
    print("=" * 50)

    # Test Telegram first
    if not test_telegram():
        print("\n⚠️ Telegram not configured. Signals will not be sent.")
        print("Set telegram.bot_token and telegram.chat_id in config/settings.yaml")

    print("\nOptions:")
    print("1. Run signal engine")
    print("2. Run backtest only")
    print("3. Exit")

    choice = input("\nSelect (1/2/3): ").strip()

    if choice == "1":
        print("\nStarting signal engine...")
        config = Config()
        engine = SignalEngine(config)

        try:
            engine.run()
        except KeyboardInterrupt:
            print("\nEngine stopped.")

    elif choice == "2":
        run_backtest()

    else:
        print("Exiting.")


if __name__ == "__main__":
    main()
