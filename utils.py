# =============================================================
# utils.py — Funciones utilitarias reutilizables
# =============================================================

import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from mutagen.id3 import ID3, APIC
from config import LASTFM_API_KEY as _LASTFM_DEFAULT

UA = "CentroIngesta/1.0 (navidrome-nas)"


def ensure_artist_folder_image(artist_path):
    """
    Busca candidatos de imagen existentes para la carpeta del artista.
    Si no hay ninguno, extrae la portada del primer MP3 que tenga.
    """
    candidatos = ["artist.jpg", "artist.png", "folder.jpg", "folder.png"]
    if any(os.path.exists(os.path.join(artist_path, c)) for c in candidatos):
        return

    for root, _, files in os.walk(artist_path):
        for f in files:
            if f.endswith(".mp3"):
                try:
                    audio = ID3(os.path.join(root, f))
                    for tag in audio.values():
                        if isinstance(tag, APIC):
                            dest = os.path.join(artist_path, "folder.jpg")
                            with open(dest, "wb") as img:
                                img.write(tag.data)
                            return
                except:
                    continue


def get_lastfm_tags(artist, limit=5):
    """Last.fm top tags — lee el key de settings (session_state) o del default."""
    import streamlit as st
    api_key = st.session_state.get("settings", {}).get("lastfm_api_key", _LASTFM_DEFAULT)
    if not api_key or api_key == "TU_API_KEY_AQUI":
        return [], "Configura tu Last.fm API Key en Settings (⚙️)."
    try:
        resp = requests.get(
            "http://ws.audioscrobbler.com/2.0/",
            params={"method": "artist.gettoptags", "artist": artist,
                    "api_key": api_key, "format": "json"},
            timeout=8,
        )
        data = resp.json()
        tags = [t["name"] for t in data.get("toptags", {}).get("tag", [])[:limit]]
        return tags, None
    except Exception as e:
        return [], str(e)


def get_duckduckgo_genres(artist, limit=5):
    """
    DuckDuckGo Instant Answer API — sin API key.
    Extrae géneros del Infobox cuando existe.
    """
    try:
        resp = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": f"{artist} musician", "format": "json",
                    "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": UA},
            timeout=8,
        )
        data = resp.json()
        for item in data.get("Infobox", {}).get("content", []):
            if "genre" in item.get("label", "").lower():
                raw = item.get("value", "")
                genres = [g.strip() for g in re.split(r"[,/\n]", raw) if g.strip()]
                return genres[:limit], None
        return [], None
    except Exception as e:
        return [], str(e)


def get_musicbrainz_genres(artist, limit=5):
    """
    MusicBrainz API — sin API key.
    Retorna tags ordenados por votos descendente.
    """
    try:
        resp = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            params={"query": artist, "fmt": "json", "limit": 1},
            headers={"User-Agent": UA},
            timeout=10,
        )
        data = resp.json()
        artists = data.get("artists", [])
        if not artists:
            return [], None
        tags = sorted(artists[0].get("tags", []),
                      key=lambda t: t.get("count", 0), reverse=True)
        return [t["name"] for t in tags[:limit]], None
    except Exception as e:
        return [], str(e)


def get_all_genres(artist, limit_each=5):
    """
    Consulta Last.fm, DuckDuckGo y MusicBrainz en paralelo.
    Combina y deduplica manteniendo orden de aparición.
    Retorna (lista_géneros, fuentes_con_error).
    """
    fuentes = {
        "Last.fm":      get_lastfm_tags,
        "DuckDuckGo":   get_duckduckgo_genres,
        "MusicBrainz":  get_musicbrainz_genres,
    }
    resultados = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fn, artist, limit_each): name
                   for name, fn in fuentes.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                tags, err = future.result()
                resultados[name] = (tags, err)
            except Exception as e:
                resultados[name] = ([], str(e))

    # Combinar deduplicando (case-insensitive)
    combinados = []
    vistos = set()
    errores = []
    for name, (tags, err) in resultados.items():
        if err:
            errores.append(f"{name}: {err}")
        for tag in tags:
            key = tag.lower().strip()
            if key not in vistos:
                vistos.add(key)
                combinados.append(tag)

    return combinados, errores
