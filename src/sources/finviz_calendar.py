"""
Finviz — calendario económico.
Los datos están embebidos como JSON en un <script> tag de la página.

URL: https://finviz.com/calendar/economic

Cada entrada tiene: event, date, importance (1-3), actual, forecast, previous,
                    ticker, category, reference.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .base import BaseSource, NewsItem

FINVIZ_CALENDAR_URL = "https://finviz.com/calendar/economic"

# Mapeo importance -> estrellas (igual que Forex Factory)
IMPORTANCE_TO_STARS = {3: 3, 2: 2, 1: 1}


class FinvizCalendarSource(BaseSource):
    name = "finviz_calendar"
    display_name = "Finviz (Calendario)"

    def fetch(self) -> list[NewsItem]:
        raw = self._get(FINVIZ_CALENDAR_URL)
        if not raw:
            return []

        soup = BeautifulSoup(raw, "lxml")
        data = _extract_json(soup)
        if not data:
            return []

        entries = data.get("entries", [])
        today = datetime.now().strftime("%Y-%m-%d")

        items: list[NewsItem] = []
        for ev in entries:
            date_str = ev.get("date", "")
            # Filtrar solo eventos de hoy
            if not date_str.startswith(today):
                continue

            importance = ev.get("importance", 0)
            stars = IMPORTANCE_TO_STARS.get(importance, 0)

            # Extraer hora del date ISO (2026-07-10T10:00:00 -> "10:00")
            time_str = _extract_time(date_str)

            # El ticker de Finviz incluye el país (ej. "USAINMBA" → USA)
            ticker = ev.get("ticker", "")
            country_code = _extract_country(ticker)
            flag = _country_to_flag(country_code)

            title = ev.get("event", "").strip()
            if not title:
                continue

            actual = ev.get("actual")
            forecast = ev.get("forecast")
            previous = ev.get("previous")

            items.append(NewsItem(
                title=title,
                url=FINVIZ_CALENDAR_URL,
                source="Finviz Calendar",
                time=time_str,
                stars=stars,
                country=flag,
                currency=country_code,
                forecast=str(forecast) if forecast else "",
                previous=str(previous) if previous else "",
                actual=str(actual) if actual else "",
                summary="",
                raw=ev,
            ))

        return items


def _extract_json(soup: BeautifulSoup) -> Optional[dict]:
    """Busca el JSON del calendario embebido en un <script> tag."""
    for script in soup.find_all("script"):
        text = script.string or ""
        if "initialDateFrom" in text and "entries" in text:
            match = re.search(r'\{"data".*\}', text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                    return parsed.get("data", {})
                except json.JSONDecodeError:
                    continue
    return None


def _extract_time(date_str: str) -> str:
    """'2026-07-10T10:00:00' -> '10:00'."""
    if not date_str or "T" not in date_str:
        return ""
    try:
        return date_str.split("T")[1][:5]
    except Exception:
        return ""


def _extract_country(ticker: str) -> str:
    """
    El ticker de Finviz incluye el país al inicio.
    Ej: 'USAINMBA' -> 'USA', 'USOILRIGS' -> 'US', 'USD CALENDAR' -> 'USD'
    """
    if not ticker:
        return ""
    ticker = ticker.upper().strip()
    # Códigos de país conocidos al inicio del ticker
    # USA tiene varios prefijos: USA, USD, US (antes de otra letra)
    if ticker.startswith(("USA", "USD", "USOIL", "USTREAS", "USTOTAL")):
        return "USD"
    if ticker.startswith("US") and len(ticker) > 2 and not ticker[2].isalpha():
        return "USD"  # ej. "US 10Y" o "USD CALENDAR"
    if ticker.startswith("EU"):
        return "EUR"
    if ticker.startswith("GB"):
        return "GBP"
    if ticker.startswith("JP"):
        return "JPY"
    if ticker.startswith("CA"):
        return "CAD"
    if ticker.startswith("AU"):
        return "AUD"
    if ticker.startswith("NZ"):
        return "NZD"
    if ticker.startswith("CH"):
        return "CHF"
    if ticker.startswith("CN"):
        return "CNY"
    if "HOLIDAYS" in ticker:
        return "USD"
    return ""


# Mapeo código de país -> emoji de bandera
_COUNTRY_FLAGS = {
    "USD": "🇺🇸", "EUR": "🇪🇺", "GBP": "🇬🇧", "JPY": "🇯🇵",
    "CAD": "🇨🇦", "AUD": "🇦🇺", "NZD": "🇳🇿", "CHF": "🇨🇭",
    "CNY": "🇨🇳", "": "🌍",
}


def _country_to_flag(code: str) -> str:
    return _COUNTRY_FLAGS.get(code, "🌍")
