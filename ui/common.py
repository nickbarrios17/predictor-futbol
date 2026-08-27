# ui/common.py
import streamlit as st


def apply_global_styles() -> None:
    st.markdown("""
    <style>
      .metric-card {
        background:#1e2a3a; border-radius:12px; padding:20px;
        text-align:center; border:1px solid #2e3f52;
      }
      .metric-label { color:#8899aa; font-size:13px; margin-bottom:4px; }
      .metric-value { color:#fff; font-size:32px; font-weight:bold; }
      .tag { display:inline-block; padding:3px 10px; border-radius:20px;
             font-size:12px; font-weight:bold; margin:2px; }
      .tag-green  { background:#1a4a2e; color:#2ecc71; }
      .tag-orange { background:#4a3000; color:#f39c12; }
      .tag-red    { background:#4a1a1a; color:#e74c3c; }
      .tag-blue   { background:#1a2a4a; color:#3498db; }
      .tag-gray   { background:#2a2a2a; color:#888; }
      .bar-container { background:#1e2a3a; border-radius:6px;
                       height:8px; width:100%; margin-top:4px; }
      .bar-fill { height:8px; border-radius:6px; }
    </style>
    """, unsafe_allow_html=True)


def pct_color(pct):
    if pct >= 50: return "#2ecc71"
    if pct >= 35: return "#f39c12"
    return "#e74c3c"

def pct_tag_class(pct):
    if pct >= 50: return "tag-green"
    if pct >= 35: return "tag-orange"
    return "tag-red"

def bar_html(pct, color):
    return (f'<div class="bar-container">'
            f'<div class="bar-fill" style="width:{pct}%;background:{color};"></div>'
            f'</div>')

def confidence_tag(conf):
    m = {"high":("tag-green","Alta ✅"),"medium":("tag-orange","Media ⚠️"),"low":("tag-red","Baja ❌")}
    css, label = m.get(conf, ("tag-gray", conf or "?"))
    return f'<span class="tag {css}">{label}</span>'

def lineup_tag(status):
    m = {"full":("tag-green","Titulares"),"rotation":("tag-orange","Rotación"),
         "reserves":("tag-red","Reservas"),"unknown":("tag-gray","Desconocido")}
    css, label = m.get(status, ("tag-gray", status or "?"))
    return f'<span class="tag {css}">{label}</span>'

def _pct_result(res):
    va, emp, vb = res.get("victoria_a",0), res.get("empate",0), res.get("victoria_b",0)
    ea, eb = res.get("equipo_a","A"), res.get("equipo_b","B")
    if va >= emp and va >= vb:   return f"Victoria {ea} ({va}%)"
    if vb >= va  and vb >= emp:  return f"Victoria {eb} ({vb}%)"
    return f"Empate ({emp}%)"


def init_session_state() -> None:
    for key in ["candidatos_a","candidatos_b","resultado",
                "dup_check","pending_save","show_replace"]:
        if key not in st.session_state:
            st.session_state[key] = None
