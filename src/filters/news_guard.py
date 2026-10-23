"""
News Guard
Blocks signals around high-impact news events
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import requests
from pathlib import Path


class NewsGuard:
    """
    High-impact news filter

    Fetches economic calendar from Forex Factory (free)
    Blocks signals within window around high-impact events
    """

    # Forex Factory calendar URL (free JSON feed)
    FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    # Alternative: Investing.com (requires scraping)
    # INVESTING_URL = "https://www.investing.com/economic-calendar/"

    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger("NewsGuard")

        # Settings
        self.enabled = config.get("news.enabled", True)
        self.block_window = config.get("news.block_window_minutes", 30)
        self.impact_levels = config.get("news.impact_levels", ["High"])
        self.calendar_url = config.get("news.calendar_url", self.FF_CALENDAR_URL)

        # Cache
        self._events: List[Dict] = []
        self._last_fetch: Optional[datetime] = None
        self._cache_file = Path("config/news_calendar.json")

        # Load cached events
        self._load_cache()

    def _load_cache(self):
        """Load cached news events from file"""
        if self._cache_file.exists():
            try:
                with open(self._cache_file, "r") as f:
                    data = json.load(f)
                    self._events = data.get("events", [])
                    if data.get("last_fetch"):
                        self._last_fetch = datetime.fromisoformat(data["last_fetch"])
            except Exception as e:
                self.logger.warning(f"Failed to load news cache: {e}")

    def _save_cache(self):
        """Save news events to cache file"""
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "events": self._events,
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None
        }

        with open(self._cache_file, "w") as f:
            json.dump(data, f, indent=2)

    def fetch_events(self, force: bool = False) -> bool:
        """
        Fetch news events from calendar

        Args:
            force: Force refresh even if recently fetched

        Returns:
            True if fetch successful
        """
        if not self.enabled:
            return True

        # Check if refresh needed (every 6 hours)
        if not force and self._last_fetch:
            if datetime.now() - self._last_fetch < timedelta(hours=6):
                return True

        try:
            response = requests.get(self.calendar_url, timeout=30)
            response.raise_for_status()

            events = response.json()

            # Filter for relevant currencies and impact
            relevant_currencies = ["USD", "EUR", "GBP"]  # XAUUSD + EURUSD related
            filtered = []

            for event in events:
                if event.get("impact") in self.impact_levels:
                    if event.get("currency") in relevant_currencies:
                        # Parse event time
                        event_time = self._parse_ff_time(event.get("date"))
                        if event_time:
                            filtered.append({
                                "time": event_time,
                                "currency": event.get("currency"),
                                "event": event.get("title"),
                                "impact": event.get("impact"),
                                "forecast": event.get("forecast"),
                                "previous": event.get("previous"),
                            })

            self._events = filtered
            self._last_fetch = datetime.now()
            self._save_cache()

            self.logger.info(f"Fetched {len(filtered)} high-impact news events")
            return True

        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch news calendar: {e}")
            return False

    def _parse_ff_time(self, date_str: str) -> Optional[datetime]:
        """Parse Forex Factory date format"""
        if not date_str:
            return None

        try:
            # FF format: "10-22-2026 08:30am" or similar
            # Try multiple formats
            formats = [
                "%m-%d-%Y %I:%M%p",
                "%m-%d-%Y %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue

            return None
        except Exception:
            return None

    def is_blocked(self, check_time: datetime = None) -> bool:
        """
        Check if current time is within news block window

        Args:
            check_time: Time to check (uses now if None)

        Returns:
            True if trading should be blocked
        """
        if not self.enabled:
            return False

        if check_time is None:
            check_time = datetime.now()

        # Ensure we have events
        if not self._events:
            self.fetch_events()

        # Check each event
        for event in self._events:
            event_time = event.get("time")
            if not event_time:
                continue

            # Check if within block window
            window = timedelta(minutes=self.block_window)

            if event_time - window <= check_time <= event_time + window:
                self.logger.info(
                    f"News block active: {event.get('currency')} - {event.get('event')} "
                    f"at {event_time.strftime('%H:%M')}"
                )
                return True

        return False

    def get_upcoming_events(self, hours: int = 24) -> List[Dict]:
        """Get upcoming high-impact events within specified hours"""
        now = datetime.now()
        end_time = now + timedelta(hours=hours)

        upcoming = []
        for event in self._events:
            event_time = event.get("time")
            if event_time and now <= event_time <= end_time:
                upcoming.append(event)

        return sorted(upcoming, key=lambda x: x.get("time", datetime.max))

    def get_status(self) -> Dict:
        """Get news guard status"""
        return {
            "enabled": self.enabled,
            "block_window_minutes": self.block_window,
            "total_events": len(self._events),
            "last_fetch": self._last_fetch.isoformat() if self._last_fetch else None,
            "currently_blocked": self.is_blocked(),
            "upcoming_24h": len(self.get_upcoming_events(24)),
        }
