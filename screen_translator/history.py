"""Study history management with structured JSON storage."""

import os
import json
import logging
import uuid
from datetime import datetime

log = logging.getLogger(__name__)

HISTORY_DIR = os.path.join(os.path.expanduser("~"), ".config", "screen-translator")
HISTORY_FILE = os.path.join(HISTORY_DIR, "history.json")


def load_history():
    """Load translation history list from JSON file."""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.error("Failed to load history JSON: %s", e)
        return []


def save_translation(original, translated, source_lang, target_lang):
    """Save a translation entry to the structured JSON history."""
    try:
        os.makedirs(HISTORY_DIR, exist_ok=True)
        history = load_history()
        
        # Avoid duplicate consecutive entries
        if history and history[0]["original"] == original and history[0]["translated"] == translated:
            return True
            
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "original": original.strip(),
            "translated": translated.strip(),
            "source": source_lang,
            "target": target_lang
        }
        
        # Prepend to show newest first
        history.insert(0, entry)
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
            
        log.info("Saved translation to history: %.40s", original)
        return True
    except Exception as e:
        log.error("Failed to save translation history: %s", e)
        return False


def delete_entry(entry_id):
    """Delete a specific entry from the history by its ID."""
    try:
        history = load_history()
        updated_history = [item for item in history if item["id"] != entry_id]
        
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(updated_history, f, indent=2, ensure_ascii=False)
            
        log.info("Deleted history entry: %s", entry_id)
        return True
    except Exception as e:
        log.error("Failed to delete history entry: %s", e)
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
