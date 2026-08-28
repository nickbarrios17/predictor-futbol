# app.py - v2.1
"""Interfaz Streamlit del Predictor de Futbol."""
import sys

# Los prints de debug usan emojis; en Windows la consola por defecto
# es cp1252 y no puede codificarlos, lo que crashea el proceso.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import streamlit as st

from ui.backtesting_tab import render_backtesting_tab
from ui.common import apply_global_styles, init_session_state
from ui.history_tab import render_history_tab
from ui.prediction_tab import render_prediction_tab
from ui.worldcup_tab import render_worldcup_tab


st.set_page_config(
    page_title="Predictor de Futbol ⚽",
    page_icon="⚽",
    layout="wide",
)

apply_global_styles()
init_session_state()

st.markdown("# ⚽ Predictor de Futbol")
st.markdown("Modelo estadistico · Poisson + Dixon-Coles + Gemini · v2.2")

tab_pred, tab_hist, tab_back, tab_wc = st.tabs([
    "🎯 Prediccion",
    "📋 Historial",
    "📊 Backtesting",
    "🏆 Mundial 2026",
])

with tab_pred:
    render_prediction_tab()

with tab_hist:
    render_history_tab()

with tab_back:
    render_backtesting_tab()

with tab_wc:
    render_worldcup_tab()
