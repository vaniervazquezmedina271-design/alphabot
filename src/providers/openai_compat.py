"""
Proveedor OpenAI-compatible.
Cubre: OpenRouter, OpenAI, Groq, Together, DeepSeek, Mistral, Fireworks,
       Cerebras, Ollama, LM Studio... (todos los que hablan el protocolo OpenAI).
"""
from __future__ import annotations

from .base import LLMProvider


class OpenAICompatProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, model: str = ""):
        super().__init__(api_key, base_url, model)
        # Para Ollama/LM Studio locales, una key dummy funciona.
        if not self.api_key:
            self.api_key = "ollama" if (self.base_url and "localhost" in self.base_url) else ""

    def _client(self):
        from openai import OpenAI
        return OpenAI(api_key=self.api_key or "no-key", base_url=self.base_url or None)

    def _supports_reasoning(self) -> bool:
        """
        Solo algunos proveedores OpenAI-compatibles aceptan la propiedad
        `reasoning` en el cuerpo de la petición. Cerebras y Groq devuelven
        error 400 ("property 'reasoning' is unsupported") si se les envía.
        Detectamos por base_url: OpenRouter y OpenAI nativo la soportan;
        Cerebras/Groq (y demás) NO, así que ahí se omite el parámetro.
        """
        url = (self.base_url or "").lower()
        # Proveedores que NO soportan reasoning -> omitir el parámetro.
        if "cerebras" in url or "groq" in url:
            return False
        # Proveedores que SÍ lo soportan.
        if "openrouter" in url or "api.openai.com" in url:
            return True
        # Por defecto, ser conservador y no enviarlo (evita 400 en proveedores
        # desconocidos que tampoco lo soporten).
        return False

    def chat(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500,
             reasoning: bool = False) -> str:
        client = self._client()
        kwargs = dict(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        # OpenRouter soporta "reasoning" en extra_body para activar <think>.
        # Cerebras/Groq no lo soportan (error 400), así que se omite ahí.
        if reasoning and self._supports_reasoning():
            kwargs["extra_body"] = {"reasoning": {"effort": "high"}}

        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    def list_models(self) -> list:
        try:
            client = self._client()
            resp = client.models.list()
            out = []
            for m in resp.data:
                mid = m.id if hasattr(m, "id") else getattr(m, "id", str(m))
                # OpenRouter marca los gratis con ":free"
                free = ":free" in str(mid).lower() or "free" in str(mid).lower()
                out.append({
                    "id": mid,
                    "name": getattr(m, "name", None) or str(mid),
                    "free": free,
                })
            return out
        except Exception as e:
            return [{"id": "", "name": f"Error: {e}", "free": False}]

    def health_check(self) -> bool:
        if not self.base_url and not self.api_key:
            # OpenAI nativo requiere key
            return False
        try:
            self.list_models()
            return True
        except Exception:
            return False
