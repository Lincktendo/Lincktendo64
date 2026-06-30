# =============================================================
# section_lyrics.py — Sección 3: Visor de Letras
# =============================================================

import os
import subprocess
import streamlit as st
from config import FINAL_DIR, PATH_TO_LYRICS_SCRIPT
from data_loader import load_data


def render():
    st.header("📝 Biblioteca de Letras")

    if st.session_state.df.empty:
        return

    all_artists = sorted(st.session_state.df["artist_folder"].unique())
    sel_artist  = st.selectbox("Artista a consultar:", all_artists)

    artist_tracks = st.session_state.df[
        st.session_state.df["artist_folder"] == sel_artist
    ]

    col_l, col_r = st.columns([1, 2])

    with col_l:
        if st.button(f"Forzar búsqueda: {sel_artist}"):
            subprocess.run([
                "bash", PATH_TO_LYRICS_SCRIPT,
                os.path.join(FINAL_DIR, sel_artist),
            ])
            st.session_state.df = load_data()
            st.rerun()

        track_sel = st.selectbox(
            "Seleccionar rola:",
            artist_tracks["Título (Metadata)"].tolist(),
        )

    with col_r:
        if track_sel:
            row = artist_tracks[
                artist_tracks["Título (Metadata)"] == track_sel
            ].iloc[0]
            lrc_path = os.path.splitext(row["path"])[0] + ".lrc"

            if os.path.exists(lrc_path):
                with open(lrc_path, "r", encoding="utf-8") as f:
                    st.text_area("Letra:", f.read(), height=300)
            else:
                st.warning("No hay archivo .lrc para esta canción.")
