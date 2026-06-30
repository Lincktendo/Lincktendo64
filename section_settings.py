# =============================================================
# section_settings.py — Settings popup, mobile-app style nav
# Fully i18n: every visible string goes through t()
# =============================================================

import subprocess
import sys
import streamlit as st
from i18n import t
from config import load_settings, save_settings

SECTIONS = [
    ("⚙️", "st_nav_general",  "general"),
    ("🔑", "st_nav_apikeys",  "apikeys"),
    ("📦", "st_nav_versions", "versions"),
    ("ℹ️", "st_nav_about",    "about"),
]


def _ver(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(
            cmd, text=True, stderr=subprocess.DEVNULL
        ).strip().split("\n")[0]
    except Exception:
        return "—"


@st.dialog("⚙️")
def _dialog():
    settings = st.session_state.get("settings", load_settings())

    if "cfg_draft" not in st.session_state:
        st.session_state.cfg_draft = dict(settings)
    if "cfg_section" not in st.session_state:
        st.session_state.cfg_section = "general"

    draft = st.session_state.cfg_draft

    # ── Nav: horizontal row, app-style ─────────────────────────
    cols = st.columns(len(SECTIONS))
    for col, (icon, label_key, key) in zip(cols, SECTIONS):
        active = st.session_state.cfg_section == key
        if col.button(
            f"{icon}\n{t(label_key)}",
            key=f"cfgnav_{key}",
            use_container_width=True,
            type="primary" if active else "secondary",
        ):
            st.session_state.cfg_section = key

    st.divider()

    section = st.session_state.cfg_section

    # ── General ────────────────────────────────────────────────
    if section == "general":
        st.markdown(f"**{t('st_paths')}**")
        draft["staging_dir"] = st.text_input(
            t("st_staging"),
            value=draft.get("staging_dir", "/data/staging/"),
            help=t("st_staging_help"),
        )
        draft["library_dir"] = st.text_input(
            t("st_library"),
            value=draft.get("library_dir", "/music/"),
            help=t("st_library_help"),
        )

        st.write("")
        st.markdown(f"**{t('st_language')}**")
        lang_opts = {"en": "🇺🇸 English", "es": "🇸🇻 Español"}
        cur_lang = draft.get("language", "en")
        draft["language"] = st.selectbox(
            t("st_language_label"),
            options=list(lang_opts.keys()),
            format_func=lambda k: lang_opts[k],
            index=list(lang_opts.keys()).index(cur_lang),
            label_visibility="collapsed",
        )

    # ── API Keys ───────────────────────────────────────────────
    elif section == "apikeys":
        st.markdown("**Last.fm**")
        draft["lastfm_api_key"] = st.text_input(
            t("st_lastfm"),
            value=draft.get("lastfm_api_key", ""),
            type="password",
            help=t("st_lastfm_help"),
        )
        st.caption(t("st_lastfm_get_key"))

        st.write("")
        st.markdown(t("st_no_key_needed"))
        c1, c2 = st.columns(2)
        c1.success("DuckDuckGo")
        c2.success("MusicBrainz")

        st.write("")
        st.markdown(t("st_lyrics_source"))
        st.caption(t("st_lyrics_source_caption"))

    # ── Versions ───────────────────────────────────────────────
    elif section == "versions":
        import mutagen
        import streamlit as _st

        ffmpeg_raw = _ver(["ffmpeg", "-version"])
        ffmpeg_ver = ffmpeg_raw.split(" ")[2] if "version" in ffmpeg_raw else "—"

        st.markdown(f"**{t('st_versions')}**")
        c1, c2 = st.columns(2)
        c1.metric("Python",    sys.version.split()[0])
        c2.metric("Streamlit", _st.__version__)
        c1.metric("yt-dlp",    _ver(["yt-dlp", "--version"]))
        c2.metric("mutagen",   mutagen.version_string)
        c1.metric("ffmpeg",    ffmpeg_ver)

        st.write("")
        st.markdown(f"**{t('st_updates')}**")
        col_a, col_b = st.columns(2)

        if col_a.button(t("st_update_ytdlp"), use_container_width=True, type="primary"):
            with st.spinner(t("st_updating")):
                try:
                    r = subprocess.run(
                        ["pip", "install", "--upgrade", "yt-dlp"],
                        capture_output=True, text=True,
                    )
                    if r.returncode == 0:
                        st.success(t("st_updated_ytdlp"))
                    else:
                        st.error(t("st_update_error", error=r.stderr[:200]))
                except Exception as e:
                    st.error(t("st_update_error", error=str(e)))

        if col_b.button(t("st_update_mutagen"), use_container_width=True):
            with st.spinner(t("st_updating")):
                try:
                    r = subprocess.run(
                        ["pip", "install", "--upgrade", "mutagen"],
                        capture_output=True, text=True,
                    )
                    if r.returncode == 0:
                        st.success(t("st_updated_mutagen"))
                    else:
                        st.error(t("st_update_error", error=r.stderr[:200]))
                except Exception as e:
                    st.error(t("st_update_error", error=str(e)))

    # ── About ──────────────────────────────────────────────────
    elif section == "about":
        st.markdown(t("st_about_body"))

    # ── Save ───────────────────────────────────────────────────
    st.divider()
    _, col_save = st.columns([3, 1])
    if col_save.button(t("st_save"), type="primary", use_container_width=True):
        draft["staging_dir"] = draft.get("staging_dir", "/data/staging/").rstrip("/") + "/"
        draft["library_dir"] = draft.get("library_dir", "/music/").rstrip("/") + "/"
        save_settings(draft)
        st.session_state["settings"] = dict(draft)
        st.session_state.pop("cfg_draft", None)
        st.success(t("st_saved"))


def render():
    """
    Renders the fixed ⚙️ button top-right.
    Call this in app.py right after set_page_config.
    """
    cols = st.columns([30, 1])
    with cols[1]:
        if st.button("⚙️", key="gear_open", help=t("tab_settings")):
            st.session_state.pop("cfg_draft", None)
            st.session_state.pop("cfg_section", None)
            _dialog()
