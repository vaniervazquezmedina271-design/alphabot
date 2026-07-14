"""
Alertas de precio (Sistema 2b) — vía yfinance.

Avisa por Telegram cuando un ticker de tu watchlist se mueve fuerte en el día
(porcentaje vs el cierre anterior). Complementa las alertas de NOTICIAS:
esto detecta el MOVIMIENTO de precio aunque no haya salido una noticia.

- Umbral configurable: filter.price_move_pct (default 5%).
- Un solo mensaje consolidado con todos los que se movieron (no spam).
- Dedup por día y dirección: no repite el mismo ticker+dirección el mismo día.
- Solo alerta en días con datos frescos (evita movimientos viejos de fin de semana).
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from .config import load_config, CACHE_DIR
from .watchlist import load_watchlist
from .notifier import send_to_telegram

# Algunos símbolos de índice necesitan prefijo "^" en Yahoo Finance.
_YF_SYMBOL = {"SPX": "^GSPC", "VIX": "^VIX", "DJI": "^DJI"}


def _ny_today() -> str:
    try:
        from dateutil import tz
        return datetime.now(tz.gettz("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _yf_symbol(ticker: str) -> str:
    return _YF_SYMBOL.get(ticker.upper(), ticker.upper())


def _sent_file():
    return CACHE_DIR / f"sent_price_{_ny_today()}.json"


def _load_sent() -> set:
    f = _sent_file()
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fh:
                return set(json.load(fh))
        except Exception:
            return set()
    return set()


def _save_sent(sent: set) -> None:
    try:
        with open(_sent_file(), "w", encoding="utf-8") as fh:
            json.dump(list(sent), fh)
    except Exception:
        pass


def _fetch_daily_changes(tickers: list[str]) -> dict[str, dict]:
    """
    Devuelve {ticker: {"pct": float, "price": float}} con el cambio % del día
    (vs cierre anterior). Usa una sola descarga en lote de yfinance.
    Solo incluye tickers cuyo último dato es de HOY (datos frescos).
    """
    import yfinance as yf

    symbols = [_yf_symbol(t) for t in tickers]
    sym_to_ticker = {_yf_symbol(t): t for t in tickers}

    try:
        data = yf.download(
            symbols, period="2d", interval="1d",
            progress=False, group_by="column", threads=True,
        )
    except Exception as e:
        print(f"  ⚠️ yfinance error: {e}")
        return {}

    if data is None or data.empty:
        return {}

    try:
        closes = data["Close"]
    except Exception:
        return {}

    # Fecha del último dato (para exigir datos frescos de hoy)
    try:
        last_date = closes.index[-1].strftime("%Y-%m-%d")
    except Exception:
        last_date = ""
    if last_date and last_date != _ny_today():
        # El mercado no operó hoy (fin de semana/feriado) → no alertar movimientos viejos
        return {}

    out: dict[str, dict] = {}
    # closes puede ser DataFrame (varios) o Series (uno)
    import pandas as pd
    if isinstance(closes, pd.Series):
        col_map = {symbols[0]: closes}
    else:
        col_map = {sym: closes[sym] for sym in closes.columns}

    for sym, serie in col_map.items():
        try:
            serie = serie.dropna()
            if len(serie) < 2:
                continue
            prev = float(serie.iloc[-2])
            last = float(serie.iloc[-1])
            if prev <= 0:
                continue
            pct = (last - prev) / prev * 100.0
            ticker = sym_to_ticker.get(sym, sym)
            out[ticker] = {"pct": pct, "price": last}
        except Exception:
            continue

    return out


def run_price_alerts() -> int:
    """
    Revisa el % del día de cada ticker de la watchlist y envía UNA alerta
    consolidada con los que superan el umbral (filter.price_move_pct).
    Devuelve cuántos movimientos se reportaron (0 si ninguno).
    """
    cfg = load_config()
    threshold = float(cfg.get("filter", {}).get("price_move_pct", 5))

    companies = load_watchlist()
    if not companies:
        return 0

    tickers = [c["ticker"] for c in companies]
    name_by_ticker = {c["ticker"]: c.get("name", c["ticker"]) for c in companies}

    changes = _fetch_daily_changes(tickers)
    if not changes:
        return 0

    sent = _load_sent()
    movers = []
    for ticker, info in changes.items():
        pct = info["pct"]
        if abs(pct) < threshold:
            continue
        direction = "up" if pct > 0 else "down"
        key = f"{ticker}:{direction}"
        if key in sent:
            continue  # ya avisado hoy en esa dirección
        movers.append((ticker, pct, info["price"], key))

    if not movers:
        return 0

    # Ordenar por magnitud del movimiento (mayor primero)
    movers.sort(key=lambda m: -abs(m[1]))

    from .formatter import _ny_now, _saludo, SEPARATOR
    ny = _ny_now()
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia = dias[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")
    hora = ny.strftime("%H:%M")

    lineas = []
    for ticker, pct, price, _key in movers:
        emoji = "📈" if pct > 0 else "📉"
        signo = "+" if pct > 0 else ""
        nombre = name_by_ticker.get(ticker, ticker)
        lineas.append(f"{emoji} <b>{ticker}</b> {nombre} · {signo}{pct:.1f}% · ${price:,.2f}")

    # Caption (texto con nombres, va junto a la imagen). Sin blockquote (caption).
    caption = (
        f"📊 <b>MOVIMIENTOS FUERTES</b> · watchlist\n"
        f"{dia} {fecha} · {hora} ET · umbral ±{threshold:.0f}%\n\n"
        + "\n".join(lineas)
        + f"\n\n🤖 AlphaBot · {_saludo()}"
    )
    # Mensaje de respaldo (texto puro con separadores) si la imagen falla
    mensaje = (
        f"📊 <b>MOVIMIENTOS FUERTES</b> (watchlist)\n"
        f"{dia} {fecha} · {hora} ET · umbral ±{threshold:.0f}%\n"
        f"{SEPARATOR}\n\n"
        + "\n".join(lineas)
        + f"\n\n{SEPARATOR}\n🤖 AlphaBot · {_saludo()}"
    )

    print(f"  💹 {len(movers)} movimiento(s) de precio ≥ {threshold}% → enviando a Telegram")

    # Intentar imagen profesional; si falla, enviar texto
    ok = False
    try:
        from .price_chart import render_price_movers_image
        from .notifier import send_photo_to_telegram
        img = render_price_movers_image(
            [(t, p, pr) for (t, p, pr, _k) in movers], threshold, name_by_ticker
        )
        if img:
            ok = send_photo_to_telegram(img, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"  ⚠️ Imagen de precios falló, uso texto: {e}")

    if not ok:
        ok = send_to_telegram(mensaje, parse_mode="HTML")

    if ok:
        for _t, _p, _pr, key in movers:
            sent.add(key)
        _save_sent(sent)
        return len(movers)
    return 0
