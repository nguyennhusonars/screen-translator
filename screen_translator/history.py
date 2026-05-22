"""Study history management."""

import os
import logging
import subprocess
from datetime import datetime

log = logging.getLogger(__name__)

HISTORY_DIR = os.path.join(os.path.expanduser("~"), ".config", "screen-translator")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.md")

HEADER = """# Screen Translator - Study History

This file contains your saved translations for study and review.
You can open this file in any text or Markdown editor.

---
"""


def save_translation(original, translated, source_lang, target_lang):
    """Save a translation entry to the Markdown history file."""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        
        # Write header if file does not exist
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write(HEADER)
                
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"""*   **[{timestamp}]** `{source_lang}` → `{target_lang}`
    *   **Original:** {original.strip()}
    *   **Translation:** {translated.strip()}

---
"""
        with open(HISTORY_FILE, "a", encoding="utf-8") as f:
            f.write(entry)
            
        log.info("Saved translation to history: %.40s", original)
        return True
    except Exception as e:
        log.error("Failed to save translation history: %s", e)
        return False


def open_history():
    """Open the study history file using the default system editor."""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write(HEADER)
                
        # Open in background with xdg-open
        subprocess.Popen(["xdg-open", HISTORY_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log.info("Opened history file: %s", HISTORY_FILE)
        return True
    except Exception as e:
        log.error("Failed to open history file: %s", e)
        return False


def clear_history():
    """Delete or clear the study history file."""
    try:
        if os.path.exists(HISTORY_FILE):
            os.remove(HISTORY_FILE)
        log.info("Cleared history file")
        return True
    except Exception as e:
        log.error("Failed to clear history file: %s", e)
        return False
