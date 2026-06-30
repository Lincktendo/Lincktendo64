# =============================================================
# section_editor.py — Sección 2: Edición de Metadata + Mover
# =============================================================

import os
import shutil
import streamlit as st
from mutagen.easyid3 import EasyID3
from config import STAGING_DIR, FINAL_DIR
from utils import ensure_artist_folder_image, get_all_genres
from data_loader import load_data


def _fmt_genre(tag: str) -> str:
    """
    Capitaliza géneros respetando guiones:
    'hip-hop' → 'Hip-Hop', 'rap' → 'Rap', 'alternative rock' → 'Alternative Rock'
    """
    def cap_hyphen(s):
        return '-'.join(seg[:1].upper() + seg[1:] for seg in s.split('-'))
    return ' '.join(cap_hyphen(word) for word in tag.split())


def _guardar_metadata(df, mask):
    """Escribe los tags ID3 a disco para todas las filas del artista."""
    errores = []
    for _, row in df[mask].iterrows():
        try:
            audio = EasyID3(row["path"])
            audio.update({
                "artist":      row["Artista"],
                "albumartist": row["Album Artist"],
                "album":       row["Album"],
                "tracknumber": row["Track"],
                "discnumber":  row["Disc"],
                "genre":       row["Genre"],
                "title":       row["Título (Metadata)"],
            })
            audio.save()
        except Exception as e:
            errores.append(f"{row['Título (Metadata)']}: {e}")
    return errores


def _mover_carpeta(artista_actual):
    """
    Mueve la carpeta de artista de staging → library.
    Si ya existía en library, fusiona el contenido.
    Borra el rastro en staging al terminar.
    Elimina imágenes sueltas del destino para no desconfigurar los álbumes.
    """
    src  = os.path.join(STAGING_DIR, artista_actual)
    dest = os.path.join(FINAL_DIR,   artista_actual)
    os.makedirs(dest, exist_ok=True)

    for item in os.listdir(src):
        s = os.path.join(src,  item)
        d = os.path.join(dest, item)
        if os.path.exists(d):
            if os.path.isdir(s):
                for subitem in os.listdir(s):
                    shutil.move(os.path.join(s, subitem), d)
                os.rmdir(s)
            else:
                shutil.move(s, d)
        else:
            shutil.move(s, d)

    shutil.rmtree(src)

    # Eliminar todas las imágenes sueltas del destino
    # (folder.jpg, portadas huérfanas, etc.) para no romper el arte de los álbumes
    IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp")
    for root, _, files in os.walk(dest):
        for f in files:
            if f.lower().endswith(IMG_EXTS):
                try:
                    os.remove(os.path.join(root, f))
                except Exception:
                    pass


def render():
    st.header("📂 Metadatos y Organización")

    if st.session_state.df.empty:
        st.info("No hay archivos en staging todavía.")
        return

    # ── Selector de artista ───────────────────────────────────
    artistas_pendientes = sorted(st.session_state.df["artist_folder"].unique())
    auto = st.session_state.pop("artista_auto_select", None)
    default_index = artistas_pendientes.index(auto) if auto in artistas_pendientes else 0
    artista_actual = st.selectbox("Artista a revisar:", artistas_pendientes, index=default_index)
    mask = st.session_state.df["artist_folder"] == artista_actual
    vista = st.session_state.df[mask]

    # ── Buscador de Género — 2 botones ───────────────────────
    with st.expander("🔍 Buscador de Género"):
        col_a, col_b = st.columns(2)

        # a) /Music/Artist genre — copiar género de la librería existente
        artist_final_path = os.path.join(FINAL_DIR, artista_actual)
        artist_en_library = os.path.isdir(artist_final_path)

        if col_a.button(
            "/Music/Artist genre",
            key=f"btn_library_{artista_actual}",
            disabled=not artist_en_library,
            help="El artista no existe aún en la librería" if not artist_en_library else
                 "Copia el género desde los archivos ya existentes en la librería",
        ):
            genre_encontrado = ""
            archivos_revisados = 0
            AUDIO_EXTS = (".mp3", ".flac", ".m4a", ".ogg", ".opus", ".wav")
            for root, _, files in os.walk(artist_final_path):
                for f in files:
                    if not f.lower().endswith(AUDIO_EXTS):
                        continue
                    archivos_revisados += 1
                    try:
                        from mutagen import File as MutagenFile
                        audio = MutagenFile(os.path.join(root, f), easy=True)
                        if audio is None:
                            continue
                        g = (audio.get("genre") or [""])[0].strip()
                        if g:
                            genre_encontrado = g
                            break
                    except Exception:
                        continue
                if genre_encontrado:
                    break

            if genre_encontrado:
                st.session_state.df.loc[mask, "Genre"] = genre_encontrado
                st.success(f"Género copiado: **{genre_encontrado}**")
                st.rerun()
            elif archivos_revisados == 0:
                st.warning("La carpeta existe pero no tiene archivos de audio.")
            else:
                st.warning(f"Se revisaron {archivos_revisados} archivo(s) pero ninguno tiene género definido aún.")

        # b) Buscar Géneros — Last.fm + DuckDuckGo + MusicBrainz en paralelo
        key_tags = f"genre_tags_{artista_actual}"
        if col_b.button("🔍 Buscar Géneros", key=f"btn_buscar_{artista_actual}"):
            with st.spinner("Consultando Last.fm, DuckDuckGo y MusicBrainz..."):
                tags, errores = get_all_genres(artista_actual)
            for k in list(st.session_state.keys()):
                if k.startswith(f"ck_{artista_actual}_"):
                    del st.session_state[k]
            if tags:
                st.session_state[key_tags] = tags
            else:
                st.info("No se encontraron géneros en ninguna fuente.")
            if errores:
                st.caption(f"⚠️ {' | '.join(errores)}")

        if key_tags in st.session_state:
            tags = [_fmt_genre(t) for t in st.session_state[key_tags]]
            st.caption("Marca los géneros que quieres aplicar (Last.fm · DuckDuckGo · MusicBrainz):")
            check_cols = st.columns(len(tags))
            for i, tag in enumerate(tags):
                check_cols[i].checkbox(tag, key=f"ck_{artista_actual}_{i}")

            seleccionados = [
                tags[i]
                for i in range(len(tags))
                if st.session_state.get(f"ck_{artista_actual}_{i}", False)
            ]

            if seleccionados:
                genre_str = ", ".join(seleccionados)
                if st.button(
                    f"✅ Aplicar: {genre_str}",
                    key=f"apply_sel_{artista_actual}",
                ):
                    st.session_state.df.loc[mask, "Genre"] = genre_str
                    for i in range(len(tags)):
                        st.session_state.pop(f"ck_{artista_actual}_{i}", None)
                    del st.session_state[key_tags]
                    st.rerun()

    # ── Sobrescribir (expander) ───────────────────────────────
    with st.expander("✍️ Sobrescribir Artist / Album Artist / Album / Genre"):
        editable_cols = ["Artista", "Album Artist", "Album", "Genre"]
        cols_input = st.columns(len(editable_cols))
        input_vals = {
            col: cols_input[i].text_input(f"Set {col}", key=f"inp_{col}_{artista_actual}")
            for i, col in enumerate(editable_cols)
        }
        if st.button("Aplicar cambios", key=f"aplicar_{artista_actual}"):
            for col, val in input_vals.items():
                if val:
                    st.session_state.df.loc[mask, col] = (
                        val.replace(",", ";") if col in ["Artista", "Album Artist"] else val
                    )
            st.rerun()

    # ── Subheader: Edición Masiva — Artista [— Album si hay uno solo] ──
    albumes = vista["Album"].dropna().unique()
    if len(albumes) == 1 and albumes[0]:
        subheader_txt = f"⚡ Edición Masiva — {artista_actual} — {albumes[0]}"
    else:
        subheader_txt = f"⚡ Edición Masiva — {artista_actual}"
    st.subheader(subheader_txt)

    # ── Data Editor — altura dinámica para mostrar todas las filas ──
    n_filas   = len(vista)
    alto_tabla = 38 + (n_filas * 35) + 16   # header + filas + padding

    # Índice visual desde 1 (el row_id sigue oculto para el sync)
    vista_display = vista.copy()
    vista_display.index = range(1, len(vista_display) + 1)

    edited = st.data_editor(
        vista_display,
        use_container_width=True,
        height=alto_tabla,
        column_config={
            "row_id":        None,
            "path":          None,
            "folder":        None,
            "artist_folder": None,
            "Portada":       st.column_config.ImageColumn("Portada"),
        },
        key=f"editor_{artista_actual}",
    )

    # Sincronizar ediciones al DataFrame principal (via row_id, no el índice visual)
    full_indexed = st.session_state.df.set_index("row_id")
    full_indexed.update(edited.set_index("row_id"))
    st.session_state.df = full_indexed.reset_index()

    # ── Botones Guardar / Mover ───────────────────────────────
    st.write("")
    col_save, col_move = st.columns([1, 1])

    # Guardar — solo escribe metadata a disco, no mueve nada
    if col_save.button("💾 Guardar", key=f"btn_guardar_{artista_actual}"):
        errores = _guardar_metadata(st.session_state.df, mask)
        if errores:
            for err in errores:
                st.error(f"Error: {err}")
        else:
            st.success("¡Metadata guardada!")

    # Mover — mueve carpeta a library, fusiona si ya existía
    if col_move.button("Mover ➡️", key=f"btn_mover_{artista_actual}"):
        errores = _guardar_metadata(st.session_state.df, mask)
        for err in errores:
            st.error(f"Error guardando: {err}")
        try:
            _mover_carpeta(artista_actual)
            st.success(f"✅ '{artista_actual}' movido a la librería.")
            st.session_state.df = load_data()
            st.rerun()
        except Exception as e:
            st.error(f"Error al mover: {e}")
