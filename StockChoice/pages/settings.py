"""stockchoice - settings page."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st

from app_utils import DEFAULT_SETTINGS, initialize_settings


# ============================================================
# INITIALIZE SETTINGS
# ============================================================

initialize_settings()


# ============================================================
# RESET PREFERENCES
# ============================================================

def reset_preferences() -> None:
    """Restore all StockChoice preferences to their defaults."""
    for key, value in DEFAULT_SETTINGS.items():
        st.session_state[key] = value


# ============================================================
# PAGE STYLING
# ============================================================

st.markdown(
    """
<style>

[data-testid="stSidebar"] {
    display: none;
}

[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    display: none !important;
    visibility: hidden !important;
}

.block-container {
    max-width: 520px;
    padding: 2.5rem 1rem 5rem 1rem;
}

.module-title {
    font-size: 2rem;
    font-weight: 800;
    margin-bottom: .15rem;
}

.module-subtitle {
    color: #9aa3b2;
    font-size: .9rem;
    margin-bottom: 1rem;
}

.section-label {
    font-size: .82rem;
    color: #9aa3b2;
    font-weight: 650;
    margin-top: 1rem;
    margin-bottom: .35rem;
}

.setting-card {
    border: 1px solid rgba(128,128,128,.25);
    border-radius: 16px;
    padding: .9rem 1rem;
    background: rgba(128,128,128,.05);
    margin: .4rem 0 .75rem 0;
}

.setting-title {
    font-size: 1rem;
    font-weight: 750;
    margin-bottom: .2rem;
}

.setting-text {
    font-size: .82rem;
    color: #9aa3b2;
    line-height: 1.4;
}

.status-pill {
    display: inline-block;
    border-radius: 999px;
    padding: .25rem .6rem;
    background: rgba(37,99,235,.13);
    color: #60a5fa;
    font-size: .78rem;
    font-weight: 700;
    margin-top: .35rem;
}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="module-title">⚙️ Settings</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="module-subtitle">
Customize the StockChoice research experience and manage
session preferences.
</div>
""",
    unsafe_allow_html=True,
)

st.page_link(
    "app.py",
    label="Home",
    icon="🏠",
    width="stretch",
)


# ============================================================
# STARTUP
# ============================================================

st.markdown(
    '<div class="section-label">STARTUP</div>',
    unsafe_allow_html=True,
)

module_options = [
    "Growth",
    "Value",
    "Dividend",
    "ETF",
    "Markets",
]

current_module = st.session_state.get(
    "mobile_default_module",
    DEFAULT_SETTINGS["mobile_default_module"],
)

if current_module not in module_options:
    current_module = "Growth"

st.session_state["mobile_default_module"] = st.selectbox(
    "Default research module",
    options=module_options,
    index=module_options.index(current_module),
    help="Preferred research area for future navigation enhancements.",
)


# ------------------------------------------------------------
# Default result count
# ------------------------------------------------------------

result_options = [
    5,
    10,
    15,
    20,
]

current_count = st.session_state.get(
    "mobile_default_result_count",
    DEFAULT_SETTINGS["mobile_default_result_count"],
)

st.session_state["mobile_default_result_count"] = st.select_slider(
    "Default number of candidates",
    options=result_options,
    value=(
        current_count
        if current_count in result_options
        else 20
    ),
)


# ============================================================
# DISPLAY
# ============================================================

st.markdown(
    '<div class="section-label">DISPLAY</div>',
    unsafe_allow_html=True,
)

st.session_state["mobile_compact_cards"] = st.toggle(
    "Compact research cards",
    value=st.session_state.get(
        "mobile_compact_cards",
        DEFAULT_SETTINGS["mobile_compact_cards"],
    ),
    help="Preference for dense mobile stock and ETF cards.",
)

st.session_state["mobile_show_charts"] = st.toggle(
    "Show analytical charts",
    value=st.session_state.get(
        "mobile_show_charts",
        DEFAULT_SETTINGS["mobile_show_charts"],
    ),
    help="Show charts on research modules.",
)

st.session_state["mobile_show_disclaimer"] = st.toggle(
    "Show research disclaimer",
    value=st.session_state.get(
        "mobile_show_disclaimer",
        DEFAULT_SETTINGS["mobile_show_disclaimer"],
    ),
)


# ============================================================
# DATA
# ============================================================

st.markdown(
    '<div class="section-label">DATA</div>',
    unsafe_allow_html=True,
)

cache_options = [
    "Fresh",
    "Balanced",
    "Data Saver",
]

current_cache = st.session_state.get(
    "mobile_cache_preference",
    DEFAULT_SETTINGS["mobile_cache_preference"],
)

if current_cache not in cache_options:
    current_cache = "Balanced"

st.session_state["mobile_cache_preference"] = st.radio(
    "Refresh preference",
    options=cache_options,
    index=cache_options.index(current_cache),
    horizontal=True,
)


# ------------------------------------------------------------
# Session information
# ------------------------------------------------------------

st.markdown(
    """
<div class="setting-card">
<div class="setting-title">Current session</div>
<div class="setting-text">
Research preferences are stored for the current Streamlit session.
Cached market data can be cleared manually when you want StockChoice
to retrieve fresh data.
</div>
</div>
""",
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Clear market-data cache
# ------------------------------------------------------------

if st.button(
    "🗑️ Clear data cache",
    use_container_width=True,
):
    st.cache_data.clear()
    st.toast("Cached market data cleared")


# ============================================================
# RESET
# ============================================================

st.markdown(
    '<div class="section-label">RESET</div>',
    unsafe_allow_html=True,
)

if st.button(
    "Reset Mobile preferences",
    type="secondary",
    use_container_width=True,
):
    reset_preferences()
    st.toast("Mobile preferences reset")
    st.rerun()


# ============================================================
# ABOUT
# ============================================================

st.markdown(
    """
<div class="setting-card">
<div class="setting-title">📱 StockChoice</div>
<div class="setting-text">
Mobile-first research suite for Growth, Value, Dividend, ETF,
Markets, Compare, and Sample Portfolio research.
</div>
<div class="status-pill">Development build</div>
</div>
""",
    unsafe_allow_html=True,
)


# ============================================================
# DISCLAIMER
# ============================================================

st.caption(
    "StockChoice is intended for informational and educational "
    "research and does not provide personalized investment advice."
)