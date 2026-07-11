"""
Forex Factory — calendario económico.
Fuente muy estable con estrellas (impacto) claras.
Endpoint JSON: https://nfs.faireconomy.media ff_calendar_thisweek.json
"""
from __future__ import annotations

from typing import Optional

from .base import BaseSource, NewsItem

# Forex Factory publica un JSON gratuito del calendario semanal.
FF_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

# Mapeo de impacto -> estrellas
IMPACT_TO_STARS = {"high": 3, "medium": 2, "low": 1, "holiday": 0}


class ForexFactorySource(BaseSource):
    name = "forex_factory"
    display_name = "Forex Factory"

    def _get(self, url: str, **kwargs) -> Optional[str]:
        # sobrescribimos para pedir JSON
        import httpx, time
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        for attempt in range(3):
            try:
                with httpx.Client(timeout=20, follow_redirects=True) as client:
                    r = client.get(url, headers=headers, **kwargs)
                    if r.status_code == 200:
                        return r.text
            except Exception:
                time.sleep(1.5 * (attempt + 1))
        return None

    def fetch(self) -> list[NewsItem]:
        raw = self._get(FF_JSON_URL)
        if not raw:
            return []
        import json
        from datetime import datetime
        try:
            data = json.loads(raw)
        except Exception:
            return []

        # Forex Factory devuelve toda la SEMANA — filtrar solo eventos de HOY
        today = datetime.now().date()

        items: list[NewsItem] = []
        for ev in data:
            date_str = ev.get("date", "")
            # Filtrar por fecha (comparar solo YYYY-MM-DD)
            try:
                event_date = datetime.fromisoformat(date_str).date()
            except Exception:
                continue  # sin fecha válida → descartar
            if event_date != today:
                continue  # no es hoy → descartar

            impact = (ev.get("impact") or "").lower()
            stars = IMPACT_TO_STARS.get(impact, 0)
            country = ev.get("country", "")
            # emoji de bandera aproximado desde el código de país
            flag = _flag_emoji(country)
            items.append(NewsItem(
                title=ev.get("title", "").strip(),
                url=ev.get("url") or "https://www.forexfactory.com/calendar",
                source="Forex Factory",
                time=_extract_time(ev.get("date", "")),
                stars=stars,
                country=flag,
                currency=country,
                forecast=ev.get("forecast", "") or "",
                previous=ev.get("previous", "") or "",
                actual=ev.get("actual", "") or "",
                raw=ev,
            ))
        return items


def _extract_time(date_str: str) -> str:
    """'2026-07-09T09:30:00-04:00' -> '09:30'."""
    if not date_str or "T" not in date_str:
        return ""
    try:
        return date_str.split("T")[1][:5]
    except Exception:
        return ""


# Mapeo moneda -> código de país ISO de 2 letras (para bandera)
CURRENCY_TO_COUNTRY = {
    "USD": "US", "EUR": "EU", "GBP": "GB", "JPY": "JP", "CHF": "CH",
    "AUD": "AU", "NZD": "NZ", "CAD": "CA", "CNY": "CN", "KRW": "KR",
    "SEK": "SE", "NOK": "NO", "DKK": "DK", "SGD": "SG", "HKD": "HK",
    "INR": "IN", "BRL": "BR", "MXN": "MX", "ZAR": "ZA", "TRY": "TR",
    "RUB": "RU", "PLN": "PL", "CZK": "CZ", "HUF": "HU", "THB": "TH",
    "IDR": "ID", "MYR": "MY", "PHP": "PH", "TWD": "TW", "ILS": "IL",
    "AED": "AE", "SAR": "SA", "CLP": "CL", "COP": "CO", "PEN": "PE",
    "ALL": "AL",
}


def _flag_emoji(code: str) -> str:
    """
    Convierte un código de país ISO de 2 letras o una moneda de 3 letras
    (USD, EUR, GBP...) en emoji de bandera.
    """
    if not code:
        return "🌍"
    code = code.upper().strip()

    # Si es moneda de 3 letras, convertir a país
    if len(code) == 3:
        code = CURRENCY_TO_COUNTRY.get(code, "")

    if len(code) != 2:
        return "🌍"

    try:
        return chr(0x1F1E6 + (ord(code[0]) - ord("A"))) + chr(0x1F1E6 + (ord(code[1]) - ord("A")))
    except Exception:
        return "🌍"
