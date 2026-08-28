# ui/fixtures_tab.py
"""
Pestaña "Por Equipo / Torneo": en vez de tipear los dos equipos a
mano, trae los partidos que la propia API ya tiene programados.

Modo equipo: buscás un equipo, elegís uno de sus próximos partidos.
Modo torneo: buscás un torneo, elegís una fecha (ronda) y predecís
todos sus partidos de una — con análisis de IA completo para cada
uno (elegido explícitamente: no hay problema de cuota de Gemini para
esto, ver conversación). Por eso tarda varios minutos con fechas de
muchos partidos.

Las predicciones de este modo se guardan automáticamente (SQLite +
Sheets) sin el diálogo interactivo de duplicados que tiene la
pestaña principal — pedir esa confirmación partido por partido no
tendría sentido cuando se predicen 10-14 de una.
"""
import traceback

import pandas as pd
import streamlit as st

import predictor
from data.fixtures import fetch_team_next_matches, fetch_tournament_fixtures
from database.sqlite import get_all_predictions, init_db, save_prediction
from database.sheets import append_prediction as sheets_append
from ui.result_view import render_resultado

_TEAM_TYPE_OPTIONS = ["default", "seleccion", "club_top", "club_menor"]
_TEAM_TYPE_LABELS = {
    "default":    "🏆 Default (20 p.)",
    "seleccion":  "🌍 Selección (15 p.)",
    "club_top":   "⭐ Club top (25 p.)",
    "club_menor": "🏅 Club menor (18 p.)",
}


def render_fixtures_tab() -> None:
    modo = st.radio("Modo", ["🔵 Por equipo", "🏆 Por torneo"],
                    horizontal=True, key="fx_modo")

    st.divider()

    if modo == "🔵 Por equipo":
        _render_modo_equipo()
    else:
        _render_modo_torneo()


def _guardar_silencioso(res: dict) -> int:
    """
    Guarda una predicción en SQLite + Sheets sin el diálogo
    interactivo de duplicados (pensado para predecir varios
    partidos seguidos sin tener que confirmar uno por uno).
    """
    init_db()
    pid = save_prediction(res, model_version="v2.0")
    res["pred_id"] = pid
    try:
        preds = get_all_predictions()
        pred_dict = next((p for p in preds if p["id"] == pid), None)
        if pred_dict:
            sheets_append(pred_dict)
    except Exception as e:
        print(f"  ⚠️  No se pudo sincronizar a Sheets: {e}")
    return pid


# ─────────────────────────────────────────────────────────────
# MODO EQUIPO
# ─────────────────────────────────────────────────────────────

def _render_modo_equipo() -> None:
    st.markdown("#### Buscar los próximos partidos programados de un equipo")

    col1, col2 = st.columns([3, 1])
    with col1:
        nombre = st.text_input("Equipo", placeholder="Ej: River Plate, Real Madrid...",
                               key="fx_team_name")
    with col2:
        team_type = st.selectbox("Tipo de equipo", _TEAM_TYPE_OPTIONS,
                                 format_func=lambda x: _TEAM_TYPE_LABELS[x],
                                 key="fx_team_type")

    if st.button("🔍 Buscar próximos partidos", key="fx_team_search_btn"):
        if not nombre:
            st.error("Ingresá un equipo.")
        else:
            with st.spinner("Buscando..."):
                st.session_state["fx_team_partidos"]   = fetch_team_next_matches(nombre, limit=8)
                st.session_state["fx_team_resultado"]  = None

    partidos = st.session_state.get("fx_team_partidos")

    if partidos is not None and not partidos:
        st.info("No se encontraron próximos partidos programados para ese equipo "
                "(puede que la API todavía no tenga el fixture cargado).")

    if partidos:
        st.markdown(f"**{len(partidos)} partidos encontrados:**")
        opciones = [
            f"{p['date']} {p['time']} — {p['team_home']} vs {p['team_away']} "
            f"({p['competition']})"
            for p in partidos
        ]
        idx = st.selectbox("Elegí el partido a predecir", range(len(partidos)),
                           format_func=lambda i: opciones[i], key="fx_team_sel")
        elegido = partidos[idx]

        if st.button("🚀 Predecir este partido", type="primary", key="fx_team_predict_btn"):
            with st.spinner("⏳ Calculando... (30-60 seg)"):
                try:
                    res = predictor.predecir(
                        elegido["team_home"], elegido["team_away"],
                        venue       = "home_a",
                        competition = elegido["competition"],
                        team_type   = team_type,
                        match_date  = elegido["date"],
                        verbose     = True,
                    )
                    pid = _guardar_silencioso(res)
                    st.session_state["fx_team_resultado"] = res
                    st.success(f"💾 Guardado con ID {pid}")
                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    st.code(traceback.format_exc(), language="python")

    res = st.session_state.get("fx_team_resultado")
    if res:
        st.divider()
        render_resultado(res, key_prefix="fx_team")


# ─────────────────────────────────────────────────────────────
# MODO TORNEO
# ─────────────────────────────────────────────────────────────

def _render_modo_torneo() -> None:
    st.markdown("#### Buscar las fechas pendientes de un torneo")
    st.caption("El fixture del torneo se cachea varios días — pensado para revisar "
              "una fecha por semana sin gastar cuota de más.")

    col1, col2 = st.columns([3, 1])
    with col1:
        nombre = st.text_input("Torneo", placeholder="Ej: Liga Profesional Argentina, Premier League...",
                               key="fx_torneo_name")
    with col2:
        team_type = st.selectbox("Tipo de equipo", _TEAM_TYPE_OPTIONS,
                                 format_func=lambda x: _TEAM_TYPE_LABELS[x],
                                 key="fx_torneo_team_type")

    if st.button("🔍 Buscar fechas", key="fx_torneo_search_btn"):
        if not nombre:
            st.error("Ingresá un torneo.")
        else:
            with st.spinner("Buscando fixture del torneo..."):
                st.session_state["fx_torneo_data"]        = fetch_tournament_fixtures(nombre)
                st.session_state["fx_torneo_resultados"]  = None

    data = st.session_state.get("fx_torneo_data")

    if data is not None and not data.get("rounds"):
        st.info("No se encontró el torneo o no tiene fechas futuras cargadas todavía.")

    if data and data.get("rounds"):
        rondas = data["rounds"]
        st.success(f"🏆 {data['tournament_name']}")

        # Nombre de la fase (ej. "Liga Profesional, Clausura") — lo
        # mostramos junto a la fecha para que quede claro a qué
        # torneo pertenece cuando la competición tiene fases
        # separadas (Apertura/Clausura, etc.)
        def _fase(r):
            partidos = rondas[r]
            return partidos[0]["competition"] if partidos else ""

        ronda_ids = list(rondas.keys())
        ronda_sel = st.selectbox(
            "Elegí la fecha",
            ronda_ids,
            format_func=lambda r: (f"Fecha {r} — {_fase(r)} ({len(rondas[r])} partidos)"
                                   if r is not None else "Sin número de fecha"),
            key="fx_torneo_ronda_sel",
        )
        partidos_ronda = rondas[ronda_sel]

        max_partidos = max(len(v) for v in rondas.values())
        if len(partidos_ronda) < max_partidos:
            st.caption("ℹ️ Esta fecha puede estar incompleta — la liga todavía no "
                      "confirmó el horario de todos sus partidos. Los que faltan "
                      "van a aparecer cuando se anuncien.")

        st.markdown(f"**Partidos de esta fecha ({len(partidos_ronda)}):**")
        preview = pd.DataFrame([
            {
                "Fecha":      p["date"],
                "Hora":       p["time"],
                "Local":      p["team_home"],
                "Visitante":  p["team_away"],
                "Competición": p["competition"],
            }
            for p in partidos_ronda
        ])
        st.dataframe(preview, use_container_width=True, hide_index=True,
                    key="fx_torneo_preview_df")

        st.caption(f"⏳ Con análisis de IA completo para cada partido, "
                  f"esto puede tardar {len(partidos_ronda) * 1}-{len(partidos_ronda) * 2} minutos.")

        if st.button(f"🚀 Predecir los {len(partidos_ronda)} partidos de esta fecha",
                    type="primary", key="fx_torneo_predict_all_btn"):
            resultados = []
            progreso   = st.progress(0.0, text="Arrancando...")

            for i, p in enumerate(partidos_ronda):
                progreso.progress(
                    i / len(partidos_ronda),
                    text=f"({i + 1}/{len(partidos_ronda)}) {p['team_home']} vs {p['team_away']}...",
                )
                try:
                    res = predictor.predecir(
                        p["team_home"], p["team_away"],
                        venue       = "home_a",
                        competition = p["competition"],
                        team_type   = team_type,
                        match_date  = p["date"],
                        verbose     = True,
                    )
                    _guardar_silencioso(res)
                    resultados.append(res)
                except Exception as e:
                    st.warning(f"⚠️ Error prediciendo {p['team_home']} vs {p['team_away']}: {e}")

            progreso.progress(1.0, text="¡Listo!")
            st.session_state["fx_torneo_resultados"] = resultados

    resultados = st.session_state.get("fx_torneo_resultados")
    if resultados:
        st.divider()
        st.markdown(f"### 📋 Resumen de la fecha ({len(resultados)} partidos)")

        resumen_rows = []
        for r in resultados:
            ia = r.get("analisis_ia", {}) or {}
            coincide = ia.get("coincide_modelo")
            resumen_rows.append({
                "Partido":       f"{r['equipo_a']} vs {r['equipo_b']}",
                "P(Local) %":    r["victoria_a"],
                "P(Empate) %":   r["empate"],
                "P(Visita) %":   r["victoria_b"],
                "Predicción IA": ia.get("prediccion", "—"),
                "Marcador IA":   ia.get("marcador_predicho", "—"),
                "Coincide":      "✅" if coincide is True else ("❌" if coincide is False else "—"),
            })
        st.dataframe(pd.DataFrame(resumen_rows), use_container_width=True,
                    hide_index=True, key="fx_torneo_resumen_df")

        st.markdown("#### Ver el detalle completo de un partido")
        opciones_detalle = [f"{r['equipo_a']} vs {r['equipo_b']}" for r in resultados]
        idx_detalle = st.selectbox("Elegí un partido", range(len(resultados)),
                                   format_func=lambda i: opciones_detalle[i],
                                   key="fx_torneo_detalle_sel")

        st.divider()
        render_resultado(resultados[idx_detalle], key_prefix=f"fx_torneo_{idx_detalle}")
