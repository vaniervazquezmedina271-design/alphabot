"""Proveedor Google Gemini."""
from __future__ import annotations

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        super().__init__(api_key, base_url, model)

    def _client(self):
        from google import genai
        return genai.Client(api_key=self.api_key)

    def chat(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500,
             reasoning: bool = False) -> str:
        client = self._client()
        # Gemini usa un solo prompt combinado
        sys_msg = ""
        parts = []
        for m in messages:
            if m["role"] == "system":
                sys_msg += m["content"] + "\n"
            else:
                prefix = "Usuario: " if m["role"] == "user" else "Asistente: "
                parts.append(f"{prefix}{m['content']}")
        prompt = (sys_msg + "\n" + "\n".join(parts)).strip()

        resp = client.models.generate_content(
            model=self.model or "gemini-2.0-flash",
            contents=prompt,
            config={"temperature": temperature, "max_output_tokens": max_tokens},
        )
        return getattr(resp, "text", "") or ""

    def list_models(self) -> list:
        try:
            client = self._client()
            resp = client.models.list()
            out = []
            for m in resp:
                mid = getattr(m, "name", str(m)).replace("models/", "")
                out.append({"id": mid, "name": getattr(m, "display_name", mid), "free": True})
            return out
        except Exception:
            return [
                {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "free": True},
                {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash Lite", "free": True},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "free": True},
            ]

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            self.list_models()
            return True
        except Exception:
            return False
