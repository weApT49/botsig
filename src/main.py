#!/usr/bin/env python3
"""
Signal Engine - Entry Point
Zero-Cost Intraday Signal Engine for MT5 iOS Target
"""

import sys
import logging
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import Config
from src.engine import SignalEngine


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
    # Load configuration
    config = Config()

    # Setup logging
    logger = setup_logging(config)
    logger.info("=" * 60)
    logger.info("Signal Engine Starting...")
    logger.info(f"Broker: {config.get('broker.name')}")
    logger.info(f"Symbols: {[s['name'] for s in config.get('symbols')]}")
    logger.info(f"Capital: {config.get('risk.capital_usc')} USC")
    logger.info("=" * 60)

    # Initialize engine
    try:
        engine = SignalEngine(config)
        engine.run()
    except KeyboardInterrupt:
        logger.info("Signal Engine stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
