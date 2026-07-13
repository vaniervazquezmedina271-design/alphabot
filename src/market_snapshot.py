"""
Snapshot de mercado (para el reporte diario del Sistema 1) — vía yfinance.

Genera un bloque compacto con el estado de los índices y activos clave del
mercado americano (S&P 500, Nasdaq 100, Dow, Russell 2000), volatilidad (VIX),
materias primas (petróleo, oro), bono 10Y, dólar (DXY) y cripto (BTC/ETH),
con el cambio % vs el cierre anterior. Se antepone al reporte diario.
"""
from __future__ import annotations

# (etiqueta, símbolo Yahoo, tipo)
#   pct        -> muestra solo el cambio %
#   level_pct  -> muestra nivel + cambio % (VIX)
#   level      -> muestra solo el nivel (rendimiento del bono, en %)
_SNAP = [
    ("S&P 500", "^GSPC", "pct"),
    ("Nasdaq 100", "^NDX", "pct"),
    ("Dow Jones", "^DJI", "pct"),
    ("Russell 2000", "^RUT", "pct"),
    ("VIX", "^VIX", "level_pct"),
    ("WTI petróleo", "CL=F", "pct"),
    ("Oro", "GC=F", "pct"),
    ("Bono 10Y", "^TNX", "level"),
    ("Dólar (DXY)", "DX-Y.NYB", "pct"),
]


def _fetch(symbols: list[str]) -> dict[str, dict]:
    """Devuelve {símbolo: {'last': float, 'pct': float}} con el cambio del día."""
    import yfinance as yf
    import pandas as pd

    try:
        # 5d (no 2d): al mezclar cripto (cotiza findes) con futuros/índices, una
        # ventana corta deja NaN y solo 1 dato válido para WTI/Oro/DXY. Con 5d
        # siempre quedan ≥2 cierres de mercado tras dropna.
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


def _arrow(pct: float) -> str:
    if pct > 0.05:
        return "🟢"
    if pct < -0.05:
        return "🔴"
    return "⚪"


def format_market_snapshot() -> str:
    """
    Devuelve un bloque HTML con el panorama de mercado, o "" si falla.
    Pensado para anteponerse al reporte diario.
    """
    try:
        symbols = [s for _, s, _ in _SNAP]
        data = _fetch(symbols)
        if not data:
            return ""

        lineas = []
        for label, sym, kind in _SNAP:
            d = data.get(sym)
            if not d:
                continue
            pct = d["pct"]
            last = d["last"]
            if kind == "level":
                lineas.append(f"{_arrow(pct)} <b>{label}</b>: {last:.2f}%")
            elif kind == "level_pct":
                signo = "+" if pct >= 0 else ""
                lineas.append(f"{_arrow(-pct)} <b>{label}</b>: {last:.1f} ({signo}{pct:.1f}%)")
            else:
                signo = "+" if pct >= 0 else ""
                lineas.append(f"{_arrow(pct)} <b>{label}</b>: {signo}{pct:.1f}%")

        if not lineas:
            return ""

        from .formatter import SEPARATOR
        cuerpo = "\n".join(lineas)
        return (
            f"🌎 <b>PANORAMA DE MERCADO</b>\n"
            f"<blockquote expandable>{cuerpo}</blockquote>\n"
            f"{SEPARATOR}\n\n"
        )
    except Exception:
        return ""
