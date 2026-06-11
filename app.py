import streamlit as st
import pandas as pd
import predictor
from sources.api_source import search_team

st.set_page_config(page_title="Predicciones Fútbol", page_icon="⚽", layout="centered")

FLAGS = {
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "Germany": "🇩🇪", "France": "🇫🇷",
    "Spain": "🇪🇸", "Mexico": "🇲🇽", "South Africa": "🇿🇦",
}


def init_app_state():
    if 'candidatos_a' not in st.session_state:
        st.session_state['candidatos_a'] = None
    if 'candidatos_b' not in st.session_state:
        st.session_state['candidatos_b'] = None


init_app_state()

st.title("⚽ Predictor IA con Transparencia")

col1, col2 = st.columns(2)
with col1:
    busqueda_a = st.text_input("Buscar Equipo A", key="search_a")
    if st.button("🔍 Buscar A"):
        st.session_state['candidatos_a'] = search_team(busqueda_a)
    candidatos_a = st.session_state.get('candidatos_a')
    seleccion_a = (
        st.selectbox("Seleccionar A", candidatos_a or [], format_func=lambda x: x.get('name', 'N/A'))
        if candidatos_a else None
    )
    name_a = seleccion_a.get('name') if seleccion_a else busqueda_a

with col2:
    busqueda_b = st.text_input("Buscar Equipo B", key="search_b")
    if st.button("🔍 Buscar B"):
        st.session_state['candidatos_b'] = search_team(busqueda_b)
    candidatos_b = st.session_state.get('candidatos_b')
    seleccion_b = (
        st.selectbox("Seleccionar B", candidatos_b or [], format_func=lambda x: x.get('name', 'N/A'))
        if candidatos_b else None
    )
    name_b = seleccion_b.get('name') if seleccion_b else busqueda_b

col3, col4 = st.columns(2)
with col3:
    venue = st.selectbox(
        "Sede", ["neutral", "home_a", "home_b"],
        format_func=lambda v: {"neutral": "Neutral", "home_a": f"Local: A", "home_b": f"Local: B"}[v],
    )
with col4:
    competition = st.text_input("Competición (opcional)", key="competition")

if st.button("🚀 Calcular", use_container_width=True):
    if not name_a or not name_b:
        st.error("Por favor, selecciona ambos equipos.")
    else:
        with st.spinner('Buscando datos, contexto del partido y simulando...'):
            try:
                res = predictor.predecir(name_a, name_b, venue=venue, competition=competition)

                st.markdown(
                    f"<h2 style='text-align: center;'>"
                    f"{FLAGS.get(name_a, '⚽')} {name_a} vs {FLAGS.get(name_b, '⚽')} {name_b}"
                    f"</h2>",
                    unsafe_allow_html=True,
                )

                ctx = res.get("context", {})
                if ctx.get("notes"):
                    st.info(f"📝 {ctx['notes']}")
                st.caption(
                    f"Etapa: {ctx.get('stage', '-')}  |  "
                    f"Confianza del contexto: {ctx.get('confidence', '-')}"
                )

                # ── 1X2 ──────────────────────────────────────
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Victoria {name_a}", f"{res['victoria_a']}%")
                c2.metric("Empate", f"{res['empate']}%")
                c3.metric(f"Victoria {name_b}", f"{res['victoria_b']}%")

                st.caption(f"λ {name_a}: {res['lambda_a']}  |  λ {name_b}: {res['lambda_b']}")

                # ── Marcadores más probables ──────────────────
                st.subheader("Marcadores más probables")
                df_marcadores = pd.DataFrame(res['top_marcadores'], columns=["Marcador", "Probabilidad (%)"])
                st.table(df_marcadores.set_index("Marcador"))

                # ── Over/Under y BTTS ──────────────────────────
                col_ou, col_btts = st.columns(2)
                with col_ou:
                    st.subheader("Over / Under")
                    ou = res["ou"]
                    df_ou = pd.DataFrame(
                        [{"Línea": l[0] + "." + l[1], "Over %": ou[f"over_{l}"], "Under %": ou[f"under_{l}"]}
                         for l in ["05", "15", "25", "35"]]
                    )
                    st.table(df_ou.set_index("Línea"))
                with col_btts:
                    st.subheader("Ambos marcan (BTTS)")
                    st.metric("Sí", f"{res['btts_si']}%")
                    st.metric("No", f"{res['btts_no']}%")

                # ── Auditoría ───────────────────────────────────
                with st.expander("🧠 Detalle del análisis"):
                    st.write("Contexto detectado automáticamente por la IA:")
                    st.json(res.get("context_raw", {}))

                    st.write("Fuerza ofensiva/defensiva calculada:")
                    c_a, c_b = st.columns(2)
                    with c_a:
                        st.write(f"### {name_a}")
                        sa = res["strength_a"]
                        st.write(f"λ ataque: {sa['lambda_ataque']}  |  λ defensa: {sa['lambda_defensa']}")
                        st.write(f"Partidos usados: {sa['partidos_usados']}")
                        if "desglose" in sa:
                            st.dataframe(pd.DataFrame(sa["desglose"]))
                    with c_b:
                        st.write(f"### {name_b}")
                        sb = res["strength_b"]
                        st.write(f"λ ataque: {sb['lambda_ataque']}  |  λ defensa: {sb['lambda_defensa']}")
                        st.write(f"Partidos usados: {sb['partidos_usados']}")
                        if "desglose" in sb:
                            st.dataframe(pd.DataFrame(sb["desglose"]))

            except Exception as e:
                st.error(f"Error: {e}")
