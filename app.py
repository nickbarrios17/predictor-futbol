import streamlit as st
import pandas as pd
import predictor
from sources.api_source import search_team
from sources.web_source import get_match_news  # Asegúrate de importar esto

st.set_page_config(page_title="Predicciones Fútbol", page_icon="⚽", layout="centered")

FLAGS = {
    "Argentina": "🇦🇷", "Brazil": "🇧🇷", "Germany": "🇩🇪", "France": "🇫🇷",
    "Spain": "🇪🇸", "Mexico": "🇲🇽", "South Africa": "🇿🇦",
}

def init_app_state():
    if 'candidatos_a' not in st.session_state: st.session_state['candidatos_a'] = None
    if 'candidatos_b' not in st.session_state: st.session_state['candidatos_b'] = None

init_app_state()

st.title("⚽ Predictor IA con Transparencia")

# --- UI Selección de Equipos ---
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

col3, col4 = st.columns(2)
with col3:
    venue = st.selectbox("Sede", ["neutral", "home_a", "home_b"])
with col4:
    competition = st.text_input("Competición (opcional)", key="competition")

# --- Lógica de Cálculo ---
if st.button("🚀 Calcular", use_container_width=True):
    if not name_a or not name_b:
        st.error("Por favor, selecciona ambos equipos.")
    else:
        with st.spinner('Obteniendo noticias y simulando resultados...'):
            try:
                # 1. Obtención de contexto real (La mejora clave)
                query = f"{name_a} vs {name_b} match preview news"
                noticias = get_match_news(query)
                
                # 2. Invocamos al predictor pasando el texto de las noticias
                # Asegúrate de que tu predictor.predecir acepte un argumento 'noticias'
                res = predictor.predecir(name_a, name_b, venue=venue, competition=competition, noticias=noticias)

                # --- Visualización ---
                st.markdown(f"<h2 style='text-align: center;'>{name_a} vs {name_b}</h2>", unsafe_allow_html=True)

                ctx = res.get("context", {})
                if ctx.get("notes"): st.info(f"📝 {ctx['notes']}")
                
                # Métricas 1X2
                c1, c2, c3 = st.columns(3)
                c1.metric(f"Victoria {name_a}", f"{res['victoria_a']}%")
                c2.metric("Empate", f"{res['empate']}%")
                c3.metric(f"Victoria {name_b}", f"{res['victoria_b']}%")

                # Auditoría de datos IA
                with st.expander("🧠 Detalle del análisis IA"):
                    st.write("Contexto detectado por la IA:")
                    st.json(res.get("context_raw", {}))
                    st.write(f"Noticias procesadas: {len(noticias) if noticias else 0} caracteres.")

            except Exception as e:
                st.error(f"Error en la ejecución: {e}")
def get_match_news(query: str, n_urls: int = 3, max_chars_per_page: int = 2000) -> str:
    """
    Función maestra: Busca, descarga y concatena noticias relevantes.
    Devuelve un texto único listo para ser inyectado en el prompt de la IA.
    """
    # 1. Buscar URLs
    urls = search_web(query, n=n_urls)
    if not urls:
        return "No se encontraron noticias relevantes."
    
    # 2. Descargar y procesar todas las URLs
    texto_total = fetch_multiple(urls, max_chars=max_chars_per_page)
    
    return texto_total