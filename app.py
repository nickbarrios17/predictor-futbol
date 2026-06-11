# app.py
import streamlit as st
import pandas as pd
import predictor
from sources.api_source import search_team

# ── Configuración ─────────────────────────────────────────────
st.set_page_config(
    page_title="Predictor de Fútbol ⚽",
    page_icon="⚽",
    layout="wide",
)

# ── CSS personalizado ─────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: #1e2a3a;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #2e3f52;
    }
    .metric-label { color: #8899aa; font-size: 13px; margin-bottom: 4px; }
    .metric-value { color: #ffffff; font-size: 32px; font-weight: bold; }
    .metric-win   { color: #2ecc71; }
    .metric-draw  { color: #f39c12; }
    .metric-lose  { color: #e74c3c; }
    .tag {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 12px;
        font-weight: bold;
        margin: 2px;
    }
    .tag-green  { background: #1a4a2e; color: #2ecc71; }
    .tag-orange { background: #4a3000; color: #f39c12; }
    .tag-red    { background: #4a1a1a; color: #e74c3c; }
    .tag-blue   { background: #1a2a4a; color: #3498db; }
    .tag-gray   { background: #2a2a2a; color: #888888; }
    .section-header {
        font-size: 15px;
        font-weight: bold;
        color: #8899aa;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid #2e3f52;
    }
    .match-row {
        display: flex;
        justify-content: space-between;
        padding: 6px 0;
        border-bottom: 1px solid #1e2a3a;
        font-size: 14px;
    }
    .bar-container {
        background: #1e2a3a;
        border-radius: 6px;
        height: 8px;
        width: 100%;
        margin-top: 4px;
    }
    .bar-fill {
        height: 8px;
        border-radius: 6px;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers de color ──────────────────────────────────────────

def pct_color(pct: float) -> str:
    if pct >= 50:  return "#2ecc71"
    if pct >= 35:  return "#f39c12"
    return "#e74c3c"

def pct_tag_class(pct: float) -> str:
    if pct >= 50:  return "tag-green"
    if pct >= 35:  return "tag-orange"
    return "tag-red"

def confidence_tag(conf: str) -> str:
    mapping = {
        "high":   ("tag-green",  "Alta ✅"),
        "medium": ("tag-orange", "Media ⚠️"),
        "low":    ("tag-red",    "Baja ❌"),
    }
    css, label = mapping.get(conf, ("tag-gray", conf or "?"))
    return f'<span class="tag {css}">{label}</span>'

def lineup_tag(status: str) -> str:
    mapping = {
        "full":     ("tag-green",  "Titulares"),
        "rotation": ("tag-orange", "Rotación"),
        "reserves": ("tag-red",    "Reservas"),
        "unknown":  ("tag-gray",   "Desconocido"),
    }
    css, label = mapping.get(status, ("tag-gray", status or "?"))
    return f'<span class="tag {css}">{label}</span>'

def bar_html(pct: float, color: str) -> str:
    return f"""
    <div class="bar-container">
      <div class="bar-fill" style="width:{pct}%; background:{color};"></div>
    </div>"""


# ── Estado de sesión ──────────────────────────────────────────
for key in ["candidatos_a", "candidatos_b", "resultado"]:
    if key not in st.session_state:
        st.session_state[key] = None


# ── Header ────────────────────────────────────────────────────
st.markdown("# ⚽ Predictor de Fútbol")
st.markdown("Modelo estadístico con Poisson + Monte Carlo + IA local")
st.divider()


# ── Búsqueda de equipos ───────────────────────────────────────
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
        seleccion_a = st.selectbox(
            "Seleccionar equipo A",
            candidatos_a,
            format_func=lambda x: x.get("name", "N/A"),
            key="sel_a",
        )
        name_a = seleccion_a["name"] if seleccion_a else busqueda_a
        team_id_a = seleccion_a["id"] if seleccion_a else None
        st.success(f"✅ {name_a} (ID: {team_id_a})")
    else:
        name_a = busqueda_a
        team_id_a = None

with col2:
    st.markdown("#### 🔴 Equipo B")
    busqueda_b = st.text_input("Buscar equipo B", key="search_b",
                                placeholder="Ej: Boca Juniors, Barcelona...")
    if st.button("🔍 Buscar B", use_container_width=True):
        with st.spinner("Buscando..."):
            st.session_state["candidatos_b"] = search_team(busqueda_b)

    candidatos_b = st.session_state["candidatos_b"]
    if candidatos_b:
        seleccion_b = st.selectbox(
            "Seleccionar equipo B",
            candidatos_b,
            format_func=lambda x: x.get("name", "N/A"),
            key="sel_b",
        )
        name_b = seleccion_b["name"] if seleccion_b else busqueda_b
        team_id_b = seleccion_b["id"] if seleccion_b else None
        st.success(f"✅ {name_b} (ID: {team_id_b})")
    else:
        name_b = busqueda_b
        team_id_b = None


# ── Parámetros del partido ────────────────────────────────────
st.divider()
col3, col4, col5 = st.columns(3)

with col3:
    venue = st.selectbox(
        "Sede",
        ["neutral", "home_a", "home_b"],
        format_func=lambda x: {
            "neutral": "⚖️ Cancha neutral",
            "home_a":  f"🏠 Local: Equipo A",
            "home_b":  f"🏠 Local: Equipo B",
        }[x],
    )
with col4:
    competition = st.text_input(
        "Competición (opcional)",
        placeholder="Champions, Liga, Copa...",
        key="competition",
    )
with col5:
    team_type = st.selectbox(
        "Tipo de equipo",
        ["default", "seleccion", "club_top", "club_menor"],
        format_func=lambda x: {
            "default":    "🏆 Default (20 partidos)",
            "seleccion":  "🌍 Selección (15 partidos)",
            "club_top":   "⭐ Club top (25 partidos)",
            "club_menor": "🏅 Club menor (18 partidos)",
        }[x],
    )

# ── Botón principal ───────────────────────────────────────────
st.divider()
if st.button("🚀 Calcular predicción", use_container_width=True, type="primary"):
    if not name_a or not name_b:
        st.error("Por favor ingresá ambos equipos.")
    elif name_a == name_b:
        st.error("Los dos equipos no pueden ser el mismo.")
    else:
        with st.spinner("⏳ Obteniendo historial, noticias y simulando... (puede tardar 30-60 seg)"):
            try:
                res = predictor.predecir(
                    name_a, name_b,
                    venue=venue,
                    competition=competition,
                    team_type=team_type,
                    verbose=True,
                )
                st.session_state["resultado"] = res
            except Exception as e:
                st.error(f"❌ Error: {e}")
                st.session_state["resultado"] = None


# ── Mostrar resultado ─────────────────────────────────────────
res = st.session_state.get("resultado")
if not res:
    st.stop()

ea = res["equipo_a"]
eb = res["equipo_b"]
ctx = res.get("context", {})
ctx_raw = res.get("context_raw", {})
strength_a = res.get("strength_a", {})
strength_b = res.get("strength_b", {})

st.divider()
st.markdown(f"## {ea}  vs  {eb}")

# Contexto detectado
stage     = ctx.get("stage", "—")
conf      = ctx.get("confidence", "low")
notas     = ctx.get("notes", "")

col_info1, col_info2, col_info3 = st.columns(3)
col_info1.markdown(f"**Competición:** {ctx.get('competition') or competition or '—'}")
col_info2.markdown(f"**Tipo:** `{stage}`")
col_info3.markdown(f"**Confianza IA:** {confidence_tag(conf)}", unsafe_allow_html=True)
if notas:
    st.info(f"📝 {notas}")

st.divider()

# ════════════════════════════════════════════════════════════════
# SECCIÓN 1 — PROBABILIDADES 1X2
# ════════════════════════════════════════════════════════════════
st.markdown("### 🎯 Probabilidades principales")

va  = res["victoria_a"]
emp = res["empate"]
vb  = res["victoria_b"]

col_va, col_emp, col_vb = st.columns(3)

with col_va:
    color = pct_color(va)
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Victoria {ea}</div>
      <div class="metric-value" style="color:{color}">{va}%</div>
      {bar_html(va, color)}
    </div>""", unsafe_allow_html=True)

with col_emp:
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Empate</div>
      <div class="metric-value" style="color:#f39c12">{emp}%</div>
      {bar_html(emp, "#f39c12")}
    </div>""", unsafe_allow_html=True)

with col_vb:
    color = pct_color(vb)
    st.markdown(f"""
    <div class="metric-card">
      <div class="metric-label">Victoria {eb}</div>
      <div class="metric-value" style="color:{color}">{vb}%</div>
      {bar_html(vb, color)}
    </div>""", unsafe_allow_html=True)

st.markdown(f"""
<p style="text-align:center; color:#666; font-size:12px; margin-top:8px;">
  λ {ea}: <b>{res['lambda_a']}</b> &nbsp;|&nbsp; λ {eb}: <b>{res['lambda_b']}</b>
  &nbsp;|&nbsp; Sede: <b>{res.get('venue','neutral')}</b>
</p>""", unsafe_allow_html=True)

st.divider()

# ════════════════════════════════════════════════════════════════
# SECCIÓN 2 — MARCADORES + OVER/UNDER + BTTS
# ════════════════════════════════════════════════════════════════
col_scores, col_ou = st.columns([1, 1])

with col_scores:
    st.markdown("### ⚽ Marcadores más probables")
    for i, (score, pct) in enumerate(res.get("top_marcadores", []), 1):
        color = pct_color(pct)
        st.markdown(f"""
        <div style="display:flex; justify-content:space-between;
                    align-items:center; padding:8px 0;
                    border-bottom:1px solid #1e2a3a;">
          <span style="font-size:15px;">
            <b style="color:#aaa;">#{i}</b> &nbsp;
            <b style="font-size:18px;">{score}</b>
          </span>
          <span class="tag {pct_tag_class(pct)}">{pct}%</span>
        </div>""", unsafe_allow_html=True)

with col_ou:
    st.markdown("### 📊 Over / Under")
    ou = res.get("ou", {})
    lineas = [("0.5", "05"), ("1.5", "15"), ("2.5", "25"), ("3.5", "35")]
    for label, key in lineas:
        ov = ou.get(f"over_{key}", 0)
        un = ou.get(f"under_{key}", 0)
        col_o, col_sep, col_u = st.columns([5, 1, 5])
        col_o.markdown(
            f'Over {label} <span class="tag {pct_tag_class(ov)}">{ov}%</span>',
            unsafe_allow_html=True,
        )
        col_sep.markdown("<div style='text-align:center;color:#444'>|</div>",
                         unsafe_allow_html=True)
        col_u.markdown(
            f'Under {label} <span class="tag {pct_tag_class(un)}">{un}%</span>',
            unsafe_allow_html=True,
        )

    st.markdown("### 🥅 Ambos equipos marcan (BTTS)")
    btts_si = res.get("btts_si", 0)
    btts_no = res.get("btts_no", 0)
    c_si, c_no = st.columns(2)
    c_si.markdown(
        f'**Sí** &nbsp; <span class="tag {pct_tag_class(btts_si)}">{btts_si}%</span>',
        unsafe_allow_html=True,
    )
    c_no.markdown(
        f'**No** &nbsp; <span class="tag {pct_tag_class(btts_no)}">{btts_no}%</span>',
        unsafe_allow_html=True,
    )

st.divider()

# ════════════════════════════════════════════════════════════════
# SECCIÓN 3 — HISTORIAL USADO POR EL MODELO
# ════════════════════════════════════════════════════════════════
st.markdown("### 📋 Historial analizado")

tab_a, tab_b = st.tabs([f"🔵 {ea}", f"🔴 {eb}"])

def render_historial(strength: dict, team_name: str):
    desglose = strength.get("desglose", [])
    if not desglose:
        st.info("El historial detallado solo está disponible en modo verbose. "
                "Si ves esto, revisá que verbose=True en predictor.py.")
        return

    st.markdown(f"""
    <div style="margin-bottom:12px;">
      λ ataque: <b>{strength.get('lambda_ataque','—')}</b> &nbsp;|&nbsp;
      λ defensa: <b>{strength.get('lambda_defensa','—')}</b> &nbsp;|&nbsp;
      Partidos usados: <b>{strength.get('partidos_usados','—')}</b>
    </div>""", unsafe_allow_html=True)

    rows = []
    for m in desglose:
        sede_icon = "🏠" if m["sede"] == "L" else "✈️"
        goles = m["goles"]
        gf, gc = goles.split("-")
        if m["sede"] == "L":
            resultado = f"{goles}"
            if int(gf) > int(gc):   icono = "✅"
            elif int(gf) == int(gc): icono = "➖"
            else:                    icono = "❌"
        else:
            resultado = f"{goles}"
            if int(gc) > int(gf):   icono = "✅"
            elif int(gc) == int(gf): icono = "➖"
            else:                    icono = "❌"

        rows.append({
            "Fecha":       m["fecha"],
            "Rival":       m["rival"],
            "Sede":        sede_icon,
            "Resultado":   f"{icono} {resultado}",
            "Competición": m["comp"],
            "w_tiempo":    m["w_time"],
            "w_comp":      m["w_comp"],
            "w_stakes":    m["w_stakes"],
            "w_lineup":    m["w_lineup"],
            "Peso total":  m["w_total"],
        })

    df = pd.DataFrame(rows)
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Peso total": st.column_config.ProgressColumn(
                "Peso total",
                min_value=0,
                max_value=1,
                format="%.4f",
            ),
        },
    )

with tab_a:
    render_historial(strength_a, ea)

with tab_b:
    render_historial(strength_b, eb)

st.divider()

# ════════════════════════════════════════════════════════════════
# SECCIÓN 4 — DETALLE DE LA IA (formateado, no JSON crudo)
# ════════════════════════════════════════════════════════════════
st.markdown("### 🤖 Análisis de la IA")

noticias_chars = len(res.get("context_raw", {}).get("_noticias_raw", ""))

col_ai1, col_ai2 = st.columns(2)

with col_ai1:
    st.markdown(f"""
    <div class="section-header">Contexto detectado</div>
    <table style="width:100%; font-size:14px; border-collapse:collapse;">
      <tr><td style="color:#888; padding:5px 0;">Tipo de partido</td>
          <td><code>{ctx_raw.get('stage','—')}</code></td></tr>
      <tr><td style="color:#888; padding:5px 0;">¿Partido de vuelta?</td>
          <td>{'Sí ✅' if ctx_raw.get('is_second_leg') else 'No'}</td></tr>
      <tr><td style="color:#888; padding:5px 0;">Resultado ida</td>
          <td>{ctx_raw.get('first_leg_score') or '—'}</td></tr>
      <tr><td style="color:#888; padding:5px 0;">Confianza</td>
          <td>{confidence_tag(ctx_raw.get('confidence','low'))}</td></tr>
      <tr><td style="color:#888; padding:5px 0;">Noticias procesadas</td>
          <td>{noticias_chars:,} caracteres</td></tr>
    </table>
    """, unsafe_allow_html=True)

with col_ai2:
    st.markdown(f"""
    <div class="section-header">Situación de cada equipo</div>
    <table style="width:100%; font-size:14px; border-collapse:collapse;">
      <tr>
        <td style="color:#888; width:130px; padding:5px 0;">Motivación {ea}</td>
        <td><code>{ctx_raw.get('motivation_a','—')}</code></td>
      </tr>
      <tr>
        <td style="color:#888; padding:5px 0;">Motivación {eb}</td>
        <td><code>{ctx_raw.get('motivation_b','—')}</code></td>
      </tr>
      <tr>
        <td style="color:#888; padding:5px 0;">Alineación {ea}</td>
        <td>{lineup_tag(ctx_raw.get('lineup_status_a','unknown'))}</td>
      </tr>
      <tr>
        <td style="color:#888; padding:5px 0;">Alineación {eb}</td>
        <td>{lineup_tag(ctx_raw.get('lineup_status_b','unknown'))}</td>
      </tr>
    </table>
    """, unsafe_allow_html=True)

# Bajas
injuries_a = ctx_raw.get("injuries_a", [])
injuries_b = ctx_raw.get("injuries_b", [])

if injuries_a or injuries_b:
    st.markdown("")
    col_inj_a, col_inj_b = st.columns(2)
    with col_inj_a:
        if injuries_a:
            st.markdown(f"**🚑 Bajas {ea}:**")
            for p in injuries_a:
                st.markdown(f"- {p}")
        else:
            st.markdown(f"**{ea}:** Sin bajas reportadas ✅")
    with col_inj_b:
        if injuries_b:
            st.markdown(f"**🚑 Bajas {eb}:**")
            for p in injuries_b:
                st.markdown(f"- {p}")
        else:
            st.markdown(f"**{eb}:** Sin bajas reportadas ✅")

# Notas de la IA
if ctx_raw.get("notes"):
    st.markdown("")
    st.markdown("**📝 Análisis de la IA:**")
    st.markdown(
        f'<div style="background:#1e2a3a; border-left:3px solid #3498db; '
        f'padding:12px 16px; border-radius:0 8px 8px 0; font-size:14px;">'
        f'{ctx_raw["notes"]}</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ════════════════════════════════════════════════════════════════
# SECCIÓN 5 — DETALLE DE LAMBDAS (técnico, colapsado)
# ════════════════════════════════════════════════════════════════
with st.expander("🔧 Detalle técnico del modelo (lambdas)"):
    lambdas = res.get("lambdas_detalle", {})
    if lambdas:
        st.markdown(f"""
        | Paso | λ {ea} | λ {eb} |
        |------|--------|--------|
        | Base (ataque × defensa rival) | `{lambdas.get('base',('—','—'))[0]}` | `{lambdas.get('base',('—','—'))[1]}` |
        | Tras ajuste sede | `{lambdas.get('post_sede',('—','—'))[0]}` | `{lambdas.get('post_sede',('—','—'))[1]}` |
        | Intensidad del partido | `×{lambdas.get('intensity','—')}` | `×{lambdas.get('intensity','—')}` |
        | Motivación | `×{lambdas.get('motivation',('—','—'))[0]}` | `×{lambdas.get('motivation',('—','—'))[1]}` |
        | Ajuste vuelta | `×{lambdas.get('second_leg',('—','—'))[0]}` | `×{lambdas.get('second_leg',('—','—'))[1]}` |
        | **Lambda final** | **`{lambdas.get('final',('—','—'))[0]}`** | **`{lambdas.get('final',('—','—'))[1]}`** |
        """)
    else:
        st.info("Datos técnicos no disponibles.")

st.caption("⚽ Modelo: Poisson Bivariado + Monte Carlo 10.000 iter. | IA: Ollama local | Datos: SofaScore API")
