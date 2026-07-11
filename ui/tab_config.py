"""
Pestaña de Configuración — fuentes, estrellas mínimas, horario, temperatura, razonamiento.
"""
from __future__ import annotations

import streamlit as st

from src.config import load_config, save_config


def render():
    st.header("⚙️ Configuración")

    cfg = load_config()

    # --- Fuentes ---
    st.subheader("📰 Fuentes de noticias")
    sources = cfg.get("sources", {})
    source_names = {
        "forex_factory": "🟢 Forex Factory (calendario con estrellas)",
        "investing": "🔵 Investing.com (calendario económico)",
        "yahoo_finance": "🟣 Yahoo Finance (noticias RSS)",
        "finviz": "🟠 Finviz (noticias mercado)",
        "bloomberg_rss": "🟡 Bloomberg (RSS)",
    }

    new_sources = {}
    for key, label in source_names.items():
        enabled = sources.get(key, {}).get("enabled", True)
        new_sources[key] = {"enabled": st.checkbox(label, value=enabled, key=f"src_{key}")}

    # --- Filtros ---
    st.subheader("🎯 Filtros")
    filt = cfg.get("filter", {})

    col1, col2 = st.columns(2)
    with col1:
        min_stars = st.slider(
            "⭐ Estrellas mínimas (reporte diario)",
            min_value=1, max_value=3, value=filt.get("min_stars", 2),
            key="min_stars",
        )
    with col2:
        breaking_min = st.slider(
            "📊 Score mínimo alertas última hora",
            min_value=0, max_value=100, value=filt.get("breaking_min_score", 70),
            key="breaking_min",
        )

    # --- Horario ---
    st.subheader("🕐 Horario del reporte")
    sched = cfg.get("schedule", {})

    col1, col2 = st.columns(2)
    with col1:
        report_time = st.text_input(
            "Hora del reporte automático",
            value=sched.get("report_time", "08:00"),
            key="report_time",
        )
    with col2:
        timezone = st.text_input(
            "Zona horaria",
            value=sched.get("timezone", "America/New_York"),
            key="timezone",
        )

    # --- Modelo (ajustes finos) ---
    st.subheader("🧠 Ajustes del modelo")
    active = cfg.get("active", {})

    col1, col2, col3 = st.columns(3)
    with col1:
        temperature = st.slider("Temperature", 0.0, 1.0,
                                value=active.get("temperature", 0.3), step=0.1, key="temp")
    with col2:
        max_tokens = st.slider("Max tokens", 500, 4000,
                               value=active.get("max_tokens", 1500), step=100, key="mtokens")
    with col3:
        reasoning = st.toggle("Razonamiento 彼岸", value=active.get("reasoning", True), key="reason")

    # --- Telegram ---
    st.subheader("📲 Telegram")
    from src.config import get_env
    token = st.text_input("Bot Token", value=get_env("TELEGRAM_BOT_TOKEN"), type="password", key="tg_token")
    chat_id = st.text_input("Chat ID", value=get_env("TELEGRAM_CHAT_ID"), key="tg_chatid")

    if st.button("💾 Guardar todo", type="primary", key="save_config"):
        cfg["sources"] = new_sources
        cfg["filter"]["min_stars"] = int(min_stars)
        cfg["filter"]["breaking_min_score"] = int(breaking_min)
        cfg["schedule"]["report_time"] = report_time
        cfg["schedule"]["timezone"] = timezone
        cfg["active"]["temperature"] = float(temperature)
        cfg["active"]["max_tokens"] = int(max_tokens)
        cfg["active"]["reasoning"] = reasoning

        # Guardar Telegram keys si cambiaron
        if token:
            from src.config import set_env_var
            set_env_var("TELEGRAM_BOT_TOKEN", token)
        if chat_id:
            from src.config import set_env_var
            set_env_var("TELEGRAM_CHAT_ID", chat_id)

        save_config(cfg)
        st.success("✅ Configuración guardada.")
