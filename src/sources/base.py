"""
Clase base de las fuentes de noticias y modelo de datos NewsItem.

NewsItem representa una noticia/evento crudo extraído de una página.
El analyzer (LLM) lo enriquece después con sentimiento, contexto, etc.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Optional

import httpx


# Headers realistas para evitar bloqueos básicos.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


@dataclass
class NewsItem:
    """Una noticia/evento crudo extraído de una fuente web."""
    title: str
    url: str
    source: str                       # nombre de la fuente ("Investing", "Yahoo", ...)
    time: Optional[str] = None        # hora publicada o programada (ej. "09:30")
    stars: int = 0                    # impacto 1-3 (estrellas). 0 si desconocido.
    country: str = ""                 # bandera/emoji o código ("🇺🇸")
    currency: str = ""                # "USD", "EUR"...
    forecast: str = ""                # valor esperado
    previous: str = ""                # valor anterior
    actual: str = ""                  # valor real (si ya salió)
    summary: str = ""                 # resumen breve del contenido si está disponible
    sources: list = field(default_factory=list)  # fuentes que traían esta misma noticia (agrupación)
    raw: dict = field(default_factory=dict)  # datos extra originales por si acaso

    def to_dict(self) -> dict:
        return asdict(self)


class BaseSource(ABC):
    """Interfaz común de todos los scrapers."""

    name: str = "base"
    display_name: str = "Base"

    @abstractmethod
    def fetch(self) -> list[NewsItem]:
        """Descarga y parsea las noticias. Devuelve lista de NewsItem."""
        ...

    # --- utilidades de red ---
    def _get(self, url: str, **kwargs) -> Optional[str]:
        """GET con headers realistas y reintentos suaves."""
        headers = {**DEFAULT_HEADERS, **kwargs.pop("headers", {})}
        for attempt in range(3):
            try:
                with httpx.Client(timeout=20, follow_redirects=True) as client:
                    r = client.get(url, headers=headers, **kwargs)
                    if r.status_code == 200:
                        return r.text
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        return None

    def _enabled(self) -> bool:
        """Comprueba en config.yaml si esta fuente está habilitada."""
        from .. import config
        cfg = config.load_config()
        src = cfg.get("sources", {}).get(self.name, {})
        return src.get("enabled", True)
