"""
Market Reaction — reacción del mercado a eventos de discurso/comparecencia.

Para eventos SIN número (discursos, comparecencias de la Fed, testimonios,
"speech"/"speaks"/"testimony"), el "resultado" NO es un BEAT/MISS sino la
REACCIÓN del mercado a lo que se dijo, que puede ser positiva o negativa.

Este módulo mide esa reacción con los 4 ETFs de referencia del mercado USA:
    SPY → S&P 500
    QQQ → Nasdaq 100
    IWM → Russell 2000
    DIA → Dow Jones

Usa yfinance (ya es dependencia; mismo patrón que price_alerts.py /
earnings_calendar.py). NUNCA lanza: si algo falla, devuelve lo que pueda y
marca los ETFs que no se pudieron calcular.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from dateutil import tz

_NY_TZ = tz.gettz("America/New_York")

# ETFs de referencia + nombre legible (el usuario pidió nomenclaturas entendibles)
ETF_NAMES = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq 100",
    "IWM": "Russell 2000",
    "DIA": "Dow Jones",
}
ETF_ORDER = ["SPY", "QQQ", "IWM", "DIA"]

# Umbral (en %) para considerar que un ETF "se movió" (fija la flecha ➡️).
_FLAT_PCT = 0.05


def _arrow(pct: float) -> str:
    """Flecha según el signo/magnitud del movimiento."""
    if pct >= _FLAT_PCT:
        return "📈"
    if pct <= -_FLAT_PCT:
        return "📉"
    return "➡️"


def _ensure_ny(dt) -> datetime:
    """Normaliza un datetime a tz-aware en zona horaria de Nueva York."""
    if dt is None:
        return datetime.now(_NY_TZ)
    try:
        if getattr(dt, "tzinfo", None) is None:
            return dt.replace(tzinfo=_NY_TZ)
        return dt.astimezone(_NY_TZ)
    except Exception:
        return datetime.now(_NY_TZ)


def _column(data, field: str):
    """Extrae de forma robusta un campo ('Close'/'High'/'Low') del DataFrame de yfinance."""
    try:
        return data[field]
    except Exception:
        return None


def _col_map(frame, tickers: list[str]):
    """Convierte un Series/DataFrame de yfinance en {ticker: Series}."""
    import pandas as pd
    if frame is None:
        return {}
    if isinstance(frame, pd.Series):
        return {tickers[0]: frame}
    try:
        return {sym: frame[sym] for sym in frame.columns}
    except Exception:
        return {}


def _reaction_intraday(start: datetime) -> dict[str, dict]:
    """
    Reacción INTRADÍA (barras de 5m) de cada ETF DESDE la barra más cercana
    (>=) a `start` HASTA la última barra disponible.

    Devuelve {ticker: {"pct": float, "max_up": float, "max_down": float}}:
      - pct:      % del último cierre respecto al cierre de la barra de inicio.
      - max_up:   % máximo AL ALZA (mayor High del tramo vs precio de inicio).
      - max_down: % máximo A LA BAJA (menor Low del tramo vs precio de inicio).
    Solo incluye los tickers que se pudieron calcular.
    """
    import yfinance as yf

    data = yf.download(
        ETF_ORDER, period="1d", interval="5m",
        progress=False, group_by="column", threads=True,
    )
    if data is None or data.empty:
        return {}

    closes = _column(data, "Close")
    if closes is None:
        return {}
    highs = _column(data, "High")
    lows = _column(data, "Low")

    # Normalizar el índice a hora de Nueva York para comparar con `start`.
    for frame in (closes, highs, lows):
        try:
            if frame is None:
                continue
            idx = frame.index
            if idx.tz is None:
                frame.index = idx.tz_localize("UTC").tz_convert(_NY_TZ)
            else:
                frame.index = idx.tz_convert(_NY_TZ)
        except Exception:
            pass

    close_map = _col_map(closes, ETF_ORDER)
    high_map = _col_map(highs, ETF_ORDER)
    low_map = _col_map(lows, ETF_ORDER)

    out: dict[str, dict] = {}
    for ticker, serie in close_map.items():
        try:
            serie = serie.dropna()
            if len(serie) < 2:
                continue
            # Barra de referencia: la primera con índice >= start.
            try:
                ref_slice = serie[serie.index >= start]
            except Exception:
                ref_slice = serie
            if len(ref_slice) >= 1:
                ref = float(ref_slice.iloc[0])
                ref_ts = ref_slice.index[0]
            else:
                ref = float(serie.iloc[0])
                ref_ts = serie.index[0]
            last = float(serie.iloc[-1])
            if ref <= 0:
                continue

            pct = (last - ref) / ref * 100.0
            max_up = max(pct, 0.0)
            max_down = min(pct, 0.0)

            # Rango alza/baja usando High/Low del tramo [ref_ts, fin].
            try:
                hs = high_map.get(ticker)
                if hs is not None:
                    hs = hs.dropna()
                    hs = hs[hs.index >= ref_ts]
                    if len(hs) >= 1:
                        max_up = max(max_up, (float(hs.max()) - ref) / ref * 100.0)
            except Exception:
                pass
            try:
                ls = low_map.get(ticker)
                if ls is not None:
                    ls = ls.dropna()
                    ls = ls[ls.index >= ref_ts]
                    if len(ls) >= 1:
                        max_down = min(max_down, (float(ls.min()) - ref) / ref * 100.0)
            except Exception:
                pass

            out[ticker] = {"pct": pct, "max_up": max_up, "max_down": max_down}
        except Exception:
            continue

    return out


def _reaction_daily(tickers: list[str]) -> dict[str, dict]:
    """
    FALLBACK: cambio del día (último cierre vs cierre previo) de cada ticker.
    Se usa cuando no hay datos intradía (fuera de sesión, fallo). El rango
    alza/baja se aproxima con el High/Low del día vs el cierre previo.

    Devuelve {ticker: {"pct": float, "max_up": float, "max_down": float}}.
    """
    import yfinance as yf

    if not tickers:
        return {}

    data = yf.download(
        tickers, period="2d", interval="1d",
        progress=False, group_by="column", threads=True,
    )
    if data is None or data.empty:
        return {}

    closes = _column(data, "Close")
    if closes is None:
        return {}
    highs = _column(data, "High")
    lows = _column(data, "Low")

    close_map = _col_map(closes, tickers)
    high_map = _col_map(highs, tickers)
    low_map = _col_map(lows, tickers)

    out: dict[str, dict] = {}
    for ticker, serie in close_map.items():
        try:
            serie = serie.dropna()
            if len(serie) < 2:
                continue
            prev = float(serie.iloc[-2])
            last = float(serie.iloc[-1])
            if prev <= 0:
                continue
            pct = (last - prev) / prev * 100.0
            max_up = max(pct, 0.0)
            max_down = min(pct, 0.0)
            try:
                hs = high_map.get(ticker)
                if hs is not None:
                    hs = hs.dropna()
                    if len(hs) >= 1:
                        max_up = max(max_up, (float(hs.iloc[-1]) - prev) / prev * 100.0)
            except Exception:
                pass
            try:
                ls = low_map.get(ticker)
                if ls is not None:
                    ls = ls.dropna()
                    if len(ls) >= 1:
                        max_down = min(max_down, (float(ls.iloc[-1]) - prev) / prev * 100.0)
            except Exception:
                pass
            out[ticker] = {"pct": pct, "max_up": max_up, "max_down": max_down}
        except Exception:
            continue

    return out


def _aggregate_bias(ups: int, downs: int, total: float, n_ok: int) -> str:
    """
    Sesgo agregado según cuántos ETFs suben vs bajan y la magnitud media.
    Devuelve: "positivo" | "negativo" | "mixto" | "neutral".
    """
    if n_ok == 0:
        return "neutral"
    if ups > 0 and downs == 0:
        return "positivo"
    if downs > 0 and ups == 0:
        return "negativo"
    if ups == 0 and downs == 0:
        return "neutral"
    # Movimientos en ambas direcciones → decidir por el promedio si es claro.
    if total >= 0.10 and ups >= downs:
        return "positivo"
    if total <= -0.10 and downs >= ups:
        return "negativo"
    return "mixto"


def etf_reaction_since(start_dt) -> dict:
    """
    Movimiento % de SPY / QQQ / IWM / DIA desde `start_dt` (inicio del discurso)
    hasta ahora.

    - Intenta datos INTRADÍA (5m): barra más cercana (>=) a start_dt como
      referencia y última barra como actual → %.
    - FALLBACK al cambio del día para los ETFs que no tengan intradía.
    - Nunca lanza. Devuelve:
        {
          "etfs": {
            "SPY": {"name": "S&P 500", "pct": 0.42, "arrow": "📈",
                    "max_up": 0.55, "max_down": -0.12, "ok": True},
            ...
          },
          "bias": "positivo|negativo|mixto|neutral",
          "max_abs_move": float,   # mayor movimiento absoluto de los 4
          "avg_move": float,       # promedio de los que se pudieron calcular
          "source": "intraday|daily|mixto|none",
        }

    Los campos max_up (máximo al alza) y max_down (máximo a la baja), relativos
    al precio de inicio, sirven para el "rango alza/baja" del cierre y para
    detectar giros durante el discurso.
    """
    start = _ensure_ny(start_dt)

    by_ticker: dict[str, dict] = {}
    source = "none"

    # 1) Intradía (preferido)
    try:
        intr = _reaction_intraday(start)
    except Exception:
        intr = {}
    if intr:
        by_ticker.update(intr)
        source = "intraday"

    # 2) Fallback diario para los ETFs que falten
    missing = [t for t in ETF_ORDER if t not in by_ticker]
    if missing:
        try:
            daily = _reaction_daily(missing)
        except Exception:
            daily = {}
        if daily:
            by_ticker.update(daily)
            source = "daily" if source == "none" else "mixto"

    etfs: dict[str, dict] = {}
    ups = downs = n_ok = 0
    max_abs = 0.0
    total = 0.0
    for t in ETF_ORDER:
        if t in by_ticker:
            d = by_ticker[t]
            pct = d.get("pct", 0.0)
            etfs[t] = {
                "name": ETF_NAMES[t],
                "pct": pct,
                "arrow": _arrow(pct),
                "max_up": d.get("max_up", max(pct, 0.0)),
                "max_down": d.get("max_down", min(pct, 0.0)),
                "ok": True,
            }
            max_abs = max(max_abs, abs(pct))
            total += pct
            n_ok += 1
            if pct > _FLAT_PCT:
                ups += 1
            elif pct < -_FLAT_PCT:
                downs += 1
        else:
            # No se pudo calcular este ETF → marcarlo.
            etfs[t] = {"name": ETF_NAMES[t], "pct": None, "arrow": "❔",
                       "max_up": None, "max_down": None, "ok": False}

    return {
        "etfs": etfs,
        "bias": _aggregate_bias(ups, downs, total, n_ok),
        "max_abs_move": max_abs,
        "avg_move": (total / n_ok) if n_ok else 0.0,
        "source": source,
    }
