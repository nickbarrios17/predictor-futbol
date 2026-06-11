import streamlit as st
import pandas as pd
import predictor
from sources.api_source import search_team

st.set_page_config(page_title="Predicciones Fútbol", page_icon="⚽", layout="centered")

FLAGS = {"Argentina": "🇦🇷", "Brazil": "🇧🇷", "Germany": "🇩🇪", "France": "🇫🇷", "Spain": "🇪🇸", "Mexico": "🇲🇽", "South Africa": "🇿🇦"}

def init_app_state():
    if 'candidatos_a' not in st.session_state: st.session_state['candidatos_a'] = None
    if 'candidatos_b' not in st.session_state: st.session_state['candidatos_b'] = None

init_app_state()

st.title("⚽ Predictor IA con Transparencia")

col1, col2 = st.columns(2)
with col1:
    busqueda_a = st.text_input("Buscar Equipo A", key="search_a")
    if st.button("🔍 Buscar A"): st.session_state['candidatos_a'] = search_team(busqueda_a)
    candidatos_a = st.session_state.get('candidatos_a')
    seleccion_a = st.selectbox("Seleccionar A", candidatos_a or [], format_func=lambda x: x.get('name', 'N/A')) if candidatos_a else None
    name_a = seleccion_a.get('name') if seleccion_a else busqueda_a

with col2:
    busqueda_b = st.text_input("Buscar Equipo B", key="search_b")
    if st.button("🔍 Buscar B"): st.session_state['candidatos_b'] = search_team(busqueda_b)
    candidatos_b = st.session_state.get('candidatos_b')
    seleccion_b = st.selectbox("Seleccionar B", candidatos_b or [], format_func=lambda x: x.get('name', 'N/A')) if candidatos_b else None
    name_b = seleccion_b.get('name') if seleccion_b else busqueda_b

if st.button("🚀 Calcular", use_container_width=True):
    if not name_a or not name_b:
        st.error("Por favor, selecciona ambos equipos.")
    else:
        with st.spinner('Analizando y auditando...'):
            try:
                res = predictor.predecir(name_a, name_b, "neutral", "FIFA", "seleccion")
                
                st.markdown(f"<h2 style='text-align: center;'>{FLAGS.get(name_a, '⚽')} {name_a} vs {FLAGS.get(name_b, '⚽')} {name_b}</h2>", unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Victoria A", f"{res['victoria_a']}%"); c2.metric("Empate", f"{res['empate']}%"); c3.metric("Victoria B", f"{res['victoria_b']}%")
                
                st.table(pd.DataFrame(res['marcadores_probables']).set_index("Marcador"))

                # Auditoría
                with st.expander("🧠 ¿Cómo pensó la IA? (Auditoría de Datos)"):
                    st.write("Se han descartado partidos de clubes y ponderado los partidos según relevancia y fecha.")
                    c_a, c_b = st.columns(2)
                    c_a.write(f"### {name_a}"); c_a.dataframe(pd.DataFrame(res['audit_a']))
                    c_b.write(f"### {name_b}"); c_b.dataframe(pd.DataFrame(res['audit_b']))
            except Exception as e:
                st.error(f"Error: {e}")