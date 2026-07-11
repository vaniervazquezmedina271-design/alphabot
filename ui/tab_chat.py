"""
Pestaña de Chat — interfaz de lenguaje natural.
El usuario habla en español normal y el agente ejecuta acciones reales:
  - "dame el reporte de hoy"      → genera y muestra el reporte diario
  - "hay noticias importantes?"   → busca alertas de alto impacto
  - "envía el reporte a telegram" → genera + envía
  - "busca noticias de NVIDIA"    → análisis específico
  - "estado del agente"           → muestra configuración

NO usa comandos de código, solo conversación.
"""
from __future__ import annotations

import streamlit as st

from src.chat import process_message, _help_text


def render():
    st.header("💬 Habla con el agente")
    st.caption("Háblame normal, en español. Yo entiendo lo que necesitas y lo ejecuto.")

    # Sugerencias rápidas (chips clicables)
    st.markdown("**💡 Prueba decirme:**")
    cols = st.columns(4)
    suggestions = [
        "📊 Dame el reporte de hoy",
        "🚨 ¿Hay noticias importantes ahora?",
        "📲 Envía el reporte a Telegram",
        "🔍 Busca noticias de NVIDIA",
    ]
    for col, s in zip(cols, suggestions):
        if col.button(s, key=f"sugg_{s}"):
            st.session_state["_pending_input"] = s.replace("📊 ", "").replace("🚨 ", "").replace("📲 ", "").replace("🔍 ", "")

    st.divider()

    # Inicializar historial de chat
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = [
            {"role": "assistant", "content": (
                "🤖 **Market Daily** — Agente del mercado americano\n\n"
                "Háblame normal y yo me encargo. ¿Qué necesitas hoy?"
            )},
        ]

    # Mostrar historial
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Procesar input pendiente (de sugerencias)
    pending = st.session_state.pop("_pending_input", None)

    # Input de chat
    user_input = st.chat_input("Escribe lo que necesites...")

    # Si hay input pendiente de sugerencia, usarlo
    if pending and not user_input:
        user_input = pending

    if user_input:
        # Mostrar mensaje del usuario
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        # Procesar y responder
        with st.chat_message("assistant"):
            with st.spinner("Procesando..."):
                try:
                    response = process_message(user_input)
                    st.markdown(response)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": response}
                    )
                except Exception as e:
                    error = f"❌ Error: {e}"
                    st.error(error)
                    st.session_state["chat_history"].append(
                        {"role": "assistant", "content": error}
                    )

    # Botones inferiores
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Limpiar chat"):
            st.session_state["chat_history"] = []
            st.rerun()
    with col2:
        if st.button("❓ Ayuda"):
            st.session_state["chat_history"].append(
                {"role": "assistant", "content": _help_text()}
            )
            st.rerun()
