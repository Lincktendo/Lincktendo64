# =============================================================
# i18n.py — Translation helper
# Usage: from i18n import t
#        t("key")  or  t("key", var=value)
# =============================================================

import json
import os
import streamlit as st

_LANG_DIR = os.path.join(os.path.dirname(__file__), "lang")
_cache: dict[str, dict] = {}


def _load(lang: str) -> dict:
    if lang not in _cache:
        path = os.path.join(_LANG_DIR, f"{lang}.json")
        fallback = os.path.join(_LANG_DIR, "en.json")
        try:
            with open(path, encoding="utf-8") as f:
                _cache[lang] = json.load(f)
        except FileNotFoundError:
            with open(fallback, encoding="utf-8") as f:
                _cache[lang] = json.load(f)
    return _cache[lang]


def t(key: str, **kwargs) -> str:
    """
    Return the translated string for `key` in the current language.
    Supports format placeholders: t("dl_song_progress", item=3, total=12)
    Falls back to the key itself if not found.
    """
    lang = st.session_state.get("settings", {}).get("language", "en")
    strings = _load(lang)
    text = strings.get(key, key)
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def available_languages() -> dict[str, str]:
    """Returns {code: label} for all available language files."""
    langs = {}
    for f in os.listdir(_LANG_DIR):
        if f.endswith(".json"):
            code = f[:-5]
            # Read the native name if present, else use code
            try:
                with open(os.path.join(_LANG_DIR, f), encoding="utf-8") as fp:
                    data = json.load(fp)
                langs[code] = data.get("_language_name", code.upper())
            except Exception:
                langs[code] = code.upper()
    return langs
