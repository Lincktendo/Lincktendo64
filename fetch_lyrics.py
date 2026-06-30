# =============================================================
# fetch_lyrics.py — Busca letras en LRCLIB para una carpeta
#
# Uso desde Streamlit : import fetch_lyrics; fetch_lyrics.run(carpeta, slots)
# Uso desde terminal  : python fetch_lyrics.py /data/staging/Justice/Cross
# =============================================================

import os
import sys
import time
import requests
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3

LRCLIB_URL   = "https://lrclib.net/api/get"
CHECKED_FILE = "/data/.lyrics_checked.txt"   # persiste entre sesiones


# ─────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────

def _metadata(path: str) -> tuple:
    """Retorna (title, artist, album, duration_seg) desde el ID3 del mp3."""
    try:
        tags = EasyID3(path)
        info = MP3(path).info
        title    = tags.get("title",       [""])[0]
        artist   = tags.get("artist",      [""])[0] or tags.get("albumartist", [""])[0]
        album    = tags.get("album",        [""])[0]
        duration = int(info.length)
        return title, artist, album, duration
    except:
        return "", "", "", 0


def _query_lrclib(title: str, artist: str, album: str, duration: int) -> tuple:
    """
    Consulta LRCLIB y retorna (lyrics_text, tipo).
    tipo puede ser: 'synced' | 'plain' | 'not_found' | 'error'
    """
    try:
        resp = requests.get(
            LRCLIB_URL,
            params={"track_name": title, "artist_name": artist,
                    "album_name": album, "duration": duration},
            headers={"Lrclib-Client": "fetch_lyrics/2.0 (navidrome-nas)"},
            timeout=15,
        )
        if resp.status_code == 404:
            return None, "not_found"
        if resp.status_code != 200:
            return None, "error"

        data   = resp.json()
        synced = (data.get("syncedLyrics") or "").strip()
        plain  = (data.get("plainLyrics")  or "").strip()

        if synced and synced != "null":
            return synced, "synced"
        if plain and plain != "null":
            return plain, "plain"
        return None, "not_found"

    except Exception:
        return None, "error"


# ─────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────

def run(folder: str, slot_header=None, slot_title=None, slot_bar=None, slot_detail=None):
    """
    Busca letras para todos los mp3 en `folder`.

    Parámetros opcionales de Streamlit (si se omiten → imprime a stdout):
        slot_header  → st.empty() para el encabezado
        slot_title   → st.empty() para el nombre de la canción
        slot_bar     → st.empty() para la barra de progreso
        slot_detail  → st.empty() para el detalle (contadores)
    """

    # ── Cargar lista de canciones ya revisadas ────────────────
    checked = set()
    if os.path.exists(CHECKED_FILE):
        with open(CHECKED_FILE, "r", encoding="utf-8") as f:
            checked = {line.strip() for line in f if line.strip()}

    # ── Recopilar MP3s de la carpeta ──────────────────────────
    mp3s = sorted(
        os.path.join(root, f)
        for root, _, files in os.walk(folder)
        for f in files
        if f.lower().endswith(".mp3")
    )
    total = len(mp3s)

    if total == 0:
        _ui(slot_header, "### ⚠️ No se encontraron MP3s en la carpeta")
        return

    # ── Contadores ────────────────────────────────────────────
    found = skipped = failed = errors = 0

    # ── Loop principal ────────────────────────────────────────
    for i, path in enumerate(mp3s):

        # Barra de progreso
        overall = i / total
        if slot_bar:
            slot_bar.progress(overall)
        if slot_header:
            slot_header.markdown(f"### 📋 Buscando letras — {i + 1} / {total}")

        # Skip si ya tiene .lrc
        lrc_path = os.path.splitext(path)[0] + ".lrc"
        if os.path.exists(lrc_path):
            skipped += 1
            _detail(slot_detail, found, failed, skipped, errors)
            continue

        # Leer metadata
        title, artist, album, duration = _metadata(path)
        if not title or not artist:
            _ui(slot_title, f"↳  SKIP (sin metadata): {os.path.basename(path)}")
            skipped += 1
            _detail(slot_detail, found, failed, skipped, errors)
            continue

        # Skip si ya se intentó y no se encontró
        song_key = f"{artist}|||{title}"
        if song_key in checked:
            skipped += 1
            _detail(slot_detail, found, failed, skipped, errors)
            continue

        # Mostrar canción actual
        _ui(slot_title, f"↳  {artist} — {title}")

        # Consultar LRCLIB
        lyrics, status = _query_lrclib(title, artist, album, duration)

        if status in ("synced", "plain"):
            with open(lrc_path, "w", encoding="utf-8") as f:
                f.write(lyrics)
            found += 1
        elif status == "not_found":
            checked.add(song_key)
            failed += 1
        else:
            errors += 1

        _detail(slot_detail, found, failed, skipped, errors)
        time.sleep(0.5)

    # ── Guardar canciones revisadas ───────────────────────────
    with open(CHECKED_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(checked))

    # ── Finalizar UI ──────────────────────────────────────────
    if slot_bar:
        slot_bar.progress(1.0)
    if slot_header:
        slot_header.markdown(
            f"### ✅ Letras listas — "
            f"{found} encontradas · {failed} no disponibles · {skipped} ya tenían"
        )
    if slot_title:
        slot_title.empty()

    return {"found": found, "skipped": skipped, "failed": failed, "errors": errors}


# ─────────────────────────────────────────────────────────────
# Helpers de UI (funcionan tanto en Streamlit como en terminal)
# ─────────────────────────────────────────────────────────────

def _ui(slot, text: str):
    if slot:
        slot.markdown(text) if text.startswith("#") else slot.caption(text)
    else:
        print(text)


def _detail(slot, found, failed, skipped, errors):
    msg = f"✅ {found} encontradas · ❌ {failed} no disponibles · ⏭ {skipped} saltadas"
    if errors:
        msg += f" · ⚠️ {errors} errores"
    if slot:
        slot.caption(msg)
    else:
        print(msg)


# ─────────────────────────────────────────────────────────────
# Uso desde terminal
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python fetch_lyrics.py /ruta/a/carpeta")
        sys.exit(1)

    folder = sys.argv[1]
    print(f"Buscando letras en: {folder}")
    result = run(folder)
    print(f"Resultado final: {result}")
