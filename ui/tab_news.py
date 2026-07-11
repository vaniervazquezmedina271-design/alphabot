"""
Pestaña de Noticias en vivo — scrapea las fuentes y muestra lo que extrajo el agente.
Para que el usuario VEA qué datos reales se usan antes de analizar.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.report import fetch_all_sources, deduplicate
from src.sources.base import NewsItem


def render():
    st.header("📰 Noticias en vivo")

    st.markdown("Scrapea las fuentes configuradas y muestra las noticias **tal cual se extrajeron** "
                "(antes de análisis con LLM). Así ves qué datos reales usa el agente.")

    if st.button("🔍 Scrapear ahora", type="primary", key="fetch_now"):
        with st.spinner("Scrapeando fuentes..."):
            items = fetch_all_sources()
            items = deduplicate(items)
            st.session_state["live_news"] = items

    news = st.session_state.get("live_news", [])

    if not news:
        st.info("Pulsa 'Scrapear ahora' para ver las noticias extraídas de las fuentes.")
        return

    st.success(f"**{len(news)} noticias extraídas** de las fuentes configuradas.")

    # Filtros rápidos
    col1, col2 = st.columns(2)
    with col1:
        source_filter = st.selectbox(
            "Filtrar por fuente:",
            ["Todas"] + sorted(set(n.source for n in news)),
            key="news_src_filter",
        )
    with col2:
        stars_filter = st.selectbox(
            "Filtrar por estrellas:",
            ["Todas", "⭐⭐⭐ (3)", "⭐⭐ (2)", "⭐ (1)", "Sin estrellas"],
            key="news_star_filter",
        )

    # Aplicar filtros
    filtered = news
    if source_filter != "Todas":
        filtered = [n for n in filtered if source_filter in n.source]
    if stars_filter == "⭐⭐⭐ (3)":
        filtered = [n for n in filtered if n.stars == 3]
    elif stars_filter == "⭐⭐ (2)":
        filtered = [n for n in filtered if n.stars == 2]
    elif stars_filter == "⭐ (1)":
        filtered = [n for n in filtered if n.stars == 1]
    elif stars_filter == "Sin estrellas":
        filtered = [n for n in filtered if n.stars == 0]

    # Tabla
    data = []
    for n in filtered:
        star_str = "⭐" * n.stars if n.stars else "—"
        data.append({
            "⭐": star_str,
            "Hora": n.time or "—",
            "País": n.country or "—",
            "Título": n.title[:80] + ("..." if len(n.title) > 80 else ""),
            "Fuente": n.source,
            "Forecast": n.forecast or "—",
            "Previo": n.previous or "—",
            "Actual": n.actual or "—",
            "URL": f"[Ver]({n.url})" if n.url else "—",
        })

    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.warning("No hay noticias con estos filtros.")
