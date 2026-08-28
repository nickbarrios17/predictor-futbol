# ui/history_tab.py
import pandas as pd
import streamlit as st

from database.sqlite import (
    delete_prediction,
    get_all_predictions,
    get_competitions,
    get_seasons,
    get_summary_stats,
    init_db,
    load_result,
)
from database.sheets import (
    GSPREAD_AVAILABLE,
    sync_from_sheets,
    sync_to_sheets,
    update_result_row,
)


def render_history_tab() -> None:
    st.markdown("### 📋 Historial de predicciones")
    init_db()

    # ── Filtros ───────────────────────────────────────────────
    cf1, cf2, cf3, cf4 = st.columns(4)
    solo_eval  = cf1.toggle("Solo evaluadas", value=False)
    comps      = ["Todas"] + get_competitions()
    seasons    = ["Todas"] + get_seasons()
    filter_comp   = cf2.selectbox("Competición", comps)
    filter_season = cf3.selectbox("Temporada", seasons)
    filter_ver    = cf4.text_input("Versión modelo", placeholder="v2.0")

    # Stats globales (filtrables)
    stats = get_summary_stats(
        model_version = filter_ver   or None,
        competition   = (filter_comp   if filter_comp   != "Todas" else None),
        season        = (filter_season if filter_season != "Todas" else None),
    )

    if stats.get("total_evaluadas", 0) > 0:
        sm1, sm2, sm3, sm4, sm5 = st.columns(5)
        sm1.metric("Total evaluadas",   stats["total_evaluadas"])
        sm2.metric("Accuracy 1X2",      f"{stats['accuracy_1x2']}%")
        sm3.metric("Accuracy Over 2.5", f"{stats['accuracy_over25']}%")
        sm4.metric("Brier Score",       stats["avg_brier_score"],
                   help="Rango 0-1. Referencia sin info: 0.333")
        sm5.metric("Log Loss",          stats["avg_log_loss"],
                   help="Menor es mejor. Referencia: 1.099")
        st.divider()

    # ── Tabla ─────────────────────────────────────────────────
    preds = get_all_predictions(with_results_only=solo_eval)

    if not preds:
        st.info("No hay predicciones guardadas aún.")
    else:
        rows = []
        for p in preds:
            rows.append({
                "ID":           p["id"],
                "Fecha":        p["created_at"][:10],
                "Partido":      f"{p['home_team']} vs {p['away_team']}",
                "Competición":  p.get("competition","—"),
                "Temporada":    p.get("season","—"),
                "P(L)%":        p["prob_home"],
                "P(E)%":        p["prob_draw"],
                "P(V)%":        p["prob_away"],
                "Predicho":     p["predicted_result"],
                "Score pred.":  p.get("predicted_score","—"),
                "Real":         (f"{p['actual_home_goals']}-{p['actual_away_goals']}"
                                 if p.get("actual_home_goals") is not None else "Pendiente"),
                "✓":            ("✅" if p.get("result_correct")==1
                                  else "❌" if p.get("result_correct")==0
                                  else "⏳"),
                "Brier":        p.get("brier_score","—"),
                "Versión":      p.get("model_version","—"),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()

    # ── Acciones ──────────────────────────────────────────────
    col_acc1, col_acc2 = st.columns(2)

    with col_acc1:
        st.markdown("#### ➕ Cargar resultado real")
        ca1, ca2, ca3 = st.columns(3)
        pred_id_in = ca1.number_input("ID", min_value=1, step=1, key="load_id")
        gh_in      = ca2.number_input("Goles local",  min_value=0, step=1, key="load_gh")
        ga_in      = ca3.number_input("Goles visita", min_value=0, step=1, key="load_ga")

        if st.button("💾 Guardar resultado", use_container_width=True):
            try:
                metricas = load_result(int(pred_id_in), int(gh_in), int(ga_in))
                # Actualizar en el sheet
                try:
                    update_result_row(int(pred_id_in), metricas)
                except Exception:
                    pass
                if metricas.get("result_correct"):
                    st.success(f"✅ Predicción CORRECTA | Brier: {metricas['brier_score']}")
                else:
                    st.warning(f"❌ Predicción incorrecta | Brier: {metricas['brier_score']}")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    with col_acc2:
        # Fix Bug 3 — gestión de historial disponible siempre,
        # sin necesitar una predicción activa
        st.markdown("#### 🗑️ Eliminar predicción")
        st.caption("Solo se pueden eliminar predicciones SIN resultado real.")
        cd1, cd2 = st.columns([1,2])
        id_del = cd1.number_input("ID a eliminar", min_value=1, step=1, key="del_id")
        if cd2.button("🗑️ Eliminar", use_container_width=True):
            borrado = delete_prediction(int(id_del))
            if borrado:
                st.success(f"✅ ID {id_del} eliminado")
                # Sincronizar sheet
                try:
                    sync_to_sheets(get_all_predictions())
                except Exception:
                    pass
                st.rerun()
            else:
                st.error(f"No se pudo eliminar ID {id_del} "
                         "(no existe o tiene resultado real cargado)")

    st.divider()

    # ── Google Sheets ─────────────────────────────────────────
    st.markdown("#### 📊 Google Sheets")
    if not GSPREAD_AVAILABLE:
        st.warning("gspread no instalado. Corré: `pip install gspread google-auth`")
    else:
        cg1, cg2, cg3 = st.columns(3)

        if cg1.button("🔄 Sincronizar → Sheets", use_container_width=True,
                       help="Vuelca todo el historial al sheet"):
            with st.spinner("Sincronizando..."):
                r = sync_to_sheets(get_all_predictions())
                if r["ok"]:
                    st.success(r["message"])
                    if r.get("url"):
                        st.markdown(f"[Abrir pestaña '{r.get('worksheet')}']({r['url']})")
                else:
                    st.error(r["message"])
                    if r.get("url"):
                        st.markdown(f"[Abrir pestaña '{r.get('worksheet')}']({r['url']})")

        if cg2.button("📥 Importar resultados desde Sheets",
                       use_container_width=True,
                       help="Lee resultados reales escritos en el sheet"):
            with st.spinner("Leyendo sheet..."):
                pendientes = sync_from_sheets()
                if not pendientes:
                    st.info("No hay resultados nuevos en el sheet.")
                else:
                    ok = 0
                    for p in pendientes:
                        try:
                            met = load_result(p["id"], p["home_goals"], p["away_goals"])
                            update_result_row(p["id"], met)
                            ok += 1
                        except Exception:
                            pass
                    st.success(f"✅ {ok} resultados importados")
                    st.rerun()

        if cg3.button("🔗 Abrir Sheet", use_container_width=True):
            st.markdown(
                "[Abrir Google Sheet](https://docs.google.com/spreadsheets/d/"
                "1aHkzk4a6IgqJnXUV_Ouk-wn0mlLnaxkmKC0Dmc4ipyc/edit)",
                unsafe_allow_html=True
            )


    # ══════════════════════════════════════════════════════════════
