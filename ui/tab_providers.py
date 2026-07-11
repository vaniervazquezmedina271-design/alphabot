"""
Pestaña de Proveedores — buscador con lupa + pegar API key + elegir modelo.

Flujo del usuario:
1. Busca el proveedor en el buscador
2. Hace clic en uno → ve el campo de API key
3. Pega su key → Guardar
4. "Ver modelos" → dropdown con modelos del proveedor
5. "Activar modelo" → lo guarda como activo en config.yaml
"""
from __future__ import annotations

import streamlit as st

from src.providers.catalog import CATALOG, RECOMMENDED_MODELS, search_catalog
from src.providers.base import get_provider
from src.config import load_config, save_config, set_env_var, get_env


def render():
    st.header("🧠 Proveedores y Modelo")

    # --- Configuración activa actual ---
    cfg = load_config()
    active = cfg.get("active", {})
    st.info(
        f"**Modelo activo:** `{active.get('model', 'no configurado')}` "
        f"vía **{active.get('provider', '?')}** "
        f"| Temp: {active.get('temperature', 0.3)} "
        f"| Razonamiento: {'✅' if active.get('reasoning') else '❌'}"
    )

    # --- Sección 1: Buscador de proveedores ---
    st.subheader("🔍 Buscar proveedor")
    search = st.text_input(
        "Escribe el nombre del proveedor...",
        placeholder="Ej: OpenRouter, Anthropic, Groq, DeepSeek, Ollama...",
        key="provider_search",
    )

    results = search_catalog(search)

    if not results:
        st.warning("No se encontraron proveedores.")
        return

    # Mostrar como tarjetas clickeables
    cols = st.columns(min(len(results), 3))
    for i, prov in enumerate(results):
        with cols[i % len(cols)]:
            name = prov["name"]
            key_env = prov["key_env"]
            has_key = bool(get_env(key_env)) if key_env else True  # Ollama no necesita key

            border_color = "🟢" if has_key else "🟡"
            card = st.container(border=True)
            with card:
                st.markdown(f"### {prov['logo']} {name}")
                st.caption(prov.get("note", ""))
                status = "✅ Key guardada" if has_key else ("N/A (local)" if not key_env else "⚠️ Sin API key")
                st.markdown(f"**Estado:** {status}")

                if st.button("Configurar", key=f"cfg_{name}"):
                    st.session_state["selected_provider"] = prov

    # --- Sección 2: Configurar proveedor seleccionado ---
    selected = st.session_state.get("selected_provider")
    if selected:
        st.divider()
        st.subheader(f"⚙️ Configurar {selected['logo']} {selected['name']}")

        key_env = selected.get("key_env", "")
        if key_env:
            current_key = get_env(key_env)
            masked = (current_key[:6] + "..." + current_key[-4:]) if len(current_key) > 10 else (current_key or "(vacía)")
            st.caption(f"Variable de entorno: `{key_env}` · Valor actual: `{masked}`")

            new_key = st.text_input(
                "Pega tu API key:",
                type="password",
                value="",
                placeholder="sk-... o tu API key aquí",
                key="api_key_input",
            )

            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Guardar API Key", type="primary"):
                    if new_key.strip():
                        set_env_var(key_env, new_key.strip())
                        st.success("✅ API key guardada en .env")
                        st.rerun()
                    else:
                        st.error("Escribe una API key válida.")
            with col2:
                if st.button("🔗 Probar conexión"):
                    provider = get_provider(selected["name"], selected)
                    if provider:
                        ok = provider.health_check()
                        if ok:
                            st.success("✅ Conexión exitosa.")
                        else:
                            st.error("❌ No se pudo conectar. Revisa la API key.")
                    else:
                        st.error("❌ Error al crear el proveedor.")
        else:
            st.success("Este proveedor no necesita API key (es local).")

        # --- Sección 3: Elegir modelo ---
        st.divider()
        st.subheader("📋 Elegir modelo")

        provider = get_provider(selected["name"], selected)
        if provider:
            with st.spinner("Cargando modelos..."):
                models = provider.list_models()

            # Models recomendados primero
            recommended_for_provider = [
                m for m in RECOMMENDED_MODELS
                if m["provider"] == selected["name"]
            ]

            if recommended_for_provider:
                st.markdown("**⚡ Recomendados:**")
                for rec in recommended_for_provider:
                    label = f"{rec['logo']} {rec['label']} {'🆓' if rec.get('free') else ''}"
                    if st.button(label, key=f"rec_{rec['model']}"):
                        _activate_model(selected["name"], rec["model"])
                st.divider()

            # Todos los modelos (filtrar gratuitos)
            show_free_only = st.checkbox("🆓 Mostrar solo gratuitos", value=False, key="free_filter")
            available = [m for m in models if m.get("id")] if models else []

            if show_free_only:
                available = [m for m in available if m.get("free")]

            if available:
                model_ids = [m["id"] for m in available]
                selected_model = st.selectbox(
                    "Modelos disponibles:",
                    model_ids,
                    key="model_select",
                    format_func=lambda x: f"{x} {'🆓' if next((m['free'] for m in available if m['id'] == x), False) else ''}",
                )

                if st.button("✅ Activar este modelo", type="primary", key="activate_model"):
                    _activate_model(selected["name"], selected_model)
            else:
                st.info("No se encontraron modelos. Verifica la conexión.")
        else:
            st.warning("Primero guarda una API key válida.")


def _activate_model(provider_name: str, model_id: str):
    """Activa un modelo y guarda en config.yaml."""
    cfg = load_config()
    cfg["active"]["provider"] = provider_name
    cfg["active"]["model"] = model_id
    save_config(cfg)
    st.success(f"✅ Modelo activado: `{model_id}` vía `{provider_name}`")
    st.rerun()
