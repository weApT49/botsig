"""
Settings Manager for Telegram Bot
Handles loading, saving, and validating configuration changes
"""

import yaml
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass


CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "settings.yaml"


@dataclass
class SettingDef:
    """Definition of a configurable setting"""
    key: str                    # Dot-notation path (e.g., "risk.risk_per_trade_pct")
    label: str                  # Display label
    setting_type: str           # "float", "int", "bool", "list", "string", "select"
    min_val: Optional[float] = None
    max_val: Optional[float] = None
    options: Optional[List[str]] = None  # For select type
    step: Optional[float] = None       # For numeric increment
    description: str = ""

    def __post_init__(self):
        # Ensure all fields are properly set
        pass


# =============================================================================
# SETTING DEFINITIONS - Add new settings here
# =============================================================================

SETTINGS_DEFINITIONS: Dict[str, List[SettingDef]] = {
    "Risk Management": [
        SettingDef(key="risk.capital_usc", label="Capital (USC)", setting_type="int", min_val=100, max_val=1000000, step=100,
                   description="Account capital in USC (cent account units)"),
        SettingDef(key="risk.risk_per_trade_pct", label="Risk per Trade (%)", setting_type="float", min_val=0.1, max_val=5.0, step=0.1,
                   description="Percentage of capital to risk per trade"),
        SettingDef(key="risk.max_risk_per_trade_pct", label="Max Risk per Trade (%)", setting_type="float", min_val=0.1, max_val=5.0, step=0.1,
                   description="Maximum allowed risk per trade"),
        SettingDef(key="risk.max_daily_losses", label="Max Daily Losses", setting_type="int", min_val=1, max_val=10,
                   description="Circuit breaker: max losing trades per day"),
        SettingDef(key="risk.max_daily_drawdown_pct", label="Max Daily Drawdown (%)", setting_type="float", min_val=0.5, max_val=10.0, step=0.5,
                   description="Circuit breaker: max daily drawdown percentage"),
    ],

    "Signal Settings": [
        SettingDef(key="signal.ttl_minutes", label="Signal TTL (minutes)", setting_type="int", min_val=5, max_val=480, step=5,
                   description="Signal time-to-live / expiration"),
        SettingDef(key="signal.cooldown_minutes", label="Cooldown (minutes)", setting_type="int", min_val=1, max_val=120, step=1,
                   description="Minimum time between signals on same pair"),
        SettingDef(key="signal.default_mode", label="Default Order Mode", setting_type="select", options=["limit", "market"],
                   description="Default order type for signals"),
    ],

    "Symbols & Timeframes": [
        SettingDef(key="symbols", label="Trading Symbols", setting_type="list",
                   description="List of symbols to trade (configured in YAML)"),
        SettingDef(key="signal.timeframes", label="Timeframes", setting_type="list",
                   description="Timeframes to analyze"),
    ],

    "Spread & Buffer": [
        SettingDef(key="spread.mode_a_buffer_pips", label="MT5 Mode Buffer (pips)", setting_type="float", min_val=0.0, max_val=20.0, step=0.5,
                   description="Extra spread buffer for MT5 terminal mode"),
        SettingDef(key="spread.mode_b_buffer_pips", label="API Mode Buffer (pips)", setting_type="float", min_val=0.0, max_val=50.0, step=0.5,
                   description="Extra spread buffer for external API mode (larger)"),
        SettingDef(key="spread.max_allowed_spread_pips", label="Max Allowed Spread (pips)", setting_type="float", min_val=1.0, max_val=100.0, step=0.5,
                   description="Skip signal if spread exceeds this"),
    ],

    "News Filter": [
        SettingDef(key="news.enabled", label="Enable News Filter", setting_type="bool",
                   description="Block signals around high-impact news"),
        SettingDef(key="news.block_window_minutes", label="Block Window (minutes)", setting_type="int", min_val=5, max_val=120, step=5,
                   description="Minutes to block before/after high-impact news"),
        SettingDef(key="news.impact_levels", label="Block Impact Levels", setting_type="list",
                   description="News impact levels to block (High, Medium, Low)"),
    ],

    "ATR Volatility Filter": [
        SettingDef(key="atr.enabled", label="Enable ATR Filter", setting_type="bool",
                   description="Filter signals based on volatility"),
        SettingDef(key="atr.period", label="ATR Period", setting_type="int", min_val=5, max_val=50,
                   description="ATR calculation period"),
        SettingDef(key="atr.min_atr_multiplier", label="Min ATR Multiplier", setting_type="float", min_val=0.1, max_val=2.0, step=0.1,
                   description="Skip if ATR < multiplier * average"),
        SettingDef(key="atr.max_atr_multiplier", label="Max ATR Multiplier", setting_type="float", min_val=1.0, max_val=10.0, step=0.1,
                   description="Skip if ATR > multiplier * average (too volatile)"),
    ],

    "Data Feed": [
        SettingDef(key="data_feed.default_mode", label="Data Feed Mode", setting_type="select", options=["mt5", "api", "synthetic"],
                   description="Data source: mt5 (terminal), api (Yahoo), synthetic (testing)"),
        SettingDef(key="data_feed.api.provider", label="API Provider", setting_type="select", options=["yahoo", "twelvedata"],
                   description="External API provider"),
        SettingDef(key="data_feed.api.rate_limit_delay", label="API Rate Limit Delay (s)", setting_type="float", min_val=0.1, max_val=5.0, step=0.1,
                   description="Delay between API calls"),
    ],

    "Schedule": [
        SettingDef(key="schedule.poll_interval_seconds", label="Poll Interval (seconds)", setting_type="int", min_val=30, max_val=3600, step=30,
                   description="How often to check for signals"),
        SettingDef(key="schedule.trading_hours.start", label="Trading Start", setting_type="string",
                   description="Trading session start (HH:MM)"),
        SettingDef(key="schedule.trading_hours.end", label="Trading End", setting_type="string",
                   description="Trading session end (HH:MM)"),
    ],

    "Telegram": [
        SettingDef(key="telegram.bot_token", label="Bot Token", setting_type="string",
                   description="Telegram bot token (restart required)"),
        SettingDef(key="telegram.chat_id", label="Chat ID", setting_type="string",
                   description="Telegram chat ID (restart required)"),
        SettingDef(key="telegram.parse_mode", label="Parse Mode", setting_type="select", options=["Markdown", "MarkdownV2", "HTML"],
                   description="Message parse mode"),
    ],
}


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_config(config: Dict[str, Any]) -> bool:
    """Save configuration to YAML file"""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False


def get_nested(config: Dict, key: str) -> Any:
    """Get nested value using dot notation (e.g., 'risk.capital_usc')"""
    keys = key.split(".")
    val = config
    for k in keys:
        if isinstance(val, dict):
            val = val.get(k)
        else:
            return None
    return val


def set_nested(config: Dict, key: str, value: Any) -> bool:
    """Set nested value using dot notation"""
    keys = key.split(".")
    val = config
    for k in keys[:-1]:
        if k not in val:
            val[k] = {}
        val = val[k]
    val[keys[-1]] = value
    return True


def validate_value(defn: SettingDef, value: Any) -> Tuple[bool, str]:
    """Validate a value against its definition"""
    try:
        if defn.setting_type == "int":
            value = int(value)
            if defn.min_val is not None and value < defn.min_val:
                return False, f"Must be >= {defn.min_val}"
            if defn.max_val is not None and value > defn.max_val:
                return False, f"Must be <= {defn.max_val}"

        elif defn.setting_type == "float":
            value = float(value)
            if defn.min_val is not None and value < defn.min_val:
                return False, f"Must be >= {defn.min_val}"
            if defn.max_val is not None and value > defn.max_val:
                return False, f"Must be <= {defn.max_val}"

        elif defn.setting_type == "bool":
            if isinstance(value, str):
                value = value.lower() in ("true", "1", "yes", "on", "enable")
            value = bool(value)

        elif defn.setting_type == "select":
            if defn.options and value not in defn.options:
                return False, f"Must be one of: {', '.join(defn.options)}"

        elif defn.setting_type == "list":
            if isinstance(value, str):
                value = [v.strip() for v in value.split(",") if v.strip()]
            if not isinstance(value, list):
                return False, "Must be a list"

        elif defn.setting_type == "string":
            value = str(value)
            if defn.key.endswith(".start") or defn.key.endswith(".end"):
                # Validate time format HH:MM
                parts = value.split(":")
                if len(parts) != 2:
                    return False, "Format must be HH:MM"
                h, m = int(parts[0]), int(parts[1])
                if not (0 <= h <= 23 and 0 <= m <= 59):
                    return False, "Invalid time (00:00-23:59)"

        return True, ""
    except Exception as e:
        return False, str(e)


def format_value(defn: SettingDef, value: Any) -> str:
    """Format value for display"""
    if defn.setting_type == "bool":
        return "✅ ON" if value else "❌ OFF"
    elif defn.setting_type == "list":
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)
    elif defn.setting_type == "float":
        return f"{value:.2f}" if isinstance(value, float) else str(value)
    return str(value)


def get_settings_menu(config: Dict) -> str:
    """Generate settings overview text"""
    lines = ["⚙️ <b>Settings Overview</b>\n"]

    for category, settings in SETTINGS_DEFINITIONS.items():
        lines.append(f"\n<b>{category}</b>")
        for s in settings:
            val = get_nested(config, s.key)
            if val is not None:
                lines.append(f"  • {s.label}: <code>{format_value(s, val)}</code>")
            else:
                lines.append(f"  • {s.label}: <i>not set</i>")

    return "\n".join(lines)


def get_category_keyboard(category: str, config: Dict) -> List[List[Dict]]:
    """Generate inline keyboard for a category"""
    keyboard = []
    settings = SETTINGS_DEFINITIONS.get(category, [])

    for s in settings:
        val = get_nested(config, s.key)
        display = format_value(s, val) if val is not None else "?"
        # Truncate long values
        if len(display) > 25:
            display = display[:22] + "..."
        keyboard.append([{
            "text": f"{s.label}: {display}",
            "callback_data": f"edit:{s.key}"
        }])

    keyboard.append([{"text": "« Back to Categories", "callback_data": "settings:categories"}])
    return keyboard


def get_categories_keyboard() -> List[List[Dict]]:
    """Generate main categories keyboard"""
    keyboard = []
    for cat in SETTINGS_DEFINITIONS.keys():
        keyboard.append([{"text": cat, "callback_data": f"settings:cat:{cat}"}])
    keyboard.append([{"text": "🔄 Reload Config", "callback_data": "settings:reload"}])
    keyboard.append([{"text": "✅ Done", "callback_data": "settings:done"}])
    return keyboard


def get_edit_keyboard(key: str, defn: SettingDef, config: Dict) -> List[List[Dict]]:
    """Generate keyboard for editing a specific setting"""
    keyboard = []

    if defn.setting_type == "bool":
        keyboard.append([
            {"text": "✅ Enable", "callback_data": f"set:{key}:true"},
            {"text": "❌ Disable", "callback_data": f"set:{key}:false"}
        ])
    elif defn.setting_type == "select":
        for opt in defn.options or []:
            current = get_nested(config, key)
            prefix = "✓ " if opt == current else ""
            keyboard.append([{"text": f"{prefix}{opt}", "callback_data": f"set:{key}:{opt}"}])
    elif defn.setting_type in ("int", "float"):
        # Quick adjust buttons
        step = defn.step or (1 if defn.setting_type == "int" else 0.1)
        current = get_nested(config, key) or 0
        keyboard.append([
            {"text": f"➖ -{step}", "callback_data": f"adj:{key}:-{step}"},
            {"text": f"➕ +{step}", "callback_data": f"adj:{key}:+{step}"}
        ])
        keyboard.append([{"text": "✏️ Enter Custom Value", "callback_data": f"input:{key}"}])
    elif defn.setting_type == "list":
        keyboard.append([{"text": "✏️ Enter Comma-Separated", "callback_data": f"input:{key}"}])
    elif defn.setting_type == "string":
        keyboard.append([{"text": "✏️ Enter Value", "callback_data": f"input:{key}"}])

    keyboard.append([{"text": "« Back", "callback_data": f"settings:cat:{_find_category(key)}"}])
    return keyboard


def _find_category(key: str) -> str:
    """Find which category a setting key belongs to"""
    for cat, settings in SETTINGS_DEFINITIONS.items():
        for s in settings:
            if s.key == key:
                return cat
    return "Risk Management"


def apply_setting(config: Dict, key: str, value: Any) -> Tuple[bool, str]:
    """Apply a setting change with validation"""
    # Find definition
    defn = None
    for settings in SETTINGS_DEFINITIONS.values():
        for s in settings:
            if s.key == key:
                defn = s
                break
        if defn:
            break

    if not defn:
        return False, f"Unknown setting: {key}"

    # Validate
    ok, err = validate_value(defn, value)
    if not ok:
        return False, err

    # Convert type
    if defn.setting_type == "int":
        value = int(value)
    elif defn.setting_type == "float":
        value = float(value)
    elif defn.setting_type == "bool":
        if isinstance(value, str):
            value = value.lower() in ("true", "1", "yes", "on", "enable")
        value = bool(value)
    elif defn.setting_type == "list" and isinstance(value, str):
        value = [v.strip() for v in value.split(",") if v.strip()]

    # Apply
    set_nested(config, key, value)
    return True, ""