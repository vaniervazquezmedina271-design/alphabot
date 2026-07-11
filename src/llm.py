"""
Fábrica de LLM: crea el proveedor activo según config.yaml.
Incluye failover automático: si el proveedor activo falla (429, rate limit,
error de conexión), prueba el siguiente proveedor de la cadena.
"""
from __future__ import annotations

from typing import Optional

from . import config
from .providers import get_provider, get_catalog_entry
from .providers.base import LLMProvider


def _build_provider(provider_name: str, model: str) -> Optional[LLMProvider]:
    """Construye un proveedor si tiene API key configurada. Devuelve None si no."""
    entry = get_catalog_entry(provider_name)
    if entry is None:
        return None

    # Verificar que la API key exista (excepto proveedores locales como Ollama)
    key_env = entry.get("key_env", "")
    if key_env and not config.get_env(key_env):
        return None

    provider = get_provider(provider_name, entry)
    if provider is None:
        return None
    provider.model = model
    return provider


def get_active_provider() -> Optional[LLMProvider]:
    """
    Construye la instancia del proveedor ACTIVO según config.yaml.
    Devuelve None si falta la API key (el dashboard avisará).
    """
    cfg = config.load_config()
    active = cfg.get("active", {})
    provider_name = active.get("provider", "OpenRouter")
    model = active.get("model", "")

    return _build_provider(provider_name, model)


def get_failover_chain() -> list[LLMProvider]:
    """
    Construye la cadena completa de proveedores para failover:
    [activo, failover1, failover2, ...]

    Solo incluye proveedores con API key configurada.
    Si el failover está desactivado o no hay proveedores configurados,
    devuelve solo el activo.
    """
    cfg = config.load_config()
    active = cfg.get("active", {})
    active_name = active.get("provider", "OpenRouter")
    active_model = active.get("model", "")

    chain: list[LLMProvider] = []

    # Proveedor primario (activo)
    primary = _build_provider(active_name, active_model)
    if primary is not None:
        chain.append(primary)

    # Proveedores de failover
    failover_cfg = cfg.get("failover", {})
    if not failover_cfg.get("enabled", True):
        return chain

    for entry in failover_cfg.get("providers", []):
        name = entry.get("provider", "")
        model = entry.get("model", "")
        if not name:
            continue
        # No duplicar el primario en la cadena de failover
        if name.lower() == active_name.lower():
            continue
        provider = _build_provider(name, model)
        if provider is not None:
            chain.append(provider)

    return chain


def get_active_settings() -> dict:
    """Devuelve temperatura, max_tokens, reasoning del bloque active."""
    active = config.load_config().get("active", {})
    return {
        "temperature": active.get("temperature", 0.3),
        "max_tokens": active.get("max_tokens", 1500),
        "reasoning": active.get("reasoning", False),
        "provider": active.get("provider", ""),
        "model": active.get("model", ""),
    }


def chat(messages: list, **overrides) -> str:
    """
    Atajo: usa la cadena de proveedores para chatear.
    Prueba el proveedor activo primero; si falla (429, rate limit, etc.),
    prueba el siguiente proveedor de la cadena de failover.

    Permite sobreescribir temperatura/max_tokens/reasoning por llamada.
    """
    chain = get_failover_chain()
    if not chain:
        raise RuntimeError(
            "No hay proveedor configurado. Abre el dashboard y pega tu API key."
        )

    s = get_active_settings()
    settings = {
        "temperature": overrides.get("temperature", s["temperature"]),
        "max_tokens": overrides.get("max_tokens", s["max_tokens"]),
        "reasoning": overrides.get("reasoning", s["reasoning"]),
    }

    last_error: Exception | None = None
    for i, provider in enumerate(chain):
        label = f"{provider.model}" if provider.model else f"proveedor #{i+1}"
        try:
            return provider.chat(messages, **settings)
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Errores recuperables: rate limit, timeout, conexión, 429, 503
            is_recoverable = any(kw in err_str for kw in [
                "429", "rate limit", "rate_limit", "quota", "timeout",
                "timed out", "connection", "503", "service unavailable",
                "overloaded", "capacity",
            ])
            if is_recoverable and i < len(chain) - 1:
                print(f"  ⚠️ {label}: {str(e)[:120]}... → probando siguiente proveedor...")
                continue
            # Error no recuperable o último proveedor → relanzar
            if i < len(chain) - 1:
                print(f"  ⚠️ {label}: {str(e)[:120]}... → probando siguiente proveedor...")
                continue
            raise

    # No debería llegar aquí, pero por seguridad
    raise RuntimeError(f"Todos los proveedores fallaron. Último error: {last_error}")
