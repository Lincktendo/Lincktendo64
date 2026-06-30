# =============================================================
# section_download.py — Sección 1: Descarga profesional
# Lógica: Artista / (Album > Playlist > Título) / Canción
# =============================================================

import re
import time
import subprocess
import shutil
import os
import glob
import streamlit as st
from config import STAGING_DIR, PATH_TO_LYRICS_SCRIPT
from data_loader import load_data

ANIM_STEPS = 8
ANIM_DELAY = 0.04

# ─────────────────────────────────────────────────────────────
# Parser de líneas yt-dlp
# ─────────────────────────────────────────────────────────────

def _parse_line(line: str) -> dict:
    m = re.search(r'Downloading item (\d+) of (\d+)', line)
    if m:
        return {"event": "new_item", "item": int(m.group(1)), "total": int(m.group(2))}

    m = re.search(r'(\d+\.?\d*)%\s+of', line)
    if m:
        extra = {}
        s = re.search(r'at\s+([\d.]+\s*\w+/s)', line)
        e = re.search(r'ETA\s+(\S+)', line)
        if s: extra["speed"] = s.group(1).strip()
        if e: extra["eta"]   = e.group(1)
        return {"event": "progress", "percent": float(m.group(1)), **extra}

    m = re.search(r'(?:thumbnail \d+ to:|Destination:)\s+.+/(?:\d+\s*[-–]\s*)?(.+?)\s*\[\w+\]\.\w+$', line)
    if m:
        return {"event": "title", "title": m.group(1).strip()}

    if line.startswith("ERROR:"):
        return {"event": "error", "message": line}

    return {}

# ─────────────────────────────────────────────────────────────
# Render de UI nativa
# ─────────────────────────────────────────────────────────────

def _render(state, slot_header, slot_title, slot_bar, slot_detail):
    item  = state["item"]
    total = state["total"]

    if total > 0:
        slot_header.markdown(f"### 💿 Canción {item} de {total}")
        overall = ((item - 1) + (state["percent"] / 100.0)) / total
    else:
        slot_header.markdown("### Conectando...")
        overall = 0.0

    if state["title"]:
        slot_title.caption(f"↳  {state['title']}")

    slot_bar.progress(min(overall, 1.0))

    parts = []
    if state["percent"] > 0:
        parts.append(f"Progreso: {state['percent']:.1f}%")
    if state["speed"]:
        parts.append(state["speed"])
    if state["eta"]:
        parts.append(f"ETA {state['eta']}")

    slot_detail.caption(" · ".join(parts) if parts else "")

# ─────────────────────────────────────────────────────────────
# Animación suave
# ─────────────────────────────────────────────────────────────

def _animate(state, from_pct, to_pct, slot_header, slot_title, slot_bar, slot_detail):
    for i in range(1, ANIM_STEPS + 1):
        t = i / ANIM_STEPS
        t_smooth = t * t * (3.0 - 2.0 * t)
        state["percent"] = from_pct + (to_pct - from_pct) * t_smooth
        _render(state, slot_header, slot_title, slot_bar, slot_detail)
        time.sleep(ANIM_DELAY)

# ─────────────────────────────────────────────────────────────
# Render principal
# ─────────────────────────────────────────────────────────────

def render():
    url = st.text_input("Pega el link (Canción o Álbum):")

    if not st.button("Procesar"):
        return

    if not url:
        st.warning("Ingresa una URL.")
        return

    slot_header = st.empty()
    slot_title  = st.empty()
    slot_bar    = st.empty()
    slot_detail = st.empty()
    slot_errors = st.container()

    state = {"item": 0, "total": 0, "percent": 0.0, "title": "", "speed": "", "eta": ""}
    slot_bar.progress(0.0)

    # Snapshot de MP3s existentes ANTES de descargar
    # Para saber exactamente qué carpetas son nuevas al terminar
    mp3s_antes = set(glob.glob(os.path.join(STAGING_DIR, "**", "*.mp3"), recursive=True))

    # Regex mejorado — ahora también atrapa:
    # "Justice (Official)", "Justice [Topic]", "Justice • Music", "Justice – VEVO"
    basura = (
        r"(?i)\s*"
        r"(?:[\(\[\-–—•·]\s*)?"           # separador opcional: (, [, -, –, —, •, ·
        r"(?:Music Group|Entertainment|Various Artists|Productions|"
        r"Official|Records|Channel|Music|VEVO|TV|Topic)"
        r"[\s\)\]]*$"                      # cierre opcional: ), ], espacios al final
    )

    cmd_download = [
        "yt-dlp", "--newline", "-f", "bestaudio/best",
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "--embed-thumbnail", "--embed-metadata", "--convert-thumbnails", "jpg",
        "--no-keep-video",
        "--ppa", "ThumbnailsConvertor:-vf crop=ih:ih",

        # Limpiar uploader — MUY IMPORTANTE (x5)
        "--replace-in-metadata", "uploader", basura, "",            # sufijos: "Justice - Topic", "(Official)", etc.
        "--replace-in-metadata", "uploader", basura, "",            # segunda pasada por si quedó algo
        "--replace-in-metadata", "uploader", r"\s*[\-–—•·]+\s*$", "",   # limpia " - " residual al final
        "--replace-in-metadata", "uploader", r"\s{2,}", " ",       # colapsa espacios dobles
        "--replace-in-metadata", "uploader", r"^\s+|\s+$", "",     # trim espacios al inicio/fin
        "--replace-in-metadata", "uploader", r"^$", "Artista_Desconocido",  # si quedó vacío
        # prefijos: "Official Arctic Monkeys" → "Arctic Monkeys"
        "--replace-in-metadata", "uploader", r"(?i)^\s*(?:Official|The Official|VEVO)\s*[-–]?\s*", "",

        # Limpiar artist — mismo filtro, este es el que se embebe en el ID3 del mp3
        "--replace-in-metadata", "artist", basura, "",
        "--replace-in-metadata", "artist", basura, "",
        "--replace-in-metadata", "artist", r"\s*[\-–—•·]+\s*$", "",
        "--replace-in-metadata", "artist", r"\s{2,}", " ",
        "--replace-in-metadata", "artist", r"^\s+|\s+$", "",
        # prefijos: "Official Arctic Monkeys" → "Arctic Monkeys"
        "--replace-in-metadata", "artist", r"(?i)^\s*(?:Official|The Official|VEVO)\s*[-–]?\s*", "",

        # FIX 2 — Metadata de album:
        # playlist_title tiene el nombre real del álbum en YouTube Music.
        # Lo copiamos a album para que quede embebido en el ID3 del mp3.
        # Si es canción suelta sin playlist, playlist_title viene vacío
        # y YouTube a veces ya trae el tag album correcto → se queda.
        "--parse-metadata", "playlist_title:%(album)s",
        # YouTube Music a veces manda playlist_title como "Album - Cross"
        # → quitamos el prefijo "Album - " (o "album – ", case insensitive)
        "--replace-in-metadata", "album", r"(?i)^[aá]lbum\s*[-–]\s*", "",
        # Limpiar "NA" literal que yt-dlp pone cuando playlist_title no existe
        # (canción suelta sin álbum) — evita que la carpeta se llame "NA"
        "--replace-in-metadata", "album", r"^NA$", "",

        "--parse-metadata", "uploader:%(album_artist)s",
        "--parse-metadata", "playlist_index:%(track_number)s",

        # FIX 3 — Nombre de archivo correcto:
        # %(playlist_index,autonumber)s → usa el índice del álbum si existe,
        # si no (canción suelta) usa autonumber (1, 2, …) como fallback.
        # Así nunca queda "NA" en el nombre.
        "-o", (
            f"{STAGING_DIR}"
            "%(album_artist)s/"
            "%(album,playlist_title,title)s/"
            "%(playlist_index,autonumber)s - %(title)s [%(id)s].%(ext)s"
        ),

        "--download-archive", "/data/staging/archive.txt",

        # FIX 1 — Soportar álbumes Y canciones sueltas:
        # --yes-playlist descarga la playlist entera si la URL es una playlist.
        # Si la URL es de un video suelto (sin ?list=), simplemente descarga ese video.
        "--yes-playlist", "--ignore-errors", url,
    ]

    def _run_yt_dlp(intento: int = 1):
        """Corre yt-dlp y retorna el returncode. Muestra '(intento N)' en header."""
        if intento > 1:
            slot_header.markdown(f"### 🔄 Reintentando descarga (intento {intento})...")
            state.update({"item": 0, "total": 0, "percent": 0.0,
                          "title": "", "speed": "", "eta": ""})
            slot_bar.progress(0.0)

        process = subprocess.Popen(
            cmd_download, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=1, text=True
        )
        for raw in iter(process.stdout.readline, ""):
            parsed = _parse_line(raw.rstrip())
            if not parsed: continue
            evt = parsed["event"]

            if evt == "new_item":
                state.update({"item": parsed["item"], "total": parsed["total"],
                              "percent": 0.0, "speed": "", "eta": "", "title": ""})
                _render(state, slot_header, slot_title, slot_bar, slot_detail)
            elif evt == "title":
                state["title"] = parsed["title"]
                _render(state, slot_header, slot_title, slot_bar, slot_detail)
            elif evt == "progress":
                if state["total"] == 0: state.update({"item": 1, "total": 1})
                state.update({"speed": parsed.get("speed", state["speed"]),
                              "eta": parsed.get("eta", state["eta"])})
                _animate(state, state["percent"], parsed["percent"],
                         slot_header, slot_title, slot_bar, slot_detail)
            elif evt == "error":
                slot_errors.error(parsed["message"])

        process.wait()
        return process.returncode

    try:
        # ── Primera pasada ────────────────────────────────────
        returncode = _run_yt_dlp(intento=1)

        # ── Retry automático si falló ─────────────────────────
        if returncode != 0:
            returncode = _run_yt_dlp(intento=2)

        # ── Limpiar imágenes huérfanas en staging ─────────────
        # yt-dlp a veces no elimina los .jpg/.webp después de embeber
        IMG_EXTS = (".jpg", ".jpeg", ".webp", ".png")
        for root, _, files in os.walk(STAGING_DIR):
            for f in files:
                if f.lower().endswith(IMG_EXTS):
                    try:
                        os.remove(os.path.join(root, f))
                    except Exception:
                        pass

        # ── Limpieza de carpetas vacías ───────────────────────
        for d in glob.glob(os.path.join(STAGING_DIR, "*")):
            if os.path.isdir(d) and not glob.glob(os.path.join(d, "**", "*.mp3"), recursive=True):
                shutil.rmtree(d)

        # ── Detectar carpetas nuevas y buscar letras ──────────
        mp3s_despues = set(glob.glob(os.path.join(STAGING_DIR, "**", "*.mp3"), recursive=True))
        carpetas_nuevas = {os.path.dirname(mp3) for mp3 in (mp3s_despues - mp3s_antes)}

        if carpetas_nuevas:
            import fetch_lyrics
            for carpeta in sorted(carpetas_nuevas):
                fetch_lyrics.run(
                    carpeta,
                    slot_header=slot_header,
                    slot_title=slot_title,
                    slot_bar=slot_bar,
                    slot_detail=slot_detail,
                )

        # ── Finalizar ─────────────────────────────────────────
        if returncode == 0:
            _animate(state, state["percent"], 100.0,
                     slot_header, slot_title, slot_bar, slot_detail)
            slot_header.markdown("### ✅ Proceso finalizado")
            slot_bar.progress(1.0)
            if carpetas_nuevas:
                primer_carpeta = sorted(carpetas_nuevas)[0]
                artista_nuevo = os.path.basename(os.path.dirname(primer_carpeta))
                st.session_state["artista_auto_select"] = artista_nuevo
            st.session_state.df = load_data()
            st.rerun()
        else:
            st.error("yt-dlp finalizó con errores después de 2 intentos.")

    except Exception as e:
        st.error(f"Error crítico: {e}")
