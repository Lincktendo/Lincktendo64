# =============================================================
# config.py — Constantes globales de la app
# =============================================================

import json
import os

STAGING_DIR           = "/data/staging/"
FINAL_DIR             = "/data/library/"
LASTFM_API_KEY        = ""   # ← se configura en ⚙️ Settings
PATH_TO_LYRICS_SCRIPT = "/opt/cronicle/scripts/fetch_lyrics.sh"

SETTINGS_FILE = "/data/ingest_system/settings.json"

DEFAULTS = {
    "staging_dir":    STAGING_DIR,
    "library_dir":    FINAL_DIR,
    "lastfm_api_key": "",
    "language":       "en",
}


def load_settings() -> dict:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return DEFAULTS.copy()


def save_settings(s: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
