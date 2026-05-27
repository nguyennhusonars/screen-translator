"""Translation engine using Google Translate (free, no API key)."""

import logging
import threading
from deep_translator import GoogleTranslator
from deep_translator.constants import GOOGLE_LANGUAGES_TO_CODES
from langdetect import detect, DetectorFactory

# Set seed for reproducible language detection
DetectorFactory.seed = 0

log = logging.getLogger(__name__)


# Cache recent translations to avoid repeated API calls
_cache = {}
_CACHE_MAX = 500


def get_supported_languages():
    """Return dict of {language_name: language_code}."""
    return dict(GOOGLE_LANGUAGES_TO_CODES)


def translate(text, target_lang="vi", source_lang="auto"):
    """
    Translate text. Returns dict with keys:
      - source: detected source language code
      - target: target language code
      - original: original text
      - translated: translated text
      - error: error message if failed, else None
    """
    # Clean up text: replace single newlines with spaces to preserve context, 
    # but keep double newlines for paragraphs.
    text = text.replace('\r\n', '\n').strip()
    # Replace single newlines that are not followed by another newline
    import re
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    # Collapse multiple spaces
    text = re.sub(r' +', ' ', text)

    if not text:
        return None

    cache_key = (text, target_lang, source_lang)
    if cache_key in _cache:
        return _cache[cache_key]

    try:
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        # Detect language if source was 'auto'
        actual_source = source_lang
        if source_lang == "auto":
            try:
                # Use langdetect for faster, reliable local detection
                actual_source = detect(text)
                # Normalize for gTTS (e.g., 'zh-cn' -> 'zh-CN')
                norm_map = {
                    "zh-cn": "zh-CN",
                    "zh-tw": "zh-TW",
                }
                actual_source = norm_map.get(actual_source, actual_source)
                log.info("Detected source language: %s", actual_source)
            except Exception as e:
                log.warning("Language detection failed: %s", e)
                actual_source = "en"

        translator = GoogleTranslator(source=actual_source, target=target_lang)
        translated = translator.translate(text)

        result = {
            "source": actual_source,
            "target": target_lang,
            "original": text,
            "translated": translated or "",
            "error": None,
        }

        # Manage cache size
        if len(_cache) >= _CACHE_MAX:
            # Remove oldest quarter
            keys = list(_cache.keys())
            for k in keys[: _CACHE_MAX // 4]:
                del _cache[k]
        _cache[cache_key] = result
        return result

    except Exception as e:
        return {
            "source": source_lang,
            "target": target_lang,
            "original": text,
            "translated": "",
            "error": str(e),
        }


def translate_async(text, target_lang, callback, source_lang="auto"):
    """Translate in background thread, call callback(result) in the thread."""
    def _work():
        result = translate(text, target_lang, source_lang)
        callback(result)
    t = threading.Thread(target=_work, daemon=True)
    t.start()


def get_definitions(text, target_lang, source_lang="auto"):
    """
    Fetch multiple dictionary meanings from Google Translate API.
    Returns a list of {"pos": str, "terms": [str]} or [] on failure/no data.
    Only meaningful for short inputs (single words or short phrases).
    """
    try:
        import urllib.request
        import json
        import urllib.parse

        sl = source_lang if source_lang != "auto" else "auto"
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx&dj=1"
            f"&sl={urllib.parse.quote(sl)}"
            f"&tl={urllib.parse.quote(target_lang)}"
            "&dt=bd&dt=t"
            f"&q={urllib.parse.quote(text)}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())

        definitions = []
        for entry in data.get("dict", []):
            pos = entry.get("pos", "")
            terms = entry.get("terms", [])[:5]  # Cap at 5 per group
            if pos and terms:
                definitions.append({"pos": pos, "terms": terms})
        return definitions
    except Exception as e:
        log.warning("get_definitions failed: %s", e)
        return []

