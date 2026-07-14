"""
Calendario de earnings (resultados) de la watchlist — vía yfinance.

Añade al reporte diario un bloque con las empresas de tu lista que reportan
resultados en los próximos días. Los ETFs/índices no tienen earnings, se omiten.
"""
from __future__ import annotations

from datetime import datetime, date, timedelta

from .watchlist import load_watchlist

# ETFs / índices de la watchlist: NO tienen earnings, se saltan.
ETF_TICKERS = {"SOXL", "DIA", "QQQ", "SPY", "SPX", "IWM", "TNA", "URA", "USO", "SLV", "GLD"}


def _next_earnings_date(ticker: str):
    """Devuelve la próxima fecha de earnings (date) del ticker, o None."""
    import yfinance as yf
    try:
        cal = yf.Ticker(ticker).calendar
    except Exception:
        return None

    raw = None
    try:
        if isinstance(cal, dict):
            raw = cal.get("Earnings Date")
        else:
            # DataFrame (versiones antiguas de yfinance)
            if cal is not None and "Earnings Date" in getattr(cal, "index", []):
                raw = cal.loc["Earnings Date"].tolist()
    except Exception:
        raw = None

    if not raw:
        return None
    if not isinstance(raw, (list, tuple)):
        raw = [raw]

    # Normalizar a date y quedarse con la próxima (>= hoy)
    hoy = date.today()
    fechas = []
    for d in raw:
        try:
            if isinstance(d, datetime):
                fechas.append(d.date())
            elif isinstance(d, date):
                fechas.append(d)
            else:
                fechas.append(datetime.fromisoformat(str(d)[:10]).date())
        except Exception:
            continue

    futuras = sorted(f for f in fechas if f >= hoy)
    if futuras:
        return futuras[0]
    return sorted(fechas)[-1] if fechas else None


def format_earnings_calendar(days_ahead: int = 7) -> str:
    """
    Bloque HTML con las empresas de la watchlist que reportan en los próximos
    `days_ahead` días. Devuelve "" si no hay ninguna o si falla.
    """
    try:
        companies = load_watchlist()
        if not companies:
            return ""

        hoy = date.today()
        limite = hoy + timedelta(days=days_ahead)

        proximos = []
        for c in companies:
            ticker = c["ticker"]
            if ticker.upper() in ETF_TICKERS:
                continue
            fecha = _next_earnings_date(ticker)
            if fecha and hoy <= fecha <= limite:
                proximos.append((fecha, ticker, c.get("name", ticker)))

        if not proximos:
            return ""

        proximos.sort(key=lambda x: x[0])
        dias_sem = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
        lineas = []
        for fecha, ticker, nombre in proximos:
            etiqueta = f"{dias_sem[fecha.weekday()]} {fecha.strftime('%d/%m')}"
            marca = " 🔔 <b>HOY</b>" if fecha == hoy else ""
            lineas.append(f"📌 <b>{ticker}</b> {nombre} — {etiqueta}{marca}")

        from .formatter import SEPARATOR
        cuerpo = "\n".join(lineas)
        return (
            f"📅 <b>EARNINGS PRÓXIMOS</b> (tu watchlist · {days_ahead} días)\n"
            f"<blockquote expandable>{cuerpo}</blockquote>\n"
            f"{SEPARATOR}\n\n"
        )
    except Exception:
        return ""
