# ui/prediction_tab.py
import traceback

import streamlit as st

import predictor
from database.sqlite import (
    check_duplicates,
    delete_prediction,
    get_all_predictions,
    init_db,
    save_prediction,
)
from database.sheets import append_prediction as sheets_append
from sources.api_source import search_team
from ui.result_view import render_resultado


def render_prediction_tab() -> None:

    # ── Búsqueda de equipos ───────────────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🔵 Equipo A")
        busqueda_a = st.text_input("Buscar equipo A", key="search_a",
                                    placeholder="Ej: River Plate, Real Madrid...")
        if st.button("🔍 Buscar A", use_container_width=True):
            with st.spinner("Buscando..."):
                st.session_state["candidatos_a"] = search_team(busqueda_a)

        candidatos_a = st.session_state["candidatos_a"]
        if candidatos_a:
            sel_a   = st.selectbox("Seleccionar equipo A", candidatos_a,
                                    format_func=lambda x: x.get("name",""), key="sel_a")
            name_a  = sel_a["name"] if sel_a else busqueda_a
            st.success(f"✅ {name_a} (ID: {sel_a['id']})")
        else:
            name_a = busqueda_a

    with col2:
        st.markdown("#### 🔴 Equipo B")
        busqueda_b = st.text_input("Buscar equipo B", key="search_b",
                                    placeholder="Ej: Boca Juniors, Barcelona...")
        if st.button("🔍 Buscar B", use_container_width=True):
            with st.spinner("Buscando..."):
                st.session_state["candidatos_b"] = search_team(busqueda_b)

        candidatos_b = st.session_state["candidatos_b"]
        if candidatos_b:
            sel_b   = st.selectbox("Seleccionar equipo B", candidatos_b,
                                    format_func=lambda x: x.get("name",""), key="sel_b")
            name_b  = sel_b["name"] if sel_b else busqueda_b
            st.success(f"✅ {name_b} (ID: {sel_b['id']})")
        else:
            name_b = busqueda_b

    # ── Parámetros ────────────────────────────────────────────
    st.divider()
    col3, col4, col5, col6 = st.columns(4)
    with col3:
        venue = st.selectbox("Sede", ["neutral","home_a","home_b"],
            format_func=lambda x: {"neutral":"⚖️ Neutral",
                                    "home_a": "🏠 Local: A",
                                    "home_b": "🏠 Local: B"}[x])
    with col4:
        competition = st.text_input("Competición (opcional)",
                                     placeholder="Champions, Liga, Copa...",
                                     key="competition")
    with col5:
        match_date = st.text_input("Fecha del partido (opcional)",
                                    placeholder="2026-06-15",
                                    key="match_date")
    with col6:
        team_type = st.selectbox("Tipo de equipo",
            ["default","seleccion","club_top","club_menor"],
            format_func=lambda x: {
                "default":    "🏆 Default (20 p.)",
                "seleccion":  "🌍 Selección (15 p.)",
                "club_top":   "⭐ Club top (25 p.)",
                "club_menor": "🏅 Club menor (18 p.)",
            }[x])

    # ── Botón calcular ────────────────────────────────────────
    st.divider()
    if st.button("🚀 Calcular predicción", use_container_width=True, type="primary"):
        if not name_a or not name_b:
            st.error("Por favor ingresá ambos equipos.")
        elif name_a == name_b:
            st.error("Los dos equipos no pueden ser el mismo.")
        else:
            with st.spinner("⏳ Calculando... (30-60 seg)"):
                try:
                    res = predictor.predecir(
                        name_a, name_b,
                        venue=venue,
                        competition=competition,
                        team_type=team_type,
                        match_date=match_date,
                        verbose=True,
                    )
                    st.session_state["resultado"]    = res
                    st.session_state["pending_save"] = True
                    st.session_state["show_replace"] = False

                    # Verificar duplicados
                    init_db()
                    dup = check_duplicates(
                        name_a, name_b,
                        competition = competition,
                        match_date  = match_date,
                    )
                    st.session_state["dup_check"] = dup

                except Exception as e:
                    st.error(f"❌ Error: {e}")
                    st.code(traceback.format_exc(), language="python")
                    st.session_state["resultado"] = None

    # ── Resultado ─────────────────────────────────────────────
    res = st.session_state.get("resultado")
    if not res:
        st.info("Calcula una prediccion para ver el detalle aca. Historial y Backtesting siguen disponibles en sus pestañas.")
    else:

        # ── Panel de duplicados / guardado ────────────────────────
        dup_check    = st.session_state.get("dup_check")
        pending_save = st.session_state.get("pending_save", False)

        if pending_save and dup_check:
            has_exact   = dup_check.get("has_exact",   False)
            has_similar = dup_check.get("has_similar", False)

            def _do_save():
                """Guarda en SQLite + Sheets y actualiza session_state."""
                pid = save_prediction(res, model_version="v2.0")
                res["pred_id"] = pid
                st.session_state["resultado"]    = res
                st.session_state["pending_save"] = False
                st.session_state["dup_check"]    = None
                st.session_state["show_replace"] = False
                # Agregar al sheet
                try:
                    pred_dict = get_all_predictions()
                    pred_dict = next((p for p in pred_dict if p["id"] == pid), None)
                    if pred_dict:
                        sheet_result = sheets_append(pred_dict)
                        if not sheet_result.get("ok"):
                            st.warning(f"SQLite guardado, pero Sheets no sincronizo: {sheet_result.get('message')}")
                except Exception as e:
                    st.warning(f"SQLite guardado, pero Sheets no sincronizo: {e}")
                st.success(f"💾 Guardado con ID {pid}")
                st.rerun()

            if has_exact:
                st.warning("⚠️ Ya existe una predicción para este partido en la misma fecha.")
                with st.expander("Ver predicciones existentes", expanded=True):
                    for p in dup_check["exact"]:
                        c1, c2, c3 = st.columns(3)
                        c1.markdown(f"**ID {p['id']}** — {p['created_at'][:10]}")
                        c2.markdown(f"{p['home_team']} vs {p['away_team']}")
                        estado = (f"Real: {p['actual_home_goals']}-{p['actual_away_goals']}"
                                  if p.get("actual_result") else "Sin resultado")
                        c3.markdown(estado)

                cb1, cb2, cb3 = st.columns(3)
                if cb1.button("🚫 No guardar (duplicado)", use_container_width=True):
                    st.session_state["pending_save"] = False
                    st.session_state["dup_check"]    = None
                    st.info("Predicción calculada pero no guardada.")
                    st.rerun()
                if cb2.button("💾 Guardar igual (otro partido)",
                               use_container_width=True, type="primary"):
                    _do_save()
                if cb3.button("🔄 Reemplazar existente", use_container_width=True):
                    st.session_state["show_replace"] = True

                if st.session_state.get("show_replace"):
                    ids_exist = [p["id"] for p in dup_check["exact"]]
                    id_del    = st.selectbox("¿Cuál querés reemplazar?", ids_exist,
                                              format_func=lambda x: f"ID {x}")
                    if st.button("✅ Confirmar reemplazo", type="primary"):
                        if delete_prediction(id_del):
                            _do_save()
                        else:
                            st.error(f"No se pudo eliminar ID {id_del} "
                                     "(tiene resultado real cargado)")

            elif has_similar:
                st.info("ℹ️ Existen predicciones del mismo partido en otras fechas o fases.")
                with st.expander("Ver predicciones similares"):
                    for p in dup_check["similar"]:
                        c1, c2, c3, c4 = st.columns(4)
                        c1.markdown(f"**ID {p['id']}**")
                        c2.markdown(p["created_at"][:10])
                        c3.markdown(p.get("stage", "—"))
                        c4.markdown(f"Real: {p['actual_home_goals']}-{p['actual_away_goals']}"
                                    if p.get("actual_result") else "Pendiente")
                cs1, cs2 = st.columns(2)
                if cs1.button("💾 Guardar (es otro partido)",
                               use_container_width=True, type="primary"):
                    _do_save()
                if cs2.button("🚫 No guardar", use_container_width=True):
                    st.session_state["pending_save"] = False
                    st.session_state["dup_check"]    = None
                    st.info("No guardado.")
                    st.rerun()
            else:
                # Sin duplicados → guardar automáticamente
                _do_save()

        # ID guardado
        if res.get("pred_id") and not pending_save:
            st.caption(f"📌 Predicción guardada — ID: {res['pred_id']}")

        # ── Visualización del resultado ───────────────────────────
        st.divider()
        render_resultado(res, key_prefix="main")


    # ══════════════════════════════════════════════════════════════
