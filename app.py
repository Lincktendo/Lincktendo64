# =============================================================
# app.py — Lincktendo64 entry point
# =============================================================

import streamlit as st
from config import load_settings
from i18n import t
from data_loader import load_data
import section_settings

st.set_page_config(
    page_title="Lincktendo64",
    page_icon="🎵",
    layout="wide",
)

# ── Load settings into session_state once ─────────────────────
if "settings" not in st.session_state:
    st.session_state["settings"] = load_settings()

# ── Load staging data once ────────────────────────────────────
if "df" not in st.session_state:
    st.session_state.df = load_data()

# ── Gear button fixed top-right (opens settings popup) ────────
section_settings.render()

# ── Header ────────────────────────────────────────────────────
st.title(t("app_title"))
st.caption(t("app_subtitle"))

# ── Tabs ──────────────────────────────────────────────────────
tab_dl, tab_ed, tab_ly = st.tabs([
    t("tab_download"),
    t("tab_editor"),
    t("tab_lyrics"),
])

import section_download
import section_editor
import section_lyrics

with tab_dl:
    section_download.render()

with tab_ed:
    section_editor.render()

with tab_ly:
    section_lyrics.render()
