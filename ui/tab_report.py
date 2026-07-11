"""
Pestaña de Reporte — generar reporte, ver en pantalla, enviar a Telegram, ver historial.
"""
from __future__ import annotations

import os
from datetime import datetime

import streamlit as st

from src.report import generate_daily_report
from src.notifier import send_to_telegram, test_telegram_connection
from src.config import HISTORY_DIR


def render():
    st.header("📊 Reporte diario")

    # --- Generar reporte ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ Generar reporte ahora", type="primary", key="gen_report"):
            with st.spinner("Scrapeando fuentes + analizando con LLM..."):
                report, entries = generate_daily_report()
                st.session_state["last_report"] = report
                st.session_state["last_entries"] = entries
    with col2:
        if st.button("📲 Enviar a Telegram", key="send_tg"):
            report = st.session_state.get("last_report", "")
            if not report:
                st.warning("Primero genera un reporte.")
            else:
                ok = send_to_telegram(report)
                if ok:
                    st.success("✅ Reporte enviado a Telegram.")
                else:
                    st.error("❌ Error al enviar. Revisa .env")

    # --- Probar conexión Telegram ---
    with st.expander("🔧 Probar conexión con Telegram"):
        if st.button("Enviar mensaje de prueba", key="test_tg"):
            ok, msg = test_telegram_connection()
            if ok:
                st.success(msg)
            else:
                st.error(msg)

    # --- Mostrar reporte generado ---
    report = st.session_state.get("last_report", "")
    if report:
        st.divider()
        st.subheader("📋 Reporte generado")
        st.markdown(report)

        entries = st.session_state.get("last_entries", [])
        if entries:
            st.caption(f"📌 {len(entries)} eventos de alto impacto")
    else:
        st.info("Pulsa 'Generar reporte ahora' para crear el reporte del día.")

    # --- Historial ---
    st.divider()
    st.subheader("📁 Historial de reportes")

    if not HISTORY_DIR.exists():
        st.info("No hay reportes guardados aún.")
        return

    files = sorted(HISTORY_DIR.glob("report_*.txt"), reverse=True)
    if not files:
        st.info("No hay reportes guardados aún.")
        return

    for f in files[:10]:  # últimos 10
        fname = f.stem.replace("report_", "")
        with st.expander(f"📅 {fname}"):
            content = f.read_text(encoding="utf-8")
            st.markdown(content)
