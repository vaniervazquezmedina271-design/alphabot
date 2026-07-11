"""Proveedor Anthropic (Claude)."""
from __future__ import annotations

from .base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        super().__init__(api_key, base_url, model)

    def _client(self):
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def chat(self, messages: list, temperature: float = 0.3, max_tokens: int = 1500,
             reasoning: bool = False) -> str:
        client = self._client()
        # Anthropic separa system del resto de mensajes
        sys_msg = ""
        conv = []
        for m in messages:
            if m["role"] == "system":
                sys_msg += m["content"] + "\n"
            else:
                conv.append({"role": m["role"], "content": m["content"]})

        # Claude exige un mensaje "user" primero
        if not conv or conv[0]["role"] != "user":
            conv.insert(0, {"role": "user", "content": "(continúa)"})

        resp = client.messages.create(
            model=self.model or "claude-3-5-sonnet-20241022",
            system=sys_msg.strip() or None,
            messages=conv,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.content[0].text if resp.content else ""

    def list_models(self) -> list:
        try:
            client = self._client()
            resp = client.models.list()
            return [
                {"id": m.id, "name": getattr(m, "display_name", m.id), "free": False}
                for m in resp.data
            ]
        except Exception:
            # Lista por defecto conocida
            return [
                {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "free": False},
                {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "free": False},
                {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "free": False},
            ]

    def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            self.list_models()
            return True
        except Exception:
            return False
