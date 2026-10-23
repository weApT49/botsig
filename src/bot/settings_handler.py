"""
Interactive Settings Handler for Telegram Bot
Adds inline keyboard-based settings editing to TelegramBot
"""

import json
import threading
from typing import Dict, Optional, Callable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .telegram_bot import TelegramBot

from .settings_manager import (
    load_config, save_config, get_nested, set_nested,
    SETTINGS_DEFINITIONS, get_categories_keyboard, get_category_keyboard,
    get_edit_keyboard, apply_setting, _find_category, format_value, get_settings_menu
)


# =============================================================================
# SETTINGS STATE MACHINE
# =============================================================================

class SettingsState:
    """Manages per-user settings interaction state"""
    def __init__(self):
        self.category: Optional[str] = None
        self.editing_key: Optional[str] = None
        self.waiting_input: bool = False


# Store state per chat_id
_user_states: Dict[str, SettingsState] = {}


def get_state(chat_id: str) -> SettingsState:
    """Get or create user state"""
    if chat_id not in _user_states:
        _user_states[chat_id] = SettingsState()
    return _user_states[chat_id]


def clear_state(chat_id: str):
    """Clear user state"""
    if chat_id in _user_states:
        del _user_states[chat_id]


# =============================================================================
# EXTENSION METHODS FOR TelegramBot
# =============================================================================

def extend_telegram_bot(bot: "TelegramBot"):
    """Add settings functionality to TelegramBot instance"""

    # Add settings command handler
    bot._commands["settings"] = _cmd_settings
    bot._commands["config"] = _cmd_settings  # Alias

    # Add callback handlers
    bot._callbacks.update({
        "settings:categories": _cb_settings_categories,
        "settings:cat:": _cb_settings_category,  # Prefix match
        "settings:reload": _cb_settings_reload,
        "settings:done": _cb_settings_done,
        "edit:": _cb_edit_setting,  # Prefix match
        "set:": _cb_set_value,  # Prefix match
        "adj:": _cb_adjust_value,  # Prefix match
        "input:": _cb_request_input,  # Prefix match
    })

    # Store reference to handle text input during editing
    bot._handle_settings_text = _handle_settings_text

    # Override _handle_message to intercept text input
    original_handle_message = bot._handle_message

    def wrapped_handle_message(message: Dict):
        chat_id = str(message.get("chat", {}).get("id", ""))
        text = message.get("text", "")

        state = get_state(chat_id)
        if state.waiting_input and state.editing_key and not text.startswith("/"):
            # Handle settings value input
            bot._handle_settings_text(chat_id, text, state)
            return

        original_handle_message(message)

    bot._handle_message = wrapped_handle_message

    # Add prefix callback matching
    original_handle_callback = bot._handle_callback

    def wrapped_handle_callback(callback: Dict):
        data = callback.get("data", "")

        # Check prefix matches
        for prefix, handler in [
            ("settings:cat:", _cb_settings_category),
            ("edit:", _cb_edit_setting),
            ("set:", _cb_set_value),
            ("adj:", _cb_adjust_value),
            ("input:", _cb_request_input),
        ]:
            if data.startswith(prefix):
                chat_id = str(callback.get("message", {}).get("chat", {}).get("id", ""))
                bot._answer_callback(callback.get("id"))
                handler(bot, chat_id, data)
                return

        original_handle_callback(callback)

    bot._handle_callback = wrapped_handle_callback


# =============================================================================
# COMMAND HANDLERS
# =============================================================================

def _cmd_settings(bot: "TelegramBot", chat_id: str, args: list):
    """Handle /settings command - show categories"""
    config = load_config()
    text = get_settings_menu(config)
    bot._send_message_with_buttons(chat_id, text, {"inline_keyboard": get_categories_keyboard()})


# =============================================================================
# CALLBACK HANDLERS
# =============================================================================

def _cb_settings_categories(bot: "TelegramBot", chat_id: str):
    """Show settings categories"""
    config = load_config()
    text = get_settings_menu(config)
    bot._send_message_with_buttons(chat_id, text, {"inline_keyboard": get_categories_keyboard()})


def _cb_settings_category(bot: "TelegramBot", chat_id: str, data: str):
    """Show settings in a category"""
    category = data[len("settings:cat:"):]
    config = load_config()

    state = get_state(chat_id)
    state.category = category
    state.editing_key = None
    state.waiting_input = False

    text = f"⚙️ <b>{category}</b>\n\nTap a setting to change:"
    bot._send_message_with_buttons(
        chat_id, text,
        {"inline_keyboard": get_category_keyboard(category, config)},
        parse_mode="HTML"
    )


def _cb_settings_reload(bot: "TelegramBot", chat_id: str):
    """Reload config from disk"""
    config = load_config()
    text = "🔄 Configuration reloaded from disk.\n\n" + get_settings_menu(config)
    bot._send_message_with_buttons(chat_id, text, {"inline_keyboard": get_categories_keyboard()}, parse_mode="HTML")


def _cb_settings_done(bot: "TelegramBot", chat_id: str):
    """Close settings menu"""
    clear_state(chat_id)
    bot._send_message(chat_id, "✅ Settings closed. Use /settings to open again.")


def _cb_edit_setting(bot: "TelegramBot", chat_id: str, data: str):
    """Show edit options for a setting"""
    key = data[len("edit:"):]

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
        bot._send_message(chat_id, f"❌ Unknown setting: {key}")
        return

    config = load_config()
    current = get_nested(config, key)

    state = get_state(chat_id)
    state.editing_key = key
    state.waiting_input = False

    text = (
        f"✏️ <b>Edit: {defn.label}</b>\n\n"
        f"Current: <code>{format_value(defn, current) if current is not None else 'not set'}</code>\n\n"
        f"{defn.description}"
    )

    bot._send_message_with_buttons(
        chat_id, text,
        {"inline_keyboard": get_edit_keyboard(key, defn, config)},
        parse_mode="HTML"
    )


def _cb_set_value(bot: "TelegramBot", chat_id: str, data: str):
    """Set a value directly (for bool/select)"""
    # Format: set:key:value
    parts = data[len("set:"):].split(":", 1)
    if len(parts) != 2:
        return
    key, value_str = parts

    config = load_config()

    # Convert value
    defn = None
    for settings in SETTINGS_DEFINITIONS.values():
        for s in settings:
            if s.key == key:
                defn = s
                break
        if defn:
            break

    if defn and defn.setting_type == "bool":
        value = value_str.lower() in ("true", "1", "yes", "on", "enable")
    elif defn and defn.setting_type == "select":
        value = value_str
    else:
        value = value_str

    ok, err = apply_setting(config, key, value)
    if ok:
        save_config(config)
        bot._send_message(chat_id, f"✅ <b>{defn.label}</b> updated to <code>{format_value(defn, value)}</code>", parse_mode="HTML")
        # Refresh category view
        cat = _find_category(key)
        _cb_settings_category(bot, chat_id, f"settings:cat:{cat}")
    else:
        bot._send_message(chat_id, f"❌ Error: {err}")


def _cb_adjust_value(bot: "TelegramBot", chat_id: str, data: str):
    """Adjust numeric value up/down"""
    # Format: adj:key:+step or adj:key:-step
    parts = data[len("adj:"):].split(":", 1)
    if len(parts) != 2:
        return
    key, step_str = parts

    config = load_config()
    current = get_nested(config, key)

    if current is None:
        bot._send_message(chat_id, "❌ No current value")
        return

    try:
        step = float(step_str)
        new_val = current + step

        # Find definition for validation
        defn = None
        for settings in SETTINGS_DEFINITIONS.values():
            for s in settings:
                if s.key == key:
                    defn = s
                    break
            if defn:
                break

        if defn:
            # Check bounds
            if defn.min_val is not None and new_val < defn.min_val:
                new_val = defn.min_val
            if defn.max_val is not None and new_val > defn.max_val:
                new_val = defn.max_val

            # Round appropriately
            if defn.setting_type == "int":
                new_val = int(round(new_val))
            else:
                new_val = round(new_val, 2)

        ok, err = apply_setting(config, key, new_val)
        if ok:
            save_config(config)
            bot._send_message(chat_id, f"✅ <b>{defn.label}</b> → <code>{format_value(defn, new_val)}</code>", parse_mode="HTML")
            cat = _find_category(key)
            _cb_settings_category(bot, chat_id, f"settings:cat:{cat}")
        else:
            bot._send_message(chat_id, f"❌ Error: {err}")
    except Exception as e:
        bot._send_message(chat_id, f"❌ Error: {e}")


def _cb_request_input(bot: TelegramBot, chat_id: str, data: str):
    """Request text input for a setting"""
    key = data[len("input:"):]

    defn = None
    for settings in SETTINGS_DEFINITIONS.values():
        for s in settings:
            if s.key == key:
                defn = s
                break
        if defn:
            break

    if not defn:
        bot._send_message(chat_id, f"❌ Unknown setting: {key}")
        return

    state = get_state(chat_id)
    state.editing_key = key
    state.waiting_input = True

    # Show format hint
    hint = ""
    if defn.setting_type == "list":
        hint = "\n\n<i>Format: comma-separated (e.g., M15,H1,H4)</i>"
    elif defn.setting_type == "string" and (key.endswith(".start") or key.endswith(".end")):
        hint = "\n\n<i>Format: HH:MM (24-hour)</i>"
    elif defn.setting_type == "float":
        hint = f"\n\n<i>Range: {defn.min_val} - {defn.max_val}</i>"
    elif defn.setting_type == "int":
        hint = f"\n\n<i>Range: {defn.min_val} - {defn.max_val}</i>"

    text = (
        f"✏️ <b>Enter new value for {defn.label}</b>{hint}\n\n"
        f"Current: <code>{format_value(defn, get_nested(load_config(), key))}</code>\n\n"
        f"Send /cancel to abort"
    )

    bot._send_message(chat_id, text, parse_mode="HTML")


def _handle_settings_text(bot: TelegramBot, chat_id: str, text: str, state: SettingsState):
    """Handle text input for setting value"""
    key = state.editing_key
    if not key:
        return

    config = load_config()

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
        bot._send_message(chat_id, f"❌ Unknown setting: {key}")
        clear_state(chat_id)
        return

    # Handle cancel
    if text.strip().lower() == "/cancel":
        clear_state(chat_id)
        cat = _find_category(key)
        _cb_settings_category(bot, chat_id, f"settings:cat:{cat}")
        return

    # Apply
    ok, err = apply_setting(config, key, text.strip())
    if ok:
        save_config(config)
        bot._send_message(chat_id, f"✅ <b>{defn.label}</b> updated to <code>{format_value(defn, get_nested(config, key))}</code>", parse_mode="HTML")
        cat = _find_category(key)
        clear_state(chat_id)
        _cb_settings_category(bot, chat_id, f"settings:cat:{cat}")
    else:
        bot._send_message(chat_id, f"❌ Invalid value: {err}\n\nTry again or send /cancel")


# =============================================================================
# LIVE RELOAD NOTIFICATION
# =============================================================================

def notify_config_changed(bot: TelegramBot, chat_id: str, changed_keys: list):
    """Notify user that config was changed externally"""
    if not changed_keys:
        return

    lines = ["⚠️ <b>Configuration Updated</b>\n\nThe following settings were changed:"]
    config = load_config()

    for key in changed_keys:
        defn = None
        for settings in SETTINGS_DEFINITIONS.values():
            for s in settings:
                if s.key == key:
                    defn = s
                    break
            if defn:
                break

        if defn:
            val = get_nested(config, key)
            lines.append(f"  • {defn.label}: <code>{format_value(defn, val)}</code>")
        else:
            lines.append(f"  • {key}")

    lines.append("\nUse /settings to view all settings.")
    bot._send_message(chat_id, "\n".join(lines), parse_mode="HTML")