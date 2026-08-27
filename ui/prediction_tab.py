# ui/prediction_tab.py
import traceback

import pandas as pd
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
from ui.common import bar_html, confidence_tag, pct_color, pct_tag_class, _pct_result


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
        ea  = res["equipo_a"]
        eb  = res["equipo_b"]
        ctx = res.get("context", {})
        ctx_raw    = res.get("context_raw", {})
        strength_a = res.get("strength_a", {})
        strength_b = res.get("strength_b", {})

        st.markdown(f"## {ea}  vs  {eb}")
        ci1, ci2, ci3 = st.columns(3)
        ci1.markdown(f"**Competición:** {ctx.get('competition') or competition or '—'}")
        ci2.markdown(f"**Tipo:** `{ctx.get('stage','—')}`")
        ci3.markdown(f"**Confianza IA:** {confidence_tag(ctx_raw.get('confidence','low'))}",
                     unsafe_allow_html=True)
        if ctx_raw.get("notes"):
            st.info(f"📝 {ctx_raw['notes']}")

        st.divider()

        # ── 1X2 ──────────────────────────────────────────────────
        st.markdown("### 🎯 Probabilidades principales")
        va, emp, vb = res["victoria_a"], res["empate"], res["victoria_b"]
        cv1, cv2, cv3 = st.columns(3)
        for col, label, pct in [(cv1, ea, va), (cv2, "Empate", emp), (cv3, eb, vb)]:
            color = pct_color(pct)
            col.markdown(f"""
            <div class="metric-card">
              <div class="metric-label">{"Victoria " if label != "Empate" else ""}{label}</div>
              <div class="metric-value" style="color:{color}">{pct}%</div>
              {bar_html(pct, color)}
            </div>""", unsafe_allow_html=True)

        st.markdown(f"""<p style="text-align:center;color:#666;font-size:12px;margin-top:8px;">
          λ {ea}: <b>{res['lambda_a']}</b> &nbsp;|&nbsp;
          λ {eb}: <b>{res['lambda_b']}</b> &nbsp;|&nbsp;
          Sede: <b>{res.get('venue','neutral')}</b></p>""",
          unsafe_allow_html=True)

        st.divider()

        # ── Marcadores + O/U + BTTS ───────────────────────────────
        cs, co = st.columns([1,1])

        with cs:
            st.markdown("### ⚽ Marcadores más probables")
            for i, (score, pct) in enumerate(res.get("top_marcadores",[])[:5], 1):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;'
                    f'padding:8px 0;border-bottom:1px solid #1e2a3a;">'
                    f'<b style="font-size:18px;">{score}</b>'
                    f'<span class="tag {pct_tag_class(pct)}">{pct}%</span></div>',
                    unsafe_allow_html=True)

        with co:
            st.markdown("### 📊 Over / Under")
            ou = res.get("ou", {})
            for label, key in [("0.5","05"),("1.5","15"),("2.5","25"),("3.5","35")]:
                ov = ou.get(f"over_{key}", 0)
                un = ou.get(f"under_{key}", 0)
                c_o, _, c_u = st.columns([5,1,5])
                c_o.markdown(f'Over {label} <span class="tag {pct_tag_class(ov)}">{ov}%</span>',
                             unsafe_allow_html=True)
                c_u.markdown(f'Under {label} <span class="tag {pct_tag_class(un)}">{un}%</span>',
                             unsafe_allow_html=True)

            st.markdown("### 🥅 BTTS")
            bs, bn = res.get("btts_si",0), res.get("btts_no",0)
            cb1, cb2 = st.columns(2)
            cb1.markdown(f'**Sí** <span class="tag {pct_tag_class(bs)}">{bs}%</span>',
                         unsafe_allow_html=True)
            cb2.markdown(f'**No** <span class="tag {pct_tag_class(bn)}">{bn}%</span>',
                         unsafe_allow_html=True)

        st.divider()

        # ── Historial analizado ───────────────────────────────────
        st.markdown("### 📋 Historial analizado")
        tab_ha, tab_hb = st.tabs([f"🔵 {ea}", f"🔴 {eb}"])

        def render_historial(strength, team_name):
            desglose = strength.get("desglose", [])
            if not desglose:
                st.info("Modo verbose no activo.")
                return

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Elo Rating",    f"{strength.get('team_elo','—')}",
                      delta=strength.get("elo_categoria",""), delta_color="off")
            c2.metric("Ataque",        f"L:{round(strength.get('attack_home',0),3)} / V:{round(strength.get('attack_away',0),3)}")
            c3.metric("Defensa",       f"L:{round(strength.get('defense_home',0),3)} / V:{round(strength.get('defense_away',0),3)}")
            c4.metric("Partidos",      strength.get("partidos_usados","—"))

            rows = []
            for m in desglose:
                sede = "🏠" if m["sede"]=="L" else "✈️"
                gf, gc = m["goles"].split("-")
                if m["sede"]=="L":
                    icono = "✅" if int(gf)>int(gc) else ("➖" if int(gf)==int(gc) else "❌")
                else:
                    icono = "✅" if int(gc)>int(gf) else ("➖" if int(gc)==int(gf) else "❌")
                rows.append({
                    "Fecha":        m["fecha"],
                    "Rival":        m["rival"],
                    "Elo rival":    m.get("rival_elo","—"),
                    "Factor rival": round(m["opp_factor"],2) if m.get("opp_factor") else "—",
                    "Sede":         sede,
                    "Resultado":    f"{icono} {m['goles']}",
                    "Goles adj.":   m.get("goles_adj","—"),
                    "Competición":  m["comp"],
                    "w_tiempo":     round(m["w_time"],3),
                    "w_comp":       round(m["w_comp"],3),
                    "w_stakes":     round(m["w_stakes"],3),
                    "Peso total":   m["w_total"],
                })
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True,
                column_config={"Peso total": st.column_config.ProgressColumn(
                    "Peso total", min_value=0, max_value=1, format="%.4f")})

        with tab_ha: render_historial(strength_a, ea)
        with tab_hb: render_historial(strength_b, eb)

        st.divider()

        # ── Análisis de IA ────────────────────────────────────────
        ia = res.get("analisis_ia", {})
        if ia and not ia.get("error"):
            st.markdown("### 🧠 Análisis de la IA")
            st.caption("La IA razona exclusivamente sobre los datos calculados.")

            pred_ia  = ia.get("prediccion","?")
            marc_ia  = ia.get("marcador_predicho","?-?")
            conf_ia  = ia.get("confianza","baja")
            coincide = ia.get("coincide_modelo")

            _cc = {"alta":"#2ecc71","media":"#f39c12","baja":"#e74c3c"}.get(conf_ia,"#888")
            _coin = ('<span class="tag tag-green">✅ Coincide</span>' if coincide is True
                     else '<span class="tag tag-red">⚠️ Difiere</span>' if coincide is False
                     else '<span class="tag tag-gray">?</span>')

            cp1, cp2, cp3 = st.columns(3)
            cp1.markdown(f'<div class="metric-card" style="border-left:4px solid {_cc};">'
                         f'<div class="metric-label">Predicción IA</div>'
                         f'<div class="metric-value" style="font-size:18px;color:{_cc};">{pred_ia}</div>'
                         f'</div>', unsafe_allow_html=True)
            cp2.markdown(f'<div class="metric-card" style="border-left:4px solid #3498db;">'
                         f'<div class="metric-label">Marcador IA</div>'
                         f'<div class="metric-value" style="font-size:28px;color:#3498db;">{marc_ia}</div>'
                         f'</div>', unsafe_allow_html=True)
            cp3.markdown(f'<div class="metric-card"><div class="metric-label">Confianza</div>'
                         f'<div class="metric-value" style="font-size:18px;color:{_cc};">{conf_ia.upper()}</div>'
                         f'<div style="margin-top:10px;">{_coin}</div></div>', unsafe_allow_html=True)

            st.markdown("")
            txt = ia.get("analisis","")
            if txt:
                st.markdown(f'<div style="background:#1a2a3a;border-left:4px solid #3498db;'
                            f'padding:16px 20px;border-radius:0 10px 10px 0;'
                            f'font-size:15px;line-height:1.7;color:#ccd;">{txt}</div>',
                            unsafe_allow_html=True)

            st.markdown("")
            fa = ia.get("fortaleza_ofensiva_a","")
            fb = ia.get("fortaleza_ofensiva_b","")
            if fa or fb:
                cfa, cfb = st.columns(2)
                if fa: cfa.markdown(f"**⚔️ Ataque {ea}**\n\n{fa}")
                if fb: cfb.markdown(f"**⚔️ Ataque {eb}**\n\n{fb}")

            factores = ia.get("factores_clave",[])
            if factores:
                st.markdown("**🔑 Factores clave**")
                for i, f in enumerate(factores,1):
                    st.markdown(f'<div style="padding:7px 0;border-bottom:1px solid #1e2a3a;'
                                f'font-size:14px;"><span style="color:#3498db;font-weight:bold;">'
                                f'#{i}</span>&nbsp; {f}</div>', unsafe_allow_html=True)

            mercados = ia.get("mercados_recomendados",[])
            if mercados:
                st.markdown("")
                st.markdown("**📈 Mercados con valor**")
                for m in mercados:
                    st.markdown(f'<div style="background:#1a3a2a;border-left:3px solid #2ecc71;'
                                f'padding:8px 14px;margin:4px 0;border-radius:0 6px 6px 0;'
                                f'font-size:14px;">✅ {m}</div>', unsafe_allow_html=True)

            for adv in ia.get("advertencias",[]):
                st.warning(adv)

        elif ia and ia.get("error"):
            st.info(f"🧠 IA no disponible: {ia.get('error')} — "
                    f"verificá `GEMINI_API_KEY` y tu conexión a internet.")

        # ── Detalle técnico ───────────────────────────────────────
        with st.expander("🔧 Detalle técnico — lambdas"):
            ld = res.get("lambdas_detalle",{})
            if ld:
                st.markdown(f"""
    | Paso | λ {ea} | λ {eb} |
    |------|--------|--------|
    | Base (incluye ventaja de sede) | `{ld.get('base',('—','—'))[0]}` | `{ld.get('base',('—','—'))[1]}` |
    | Intensidad | `×{ld.get('intensity','—')}` | `×{ld.get('intensity','—')}` |
    | Motivación | `×{ld.get('motivation',('—','—'))[0]}` | `×{ld.get('motivation',('—','—'))[1]}` |
    | Vuelta | `×{ld.get('second_leg',(1,1))[0]}` | `×{ld.get('second_leg',(1,1))[1]}` |
    | **Final** | **`{ld.get('final',('—','—'))[0]}`** | **`{ld.get('final',('—','—'))[1]}`** |
    """)

        # ── Comparativa modelo vs IA ──────────────────────────────
        with st.expander("📊 Comparativa: Modelo vs IA"):
            st.markdown("**🔢 Modelo estadístico (Poisson)**")
            resultado_modelo = _pct_result(res)
            st.markdown(f"Predicción: **{resultado_modelo}**")

            if ia and not ia.get("error"):
                st.markdown("**🧠 IA narrativa (Gemini)**")
                st.markdown(f"Predicción: **{ia.get('prediccion','—')}** "
                            f"| Marcador: **{ia.get('marcador_predicho','—')}** "
                            f"| Confianza: **{ia.get('confianza','—')}**")

        st.caption("⚽ Poisson + Monte Carlo 10k iter. | 🧠 Gemini | 📡 SofaScore API | 🗄️ SQLite + Google Sheets")


    # ══════════════════════════════════════════════════════════════
