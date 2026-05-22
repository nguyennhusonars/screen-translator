"""Configuration management."""

import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "screen-translator")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "source_language": "auto",      # Default source: Auto-detect
    "target_language": "vi",        # Default target: Vietnamese
    "auto_translate": True,         # Auto-translate on selection
    "popup_timeout": 8,             # Seconds before popup auto-hides (0 = never)
    "min_text_length": 2,           # Minimum chars to trigger translation
    "max_text_length": 5000,        # Maximum chars to translate
    "selection_delay_ms": 600,      # Delay after selection stabilizes before translating
}


def load():
    """Load config, merging with defaults."""
    config = dict(DEFAULTS)
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                user_config = json.load(f)
                config.update(user_config)
    except (json.JSONDecodeError, IOError):
        pass
    return config


def save(config):
    """Save config to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
