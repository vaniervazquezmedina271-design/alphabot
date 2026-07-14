"""
Snapshot de mercado (para el reporte diario del Sistema 1) — vía yfinance.

Genera un bloque compacto, limpio y fácil de entender con el estado de los
índices y activos clave del mercado americano: índices principales
(S&P 500, Nasdaq 100, Dow Jones, Russell 2000), volatilidad (VIX),
petróleo (WTI) y oro, con el cambio % vs el cierre anterior.

Estilo simple tipo Sistema 2: nombres cortos, emojis claros, sin jerga.
Se envía como un MENSAJE APARTE, separado del reporte de eventos económicos.

NOTA: por decisión del usuario NO se incluye el bono del Tesoro 10 años ni el
índice del dólar (DXY): complican la lectura y no se quieren ver.
"""
from __future__ import annotations

# (etiqueta corta, símbolo Yahoo, emoji, tipo)
#   pct        -> muestra solo el cambio %
#   level_pct  -> muestra nivel + cambio % (VIX)
_SNAP = [
    ("S&P 500", "^GSPC", "🇺🇸", "pct"),
    ("Nasdaq", "^NDX", "💻", "pct"),
    ("Dow Jones", "^DJI", "🏭", "pct"),
    ("Russell 2000", "^RUT", "🏢", "pct"),
    ("VIX (miedo)", "^VIX", "😨", "level_pct"),
    ("Petróleo", "CL=F", "🛢️", "pct"),
    ("Oro", "GC=F", "🥇", "pct"),
]


def _fetch(symbols: list[str]) -> dict[str, dict]:
    """Devuelve {símbolo: {'last': float, 'pct': float}} con el cambio del día."""
    import yfinance as yf
    import pandas as pd

    try:
        # 5d (no 2d): al mezclar futuros/índices, una ventana corta deja NaN y
        # solo 1 dato válido para WTI/Oro. Con 5d siempre quedan ≥2 cierres de
        # mercado tras dropna.
        data = yf.download(symbols, period="5d", interval="1d",
                           progress=False, group_by="column", threads=True)
    except Exception:
        return {}
    if data is None or data.empty:
        return {}
    try:
        closes = data["Close"]
    except Exception:
        return {}

    if isinstance(closes, pd.Series):
        col_map = {symbols[0]: closes}
    else:
        col_map = {s: closes[s] for s in closes.columns}

    out: dict[str, dict] = {}
    for sym, serie in col_map.items():
        try:
            serie = serie.dropna()
            if len(serie) == 0:
                continue
            last = float(serie.iloc[-1])
            if len(serie) >= 2 and float(serie.iloc[-2]) > 0:
                prev = float(serie.iloc[-2])
                pct = (last - prev) / prev * 100.0
            else:
                pct = 0.0
            out[sym] = {"last": last, "pct": pct}
        except Exception:
            continue
    return out


def _dot(pct: float) -> str:
    """Punto de color según el signo del cambio."""
    if pct > 0.05:
        return "🟢"
    if pct < -0.05:
        return "🔴"
    return "⚪"


def format_market_snapshot() -> str:
    """
    Devuelve un bloque HTML con el panorama de mercado limpio y simple, o ""
    si falla. Se envía como MENSAJE APARTE (antes del reporte de eventos).
    """
    try:
        symbols = [s for _, s, _, _ in _SNAP]
        data = _fetch(symbols)
        if not data:
            return ""

        lineas = []
        for label, sym, emoji, kind in _SNAP:
            d = data.get(sym)
            if not d:
                continue
            pct = d["pct"]
            last = d["last"]
            signo = "+" if pct >= 0 else ""
            if kind == "level_pct":
                # VIX: sube = miedo (rojo); baja = calma (verde). Mostrar nivel + %.
                lineas.append(f"{emoji} <b>{label}</b>: {last:.0f} ({signo}{pct:.1f}%)")
            else:
                lineas.append(f"{_dot(pct)} <b>{label}</b>: {signo}{pct:.1f}%")

        if not lineas:
            return ""

        cuerpo = "\n".join(lineas)
        return (
            f"🌎 <b>CÓMO ESTÁ EL MERCADO HOY</b>\n\n"
            f"{cuerpo}"
        )
    except Exception:
        return ""
