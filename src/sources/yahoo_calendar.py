"""
Yahoo Finance — calendario económico.
Scraping del calendario: https://finance.yahoo.com/calendar/economic?day=YYYY-MM-DD

La tabla está en el HTML (no requiere JavaScript).
Columnas: Event, Country, Event Time, For, Actual, Market Expectation, Prior.

Yahoo no marca importancia/estrellas → el LLM las asigna en el análisis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup

from .base import BaseSource, NewsItem, DEFAULT_HEADERS

YAHOO_CALENDAR_URL = "https://finance.yahoo.com/calendar/economic"


class YahooCalendarSource(BaseSource):
    name = "yahoo_calendar"
    display_name = "Yahoo Finance (Calendario)"

    def fetch(self) -> list[NewsItem]:
        # Pedir el calendario de hoy
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"{YAHOO_CALENDAR_URL}?day={today}"
        raw = self._get(url, headers={"Accept-Language": "en-US,en;q=0.9"})
        if not raw:
            return []

        soup = BeautifulSoup(raw, "lxml")
        # La tabla tiene clase yf-1hgjbtd
        table = soup.find("table")
        if not table:
            return []

        items: list[NewsItem] = []
        rows = table.find_all("tr")

        # Saltar la primera fila (encabezados)
        for row in rows[1:]:
            try:
                tds = row.find_all("td")
                if len(tds) < 8:
                    continue

                event = tds[0].get_text(strip=True)
                country = tds[1].get_text(strip=True)
                event_time = tds[2].get_text(strip=True)
                # for_period = tds[3].get_text(strip=True)  # mes de referencia
                actual = tds[4].get_text(strip=True)
                expectation = tds[5].get_text(strip=True)
                prior = tds[6].get_text(strip=True)

                if not event or event == "-":
                    continue

                # Limpiar asteriscos del nombre del evento
                event = event.replace("*", "").strip()

                # Convertir código de país a emoji de bandera
                flag = _country_to_flag(country)

                # Extraer hora (ej. "8:30 AM UTC" -> "08:30")
                time_str = _parse_time(event_time)

                items.append(NewsItem(
                    title=event,
                    url=f"{YAHOO_CALENDAR_URL}?day={today}",
                    source="Yahoo Calendar",
                    time=time_str,
                    stars=0,  # Yahoo no marca importancia → el LLM la asigna
                    country=flag,
                    currency=country if len(country) <= 3 else "",
                    forecast=expectation if expectation != "-" else "",
                    previous=prior if prior != "-" else "",
                    actual=actual if actual != "-" else "",
                    summary="",
                    raw={"country": country, "event_time": event_time},
                ))
            except Exception:
                continue

        return items


def _parse_time(time_str: str) -> str:
    """
    Convierte '8:30 AM UTC' -> '08:30'.
    Si no puede parsear, devuelve el string original.
    """
    if not time_str:
        return ""
    try:
        from dateutil import parser as dtp
        # Quitar 'UTC' para que dateutil lo parsee como hora
        clean = time_str.replace("UTC", "").strip()
        dt = dtp.parse(clean)
        return dt.strftime("%H:%M")
    except Exception:
        return time_str


# Mapeo código de país -> emoji de bandera
_COUNTRY_CODES = {
    "US": "🇺🇸", "USD": "🇺🇸", "EU": "🇪🇺", "EUR": "🇪🇺",
    "GB": "🇬🇧", "GBP": "🇬🇧", "JP": "🇯🇵", "JPY": "🇯🇵",
    "CH": "🇨🇭", "CHF": "🇨🇭", "AU": "🇦🇺", "AUD": "🇦🇺",
    "NZ": "🇳🇿", "NZD": "🇳🇿", "CA": "🇨🇦", "CAD": "🇨🇦",
    "CN": "🇨🇳", "CNY": "🇨🇳", "DE": "🇩🇪", "FR": "🇫🇷",
    "IT": "🇮🇹", "ES": "🇪🇸", "NL": "🇳🇱", "EE": "🇪🇪",
    "IN": "🇮🇳", "BR": "🇧🇷", "MX": "🇲🇽", "ZA": "🇿🇦",
    "KR": "🇰🇷", "SG": "🇸🇬", "HK": "🇭🇰", "RU": "🇷🇺",
}


def _country_to_flag(code: str) -> str:
    """Convierte un código de país/moneda a emoji de bandera."""
    if not code:
        return "🌍"
    code = code.upper().strip()
    return _COUNTRY_CODES.get(code, "🌍")
