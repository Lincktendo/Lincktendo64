# =============================================================
# data_loader.py — Carga archivos MP3 del staging
# Si algo falla al leer un archivo, lo salta silenciosamente
# =============================================================

import os
import base64
import pandas as pd
from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from config import STAGING_DIR, FINAL_DIR

AUDIO_EXTS = (".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav")


def load_data() -> pd.DataFrame:
    """
    Escanea STAGING_DIR y devuelve un DataFrame con todos los MP3.
    También precarga géneros desde FINAL_DIR para sugerencias.
    """
    files_data = []
    genre_lookup = {}

    # ── Pre-cargar géneros ya existentes en la librería ──────────────
    if os.path.exists(FINAL_DIR):
        for artist_name in os.listdir(FINAL_DIR):
            artist_path = os.path.join(FINAL_DIR, artist_name)
            if not os.path.isdir(artist_path):
                continue
            for root, _, files in os.walk(artist_path):
                for f in files:
                    if not f.lower().endswith(AUDIO_EXTS):
                        continue
                    try:
                        audio = MutagenFile(os.path.join(root, f), easy=True)
                        if audio is None:
                            continue
                        genre = (audio.get("genre") or [""])[0].strip()
                        if genre:
                            genre_lookup[artist_name] = genre
                            break
                    except:
                        continue
                if artist_name in genre_lookup:
                    break

    # ── Escanear staging ─────────────────────────────────────────────
    row_id = 0
    if os.path.exists(STAGING_DIR):
        for root, _, files in os.walk(STAGING_DIR):
            for f in files:
                if not f.endswith(".mp3"):
                    continue
                path = os.path.join(root, f)
                lrc_path = os.path.splitext(path)[0] + ".lrc"
                has_lrc = "✅" if os.path.exists(lrc_path) else "❌"

                try:
                    audio = EasyID3(path)
                    id3   = ID3(path)

                    img_b64 = ""
                    for tag in id3.values():
                        if isinstance(tag, APIC):
                            img_b64 = (
                                f"data:image/jpeg;base64,"
                                f"{base64.b64encode(tag.data).decode('utf-8')}"
                            )
                            break

                    artist       = audio.get("artist",      [""])[0].replace(",", ";")
                    album_artist = audio.get("albumartist", [""])[0].replace(",", ";")

                    files_data.append({
                        "row_id":          row_id,
                        "Portada":         img_b64,
                        "path":            path,
                        "folder":          root,
                        "artist_folder":   os.path.basename(os.path.dirname(os.path.dirname(path))),
                        "Artista":         artist,
                        "Album Artist":    album_artist,
                        "Album":           audio.get("album",       [""])[0],
                        "Track":           audio.get("tracknumber", [""])[0] or "01",
                        "Disc":            audio.get("discnumber",  [""])[0] or "01",
                        "Genre":           audio.get("genre",       [""])[0] or genre_lookup.get(artist, ""),
                        "Título (Metadata)": audio.get("title",    [""])[0],
                        "Letra":           has_lrc,
                    })
                    row_id += 1
                except:
                    continue

    return pd.DataFrame(files_data)
