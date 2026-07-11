"""
Clase base e interfaz común para todos los proveedores LLM.

Cada proveedor implementa:
  - chat(messages, **kwargs) -> str
  - list_models() -> list[dict]   (id, name, free)
  - health_check() -> bool
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Interfaz común que implementan todos los proveedores."""

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

    @abstractmethod
    def chat(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500,
             reasoning: bool = False) -> str:
        """
        Envía una lista de mensajes y devuelve el texto de respuesta.
        messages: [{"role": "system"|"user"|"assistant", "content": "..."}]
        Si reasoning=True y el modelo lo soporta, se activa el modo <think>.
        """
        ...

    @abstractmethod
    def list_models(self) -> list:
        """
        Devuelve los modelos disponibles del proveedor.
        Lista de dicts: {"id": str, "name": str, "free": bool}
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """True si la conexión y la API key funcionan."""
        ...

    # ---- utilidad compartida ----
    def _has_key(self) -> bool:
        return bool(self.api_key and self.api_key.strip())


def get_provider(provider_name: str, config: dict) -> Optional[LLMProvider]:
    """
    Fábrica: devuelve la instancia del proveedor correcto según el nombre
    y la configuración (que incluye base_url y api_key_env).

    config debe contener al menos: api_type, base_url, api_key_env
    Lee la API key desde el entorno (os.environ).
    """
    # Asegurar que el .env está cargado antes de leer las keys
    from .. import config as cfg_module
    cfg_module.load_env()

    api_type = (config.get("api_type") or "openai").lower()
    base_url = config.get("base_url", "")
    # El catálogo usa "key_env" (compat con ambos nombres)
    key_env = config.get("key_env") or config.get("api_key_env") or ""
    api_key = os.environ.get(key_env, "") if key_env else ""

    if api_type == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(api_key=api_key, base_url=base_url)
    if api_type == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(api_key=api_key, base_url=base_url)
    # por defecto: OpenAI-compatible
    from .openai_compat import OpenAICompatProvider
    return OpenAICompatProvider(api_key=api_key, base_url=base_url)
