# ui/result_view.py
"""
Renderizado de un resultado de predicción ya calculado.

Extraído de ui/prediction_tab.py para poder reusarlo tal cual desde
ui/fixtures_tab.py (modo equipo/torneo), donde se muestran varios
resultados en la misma página. key_prefix evita colisiones de
key entre widgets cuando se llama esta función más de una vez.
"""
import pandas as pd
import streamlit as st

from ui.common import bar_html, confidence_tag, pct_color, pct_tag_class, _pct_result


def render_resultado(res: dict, key_prefix: str = "") -> None:
    ea  = res["equipo_a"]
    eb  = res["equipo_b"]
    ctx = res.get("context", {})
    ctx_raw    = res.get("context_raw", {})
    strength_a = res.get("strength_a", {})
    strength_b = res.get("strength_b", {})

    st.markdown(f"## {ea}  vs  {eb}")
    ci1, ci2, ci3 = st.columns(3)
    ci1.markdown(f"**Competición:** {ctx.get('competition') or '—'}")
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
    tab_ha, tab_hb = st.tabs([f"🔵 {ea}", f"🔴 {eb}"], key=f"{key_prefix}_hist_tabs")

    def render_historial(strength, team_name, df_key):
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
            icono = "✅" if int(gf)>int(gc) else ("➖" if int(gf)==int(gc) else "❌")
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
        st.dataframe(df, use_container_width=True, hide_index=True, key=df_key,
            column_config={"Peso total": st.column_config.ProgressColumn(
                "Peso total", min_value=0, max_value=1, format="%.4f")})

    with tab_ha: render_historial(strength_a, ea, f"{key_prefix}_hist_a")
    with tab_hb: render_historial(strength_b, eb, f"{key_prefix}_hist_b")

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
    with st.expander("🔧 Detalle técnico — lambdas", key=f"{key_prefix}_exp_lambdas"):
        ld = res.get("lambdas_detalle",{})
        if ld:
            st.markdown(f"""
| Paso | λ {ea} | λ {eb} |
|------|--------|--------|
| Base (incluye ventaja de sede) | `{ld.get('base',('—','—'))[0]}` | `{ld.get('base',('—','—'))[1]}` |
| Intensidad | `×{ld.get('intensity','—')}` | `×{ld.get('intensity','—')}` |
| Motivación | `×{ld.get('motivation',('—','—'))[0]}` | `×{ld.get('motivation',('—','—'))[1]}` |
| Alineación | `×{ld.get('lineup',(1,1))[0]}` | `×{ld.get('lineup',(1,1))[1]}` |
| Vuelta | `×{ld.get('second_leg',(1,1))[0]}` | `×{ld.get('second_leg',(1,1))[1]}` |
| **Final** | **`{ld.get('final',('—','—'))[0]}`** | **`{ld.get('final',('—','—'))[1]}`** |
""")

    # ── Comparativa modelo vs IA ──────────────────────────────
    with st.expander("📊 Comparativa: Modelo vs IA", key=f"{key_prefix}_exp_comparativa"):
        st.markdown("**🔢 Modelo estadístico (Poisson)**")
        resultado_modelo = _pct_result(res)
        st.markdown(f"Predicción: **{resultado_modelo}**")

        if ia and not ia.get("error"):
            st.markdown("**🧠 IA narrativa (Gemini)**")
            st.markdown(f"Predicción: **{ia.get('prediccion','—')}** "
                        f"| Marcador: **{ia.get('marcador_predicho','—')}** "
                        f"| Confianza: **{ia.get('confianza','—')}**")

    st.caption("⚽ Poisson + Dixon-Coles | 🧠 Gemini | 📡 SofaScore API | 🗄️ SQLite + Google Sheets")
