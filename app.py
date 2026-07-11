#!/usr/bin/env python3
"""
app.py — Dashboard Streamlit del Agente de Búsqueda Financiera.

Uso:
  streamlit run app.py

Se abre en http://localhost:8501

Pestañas:
  1. 🧠 Proveedores y Modelo — buscador + API key + elegir modelo
  2. ⚙️ Configuración — fuentes, estrellas, horario, ajustes del modelo
  3. 📰 Noticias en vivo — scrapeo real de las fuentes (ver antes de analizar)
  4. 📊 Reporte — generar reporte, enviar a Telegram, historial
  5. 💬 Chat — consultas ad-hoc con el agente
"""
import streamlit as st

from ui.tab_providers import render as render_providers
from ui.tab_config import render as render_config
from ui.tab_news import render as render_news
from ui.tab_report import render as render_report
from ui.tab_chat import render as render_chat

# --- Configuración de la página ---
st.set_page_config(
    page_title="📊 Market Daily — Agente Financiero",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
with st.sidebar:
    st.markdown("# 📊 Market Daily")
    st.caption("Agente de Búsqueda Financiera")
    st.divider()
    st.markdown(
        "### Pestañas\n"
        "🧠 **Proveedores** — Elige modelo y API key\n"
        "⚙️ **Configuración** — Fuentes y ajustes\n"
        "📰 **Noticias** — Scrapeo en vivo\n"
        "📊 **Reporte** — Generar y enviar\n"
        "💬 **Chat** — Consultas ad-hoc\n"
    )
    st.divider()

    # Estado rápido
    try:
        from src.config import load_config, get_env
        cfg = load_config()
        active = cfg.get("active", {})
        st.markdown(f"**Modelo:** `{active.get('model', '❌')}`")
        st.markdown(f"**Proveedor:** {active.get('provider', '❌')}")

        tg_token = get_env("TELEGRAM_BOT_TOKEN")
        tg_chat = get_env("TELEGRAM_CHAT_ID")
        tg_status = "✅" if tg_token and tg_chat else "❌"
        st.markdown(f"**Telegram:** {tg_status}")
    except Exception:
        st.markdown("_Cargando configuración..._")

# --- Pestañas principales ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🧠 Proveedores",
    "⚙️ Configuración",
    "📰 Noticias en vivo",
    "📊 Reporte",
    "💬 Chat",
])

with tab1:
    render_providers()

with tab2:
    render_config()

with tab3:
    render_news()

with tab4:
    render_report()

with tab5:
    render_chat()
