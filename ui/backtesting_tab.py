# ui/backtesting_tab.py
import traceback

import pandas as pd
import streamlit as st

from backtesting.backtester import backtest_equipo
from backtesting.metrics import (
    resumen_baselines,
    resumen_calibracion,
    resumen_metricas,
)
from data.fetcher import fetch_matches


def render_backtesting_tab() -> None:
    st.markdown("### 📊 Backtesting")
    st.caption("Evaluá el modelo sobre partidos históricos ya conocidos.")

    bb1, bb2, bb3 = st.columns(3)
    bt_team = bb1.text_input("Equipo", placeholder="Ej: Argentina")
    bt_n    = bb2.slider("Partidos de test", min_value=3, max_value=10, value=5)
    bt_type = bb3.selectbox("Tipo", ["default","seleccion","club_top","club_menor"])

    if st.button("▶️ Correr backtesting", type="primary", use_container_width=True):
        if not bt_team:
            st.error("Ingresá un equipo")
        else:
            with st.spinner(f"Corriendo backtesting para {bt_team}..."):
                try:
                    matches = fetch_matches(bt_team, bt_type)
                    if len(matches) < bt_n + 5:
                        st.error(f"Historial insuficiente: {len(matches)} partidos "
                                 f"(mínimo {bt_n + 5})")
                    else:
                        resultados = backtest_equipo(
                            matches, bt_team, n_test=bt_n,
                            venue="auto",
                            team_type=bt_type,
                            fetch_rival_history=True,
                            verbose=False
                        )
                        if not resultados:
                            st.warning("Sin resultados")
                        else:
                            resumen = resumen_metricas(resultados, label=bt_team)
                            st.divider()
                            st.markdown(f"#### {bt_team} — {resumen['total_partidos']} partidos")

                            br1, br2, br3, br4 = st.columns(4)
                            br1.metric("Accuracy 1X2",      f"{resumen['accuracy_1x2']}%")
                            br2.metric("Accuracy Over 2.5", f"{resumen['accuracy_over25']}%")
                            br3.metric("Avg Brier Score",   resumen['avg_brier_score'],
                                       delta="ref: 0.333", delta_color="off")
                            br4.metric("Avg Log Loss",      resumen['avg_log_loss'],
                                       delta="ref: 1.099", delta_color="off")

                            base = resumen_baselines(resultados)
                            if base:
                                st.markdown("##### Comparacion contra baselines")
                                base_rows = [{
                                    "Modelo": "Predictor actual",
                                    "Accuracy 1X2": resumen["accuracy_1x2"],
                                    "Brier": resumen["avg_brier_score"],
                                    "LogLoss": resumen["avg_log_loss"],
                                }]
                                for name, b in base.items():
                                    base_rows.append({
                                        "Modelo": name,
                                        "Accuracy 1X2": b["accuracy_1x2"],
                                        "Brier": b["avg_brier_score"],
                                        "LogLoss": b["avg_log_loss"],
                                    })
                                st.dataframe(pd.DataFrame(base_rows),
                                             use_container_width=True,
                                             hide_index=True)

                            st.divider()
                            calibracion = resumen_calibracion(resultados)
                            if calibracion:
                                st.markdown("##### Calibracion por confianza")
                                st.caption(
                                    "Compara la confianza promedio del pick elegido "
                                    "contra el acierto real observado."
                                )
                                st.dataframe(
                                    pd.DataFrame([{
                                        "Rango": r["rango"],
                                        "N": r["n"],
                                        "Confianza media": f"{r['confianza_media']}%",
                                        "Acierto real": f"{r['acierto_real']}%",
                                        "Diferencia": f"{r['diferencia']}%",
                                        "Estado": r["estado"],
                                    } for r in calibracion]),
                                    use_container_width=True,
                                    hide_index=True,
                                )
                                if resumen["total_partidos"] < 30:
                                    st.info(
                                        "La muestra todavia es chica; usalo como senal, "
                                        "no como conclusion definitiva."
                                    )

                            st.divider()
                            bp1, bp2, bp3 = st.columns(3)
                            bp1.metric("Precisión Home",  f"{resumen['precision_home']}%",
                                       help=f"n={resumen['n_pred_home']}")
                            bp2.metric("Precisión Empate",f"{resumen['precision_draw']}%",
                                       help=f"n={resumen['n_pred_draw']}")
                            bp3.metric("Precisión Away",  f"{resumen['precision_away']}%",
                                       help=f"n={resumen['n_pred_away']}")

                            det = []
                            for r in resumen.get("detalle",[]):
                                det.append({
                                    "Partido":  r.get("partido_modelo", r.get("partido","—")),
                                    "Fecha":    r.get("fecha","—"),
                                    "Real":     r.get("resultado_real","—"),
                                    "Predicho": r.get("predicted_result","—"),
                                    "✓ 1X2":    "✅" if r["result_correct"] else "❌",
                                    "✓ O2.5":   "✅" if r["over25_correct"] else "❌",
                                    "✓ BTTS":   "✅" if r["btts_correct"]   else "❌",
                                    "Brier":    r["brier_score"],
                                    "LogLoss":  r["log_loss"],
                                    "Hist. A":   r.get("train_matches_a","—"),
                                    "Hist. B":   r.get("train_matches_b","—"),
                                    "Fuente rival": r.get("rival_source","—"),
                                })
                            st.dataframe(pd.DataFrame(det),
                                         use_container_width=True, hide_index=True)
                except Exception as e:
                    st.error(f"Error: {e}")
                    st.code(traceback.format_exc())
