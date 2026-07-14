"""
Report — orquestador del pipeline.

DOS SISTEMAS SEPARADOS:

1. REPORTE DIARIO (8am): SOLO calendario económico de Finviz.
   Eventos programados con hora fija y estrellas (IPC, Fed, BCE, NFP...).
   Se agrupan en un solo mensaje. NO usa noticias en tiempo real.

2. ALERTAS EN TIEMPO REAL: noticias que van saliendo (CNBC, Yahoo, Bloomberg, Finviz).
   NO se acumulan: cada una se envía al instante cuando aparece.
   Solo alto impacto de la watchlist del usuario.
"""
from __future__ import annotations

import json
import os
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import load_config, HISTORY_DIR, CACHE_DIR
from .sources.base import NewsItem
from .sources.forex_factory import ForexFactorySource
from .sources.investing import InvestingSource
from .sources.yahoo_finance import YahooFinanceSource
from .sources.yahoo_calendar import YahooCalendarSource
from .sources.finviz import FinvizSource
from .sources.finviz_calendar import FinvizCalendarSource
from .sources.bloomberg_rss import BloombergRSSSource
from .sources.reuters import ReutersSource
from .analyzer import analyze_batch, analyze_single, analyze_batch_breaking
from .formatter import format_daily_report, format_breaking_alert
from .notifier import send_to_telegram
from .watchlist import match_company, get_watchlist_min_score, load_watchlist, is_noisy_etf
from .backup import save_report_backup, save_alert_backup
from .results_tracker import track_events_from_report, run_results_tracking


# ============================================================
#  REGISTRO DE FUENTES POR TIPO
# ============================================================

# SISTEMA 1 — Calendario macro (eventos programados con estrellas)
CALENDAR_SOURCES = {
    "forex_factory": ForexFactorySource,
    "yahoo_calendar": YahooCalendarSource,
    "finviz_calendar": FinvizCalendarSource,
}

# SISTEMA 2 — Noticias en tiempo real (van saliendo)
NEWS_SOURCES = {
    "reuters": ReutersSource,
    "investing": InvestingSource,
    "yahoo_finance": YahooFinanceSource,
    "finviz": FinvizSource,
    "bloomberg_rss": BloombergRSSSource,
}

# Registro completo para compatibilidad con el dashboard
ALL_SOURCES = {**CALENDAR_SOURCES, **NEWS_SOURCES}


# ============================================================
#  HEALTH-CHECK DE FUENTES (avisa si una fuente deja de traer noticias)
# ============================================================

HEALTH_FILE = CACHE_DIR / "source_health.json"
HEALTH_ZERO_THRESHOLD = 3   # nº de ejecuciones seguidas con 0 ítems para avisar


def _load_health() -> dict:
    if HEALTH_FILE.exists():
        try:
            with open(HEALTH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_health(state: dict) -> None:
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass


def _record_source_health(name: str, count: int) -> None:
    """
    Registra cuántos ítems trajo una fuente. Lleva la cuenta de ejecuciones
    seguidas con 0 resultados. Si vuelve a traer datos, se resetea.
    """
    state = _load_health()
    entry = state.get(name, {"zeros": 0, "alerted": False})
    if count > 0:
        entry = {"zeros": 0, "alerted": False}
    else:
        entry["zeros"] = entry.get("zeros", 0) + 1
    state[name] = entry
    _save_health(state)


def notify_unhealthy_sources() -> int:
    """
    Avisa por Telegram (una sola vez) de las fuentes que llevan varias
    ejecuciones seguidas trayendo 0 noticias. Devuelve cuántas se avisaron.
    Evita "silencios" sin que te enteres (como pasó con el Sistema 1).
    """
    state = _load_health()
    caidas = [
        name for name, e in state.items()
        if e.get("zeros", 0) >= HEALTH_ZERO_THRESHOLD and not e.get("alerted")
    ]
    if not caidas:
        return 0

    lista = ", ".join(caidas)
    msg = (
        "⚠️ <b>Aviso de fuentes</b>\n"
        f"Estas fuentes llevan {HEALTH_ZERO_THRESHOLD}+ ejecuciones sin traer "
        f"noticias (quizá cambiaron su web o están caídas):\n\n<code>{lista}</code>\n\n"
        "Revisa el scraper correspondiente en <code>src/sources/</code>."
    )
    try:
        send_to_telegram(msg, parse_mode="HTML")
    except Exception:
        pass

    # Marcar como avisadas para no repetir el aviso cada ejecución
    for name in caidas:
        state[name]["alerted"] = True
    _save_health(state)
    return len(caidas)


# ============================================================
#  SISTEMA 1 — REPORTE DIARIO (calendario macro)
# ============================================================

def fetch_calendar_sources() -> list[NewsItem]:
    """Scrapea solo las fuentes de calendario (eventos programados)."""
    cfg = load_config()
    sources_cfg = cfg.get("sources", {})
    all_items: list[NewsItem] = []

    for name, cls in CALENDAR_SOURCES.items():
        if not sources_cfg.get(name, {}).get("enabled", True):
            continue
        try:
            src = cls()
            items = src.fetch()
            all_items.extend(items)
            _record_source_health(name, len(items))
            print(f"  📅 {src.display_name}: {len(items)} eventos")
        except Exception as e:
            _record_source_health(name, 0)
            print(f"  ⚠️ {name}: error {e}")

    return all_items


def _is_us_relevant(item: NewsItem) -> bool:
    """
    Filtro PRELIMINAR (no estricto) para el calendario macro.
    Descarta eventos claramente regionales que NO afectan al mercado americano.

    NOTA: ya NO se usa en el Sistema 1 (el calendario de Finviz es solo de
    EE.UU.). Se conserva por compatibilidad y por si vuelve a activarse otra
    fuente de calendario multi-país en el futuro.
    """
    currency = (item.currency or "").upper().strip()
    country = (item.country or "").strip()

    # Eventos de USA → siempre relevantes
    if currency == "USD" or country in ("🇺🇸", "US", "USA"):
        return True

    # Fuentes de NOTICIAS en tiempo real → siempre relevantes (el LLM decide después)
    source = (item.source or "").lower()
    is_calendar_source = "calendar" in source or "forex factory" in source
    if not is_calendar_source:
        if any(s in source for s in ["cnbc", "marketwatch", "yahoo", "bloomberg", "finviz"]):
            return True

    # Eventos internacionales que SUELEN afectar a USA (por título)
    title = (item.title or "").lower()
    intl_relevant = [
        "opec", "china tariff", "chinese tariff", "trade war",
        "european union", "eu regulation", "eu tech",
        "sanctions", "semiconductor", "chips",
        "brexit", "uk economy",
    ]
    if any(kw in title for kw in intl_relevant):
        return True

    return False


def generate_daily_report(reasoning: bool = True) -> tuple[str, list[dict]]:
    """
    SISTEMA 1 — Reporte diario de eventos macro programados.
    Usa SOLO el calendario económico de Finviz.
    Scrapea el calendario → filtra por estrellas → analiza → formatea.

    NOTA: el calendario de Finviz ya trae solo eventos de EE.UU., por lo que
    NO se filtra por país aquí. La relevancia para EE.UU. es una peculiaridad
    del Sistema 2 (noticias en tiempo real), NO del Sistema 1.

    Devuelve (texto_formateado, lista_de_entradas).
    """
    cfg = load_config()
    min_stars = cfg.get("filter", {}).get("min_stars", 2)

    print("📅 Scrapeando calendario macro de Finviz (Sistema 1)...")
    calendar_items = fetch_calendar_sources()
    calendar_items = deduplicate(calendar_items)

    # ÚNICO FILTRO: impacto por estrellas (2+). Todos los eventos del calendario
    # de Finviz son de EE.UU., así que no se descarta nada por país.
    items = [it for it in calendar_items if it.stars >= min_stars]
    print(f"  ⭐ {len(items)} de {len(calendar_items)} eventos con {min_stars}+ estrellas")

    # Encabezado del reporte: panorama de mercado + earnings próximos (vía yfinance)
    try:
        from .market_snapshot import format_market_snapshot
        snapshot = format_market_snapshot()
    except Exception:
        snapshot = ""
    try:
        from .earnings_calendar import format_earnings_calendar
        earnings = format_earnings_calendar(days_ahead=7)
    except Exception:
        earnings = ""
    header = snapshot + earnings

    if not items:
        return header + "📊 No hay eventos macro de alto impacto programados hoy para el mercado americano.", []

    # Limitar a 10 para que el LLM devuelva JSON completo
    items = items[:10]

    print(f"🧠 Analizando {len(items)} eventos macro con LLM...")
    analyses = analyze_batch(items, reasoning=reasoning)

    # Construir entradas
    entries = []
    for item, analysis in zip(items, analyses):
        if analysis and isinstance(analysis, dict):
            entries.append({"item": item, "analysis": analysis})

    # Ordenar por estrellas (3 primero) y por hora
    entries.sort(key=lambda e: (-e["item"].stars, e["item"].time or ""))

    if not entries:
        return "📊 No se pudo analizar los eventos.", []

    print(f"📊 {len(entries)} eventos macro de alto impacto")
    report_text = header + format_daily_report(entries)

    # Guardar historial + backup automático
    _save_history(report_text, entries)
    save_report_backup(report_text, entries)

    # Registrar eventos para seguimiento de resultados (Sección 1)
    track_events_from_report(entries)

    return report_text, entries


def run_and_send(reasoning: bool = True, force: bool = False) -> bool:
    """
    SISTEMA 1 — Genera el reporte diario y lo envía a Telegram.

    GUARD anti-duplicado: el cron del Sistema 1 dispara varias veces dentro de
    la ventana 7-8 AM NY (minutos desfasados) porque GitHub Actions retrasa o
    salta las ejecuciones "a la hora en punto". Para que el reporte salga UNA
    sola vez al día, se consulta el estado compartido (data/state/daily_report.json):
    si ya se envió hoy (hora NY), se omite. Tras enviarlo con éxito se marca.

    force=True omite el guard (acción explícita del usuario por /report).
    """
    # Traer el guard más reciente (en local hace git pull; en la nube el
    # checkout ya trae lo último) y comprobar si ya salió hoy.
    if not force:
        try:
            from .sent_state import pull as _pull_state, daily_report_sent_today
            _pull_state()
            if daily_report_sent_today():
                print("⏭️ Reporte diario ya enviado hoy (guard). Omitido para no duplicar.")
                return False
        except Exception as e:
            print(f"  ⚠️ Guard reporte diario: {e}")

    report_text, entries = generate_daily_report(reasoning)
    print(f"\n📊 Reporte generado ({len(report_text)} chars, {len(entries)} eventos)")

    # Avisar si alguna fuente de calendario lleva varias ejecuciones sin datos
    notify_unhealthy_sources()

    ok = send_to_telegram(report_text)
    if ok:
        print("✅ Reporte enviado a Telegram.")
        # Marcar el guard compartido para que el cron no lo repita hoy.
        try:
            from .sent_state import mark_daily_report_sent
            mark_daily_report_sent()
        except Exception as e:
            print(f"  ⚠️ No se pudo marcar el guard del reporte diario: {e}")
    else:
        print("❌ Error al enviar a Telegram.")
    return ok


# ============================================================
#  SISTEMA 2 — ALERTAS EN TIEMPO REAL (noticias del momento)
# ============================================================

def fetch_news_sources() -> list[NewsItem]:
    """Scrapea solo las fuentes de noticias en tiempo real."""
    cfg = load_config()
    sources_cfg = cfg.get("sources", {})
    all_items: list[NewsItem] = []

    for name, cls in NEWS_SOURCES.items():
        if not sources_cfg.get(name, {}).get("enabled", True):
            continue
        try:
            src = cls()
            items = src.fetch()
            all_items.extend(items)
            _record_source_health(name, len(items))
            print(f"  📰 {src.display_name}: {len(items)} noticias")
        except Exception as e:
            _record_source_health(name, 0)
            print(f"  ⚠️ {name}: error {e}")

    return all_items


def get_sent_hash(title: str) -> str:
    """
    Firma de una noticia para saber si ya fue enviada.
    Usa la firma de tokens (no el título exacto) para que la misma noticia
    publicada por otra fuente NO se reenvíe en la siguiente ejecución.
    """
    return news_signature(title)


def _ny_today() -> str:
    """Fecha de hoy en zona horaria de Nueva York (no UTC del servidor)."""
    try:
        from dateutil import tz
        ny_now = datetime.now(tz.gettz("America/New_York"))
        return ny_now.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def _ny_date_offset(days_ago: int) -> str:
    """Fecha (YYYY-MM-DD) de hace `days_ago` días en hora de Nueva York."""
    try:
        from dateutil import tz
        from datetime import timedelta
        d = datetime.now(tz.gettz("America/New_York")) - timedelta(days=days_ago)
        return d.strftime("%Y-%m-%d")
    except Exception:
        from datetime import timedelta
        return (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def load_sent_alerts() -> set:
    """
    Carga las firmas de noticias ya enviadas (estado COMPARTIDO local+nube,
    en data/state/sent_alerts.json, rastreado por git, ventana 48h).
    """
    try:
        from .sent_state import load_sent_signatures
        return load_sent_signatures()
    except Exception:
        return set()


def save_sent_alerts(sent: set) -> None:
    """
    (Compatibilidad) El guardado real y la sincronización por git se hacen con
    sent_state.record_and_sync() al final de run_breaking_alerts. Esta función
    solo persiste localmente por si se llama desde otro sitio.
    """
    try:
        from .sent_state import record_and_sync
        record_and_sync(set(sent))
    except Exception:
        pass


# ============================================================
#  CACHE DE NOTICIAS ANALIZADAS (ahorra tokens: no re-analizar)
# ============================================================

def load_analyzed_cache() -> dict:
    """
    Cache de noticias analizadas en las últimas ~48h (hoy + ayer, hora NY).
    Devuelve {firma: analysis_dict}.
    Muchas noticias siguen "vivas" al día siguiente; con 48h no se re-analizan
    (ahorro de tokens). El cache de HOY tiene prioridad sobre el de ayer.
    """
    merged: dict = {}
    for days in (1, 0):  # ayer primero; hoy sobrescribe
        cache_file = CACHE_DIR / f"analyzed_{_ny_date_offset(days)}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    merged.update(json.load(f))
            except Exception:
                pass
    return merged


def save_analyzed_cache(cache: dict) -> None:
    """Guarda el cache de noticias analizadas."""
    today = _ny_today()
    cache_file = CACHE_DIR / f"analyzed_{today}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception:
        pass


def run_breaking_alerts(reasoning: bool = False, max_news: int = 15) -> int:
    """
    SISTEMA 2 — Procesa noticias en tiempo real.

    Optimizaciones de tokens:
      - Dedup entre fuentes ANTES del LLM (una noticia = una vez)
      - Cache de analizadas (48h): no re-analiza noticias ya procesadas
      - Análisis EN LOTE: 1 llamada por cada ~5 noticias nuevas
      - Modo solo-watchlist: solo noticias de la lista del usuario

    max_news: máximo de noticias a analizar por ejecución (las más recientes).
    Devuelve el número de alertas enviadas.
    """
    cfg = load_config()
    min_score = cfg.get("filter", {}).get("breaking_min_score", 70)
    commodity_min = cfg.get("filter", {}).get("commodity_min_score", 70)
    wl_min_score = get_watchlist_min_score()

    only_watchlist = cfg.get("watchlist", {}).get("only", False)

    # MODO CLOUD-ONLY: la nube es el único emisor de alertas. Ya no hay
    # coordinación por "heartbeat" entre PC y nube (se eliminó): al haber un
    # solo emisor no hay choques de estado ni alertas duplicadas. El estado
    # compartido (data/state) sigue evitando repeticiones entre ejecuciones.

    # Alertas de PRECIO (movimiento del día vía yfinance), independientes de las noticias
    try:
        from .price_alerts import run_price_alerts
        run_price_alerts()
    except Exception as e:
        print(f"  ⚠️ Alertas de precio: {e}")

    print("🚨 Scrapeando noticias en tiempo real (Sistema 2)...")
    items = fetch_news_sources()
    # Avisar por Telegram si alguna fuente lleva varias ejecuciones sin traer nada
    notify_unhealthy_sources()
    items = deduplicate(items)

    # Watchlist: empresas seguidas por el usuario
    wl_companies = load_watchlist()
    if wl_companies:
        wl_items = []
        other_items = []
        for item in items:
            if match_company(item):
                wl_items.append(item)
            else:
                other_items.append(item)

        if only_watchlist:
            # MODO SOLO-WATCHLIST: descartar todo lo que no sea de tu lista
            items = wl_items
            print(f"  🎯 Solo watchlist: {len(wl_items)} noticias de tu lista "
                  f"(descartadas {len(other_items)} ajenas)")
        else:
            # Modo prioridad: watchlist primero, luego el resto
            items = wl_items + other_items
            if wl_items:
                print(f"  🎯 {len(wl_items)} noticias coinciden con tu watchlist (prioridad)")

    items = items[:max_news]  # solo las más recientes (watchlist prioritarias incluidas)

    # Traer el estado compartido más reciente (en local: git pull; en la nube el
    # checkout ya lo trae) para no repetir lo que envió el otro emisor.
    try:
        from .sent_state import pull as _pull_state
        _pull_state()
    except Exception:
        pass

    sent_hashes = load_sent_alerts()
    analyzed_cache = load_analyzed_cache()
    # Conjuntos de tokens de lo ya enviado, para detectar la MISMA noticia
    # aunque venga de otra fuente con titular distinto entre ejecuciones.
    sent_token_sets = [set(sig.split()) for sig in sent_hashes]

    # PASO 1 — Candidatos: quitar ya enviadas/equivalentes y separar las que
    # ya están en cache de las que hay que analizar con el LLM.
    candidates: list[tuple] = []   # [(item, h, toks)]
    to_analyze: list[NewsItem] = []
    for item in items:
        h = get_sent_hash(item.title)
        toks = _title_tokens(item.title)
        if h in sent_hashes or any(_titles_similar(toks, prev) for prev in sent_token_sets):
            continue  # ya enviada o equivalente → saltar
        candidates.append((item, h, toks))
        if h not in analyzed_cache:
            to_analyze.append(item)

    cache_hits = len(candidates) - len(to_analyze)

    # PASO 2 — Analizar EN LOTE las nuevas (1 llamada por cada ~5 noticias,
    # en vez de 1 por noticia). Gran ahorro de tokens y de tiempo.
    llm_calls = 0
    if to_analyze:
        print(f"  🧠 Analizando {len(to_analyze)} noticias nuevas en lote...")
        batch_results = analyze_batch_breaking(to_analyze, chunk_size=5)
        llm_calls = (len(to_analyze) + 4) // 5
        for it, analysis in zip(to_analyze, batch_results):
            if analysis and isinstance(analysis, dict):
                analyzed_cache[get_sent_hash(it.title)] = analysis
        save_analyzed_cache(analyzed_cache)

    # PASO 3a — Evaluar candidatos y quedarse con los que pasan el umbral.
    #   - Empresa de watchlist → umbral reducido (55)
    #   - ETF de materia prima/apalancado (alias genéricos) → umbral estricto (anti-ruido)
    #   - Sin watchlist → umbral normal (70)
    aprobadas: list[dict] = []
    for item, h, toks in candidates:
        analysis = analyzed_cache.get(h)
        if not analysis or not isinstance(analysis, dict):
            continue

        puede_mover = analysis.get("puede_mover_mercado", False)
        confianza = analysis.get("confianza", 0)

        company = match_company(item)
        if company:
            threshold = max(wl_min_score, commodity_min) if is_noisy_etf(company.get("ticker", "")) else wl_min_score
        else:
            threshold = min_score

        if puede_mover and confianza >= threshold:
            aprobadas.append({
                "item": item, "h": h, "toks": toks, "analysis": analysis,
                "company": company, "confianza": confianza, "threshold": threshold,
            })
        else:
            print(f"  ✗ Descartada (impacto={confianza}%, umbral={threshold}, mover={puede_mover})")

    # PASO 3b — Enviar como MÁXIMO 1 alerta por ticker en esta ejecución,
    # quedándonos con la de MAYOR confianza. Evita 2 alertas del mismo activo
    # (ej. dos noticias de petróleo distintas que mapean a USO).
    aprobadas.sort(key=lambda a: -a["confianza"])
    sent_count = 0
    tickers_enviados: set = set()
    nuevas_sigs: set = set()   # firmas enviadas en esta ejecución → sincronizar al final
    for a in aprobadas:
        company = a["company"]
        ticker = company["ticker"] if company else None
        if ticker and ticker in tickers_enviados:
            print(f"  ⏭️ Omitida: ya se envió una alerta de {ticker} en esta ejecución "
                  f"({a['confianza']}%): {a['item'].title[:45]}...")
            continue

        entry = {"item": a["item"], "analysis": a["analysis"]}
        alert_text = format_breaking_alert(entry)
        tag = f" 🎯{ticker}" if ticker else ""
        print(f"  🚨 ALTO IMPACTO ({a['confianza']}%, umbral {a['threshold']}){tag} → enviando a Telegram")
        ok = send_to_telegram(alert_text)
        if ok:
            sent_count += 1
            if ticker:
                tickers_enviados.add(ticker)
            sent_hashes.add(a["h"])
            sent_token_sets.append(a["toks"])
            nuevas_sigs.add(a["h"])
            # Backup automático de la alerta enviada
            save_alert_backup(a["item"].to_dict(), a["analysis"], alert_text)

    # Sincronizar el estado COMPARTIDO una sola vez: guarda + git commit/push,
    # para que ni la nube ni el bot local repitan estas noticias.
    if nuevas_sigs:
        try:
            from .sent_state import record_and_sync
            record_and_sync(nuevas_sigs)
        except Exception as e:
            print(f"  ⚠️ Sync estado enviadas: {e}")

    print(f"\n📊 {sent_count} alertas enviadas | {llm_calls} llamadas LLM (lote) | {cache_hits} cache hits (tokens ahorrados)")
    return sent_count


# ============================================================
#  COMPATIBILIDAD — para el dashboard y pruebas
# ============================================================

def fetch_all_sources() -> list[NewsItem]:
    """Scrapea TODAS las fuentes (calendario + noticias). Para el dashboard."""
    return fetch_calendar_sources() + fetch_news_sources()


# ============================================================
#  HUELLA DE NOTICIAS (dedup entre fuentes distintas)
# ============================================================

# Palabras vacías (ES + EN) que no aportan a la identidad de la noticia.
_STOPWORDS = {
    # inglés
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "as", "at", "by", "with", "from", "that", "this", "it", "its",
    "be", "has", "have", "had", "will", "after", "over", "amid", "says", "say",
    "new", "up", "down", "not", "no", "but", "into", "out", "than", "then",
    "his", "her", "their", "amp", "via", "how", "why", "what", "when", "who",
    # español
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "y", "o",
    "en", "con", "por", "para", "que", "se", "su", "sus", "al", "lo", "como",
    "mas", "más", "sobre", "tras", "entre", "ante", "desde", "hasta",
}

# Prioridad de fuente: si la misma noticia aparece en varias webs, se conserva
# la de mayor prioridad (Bloomberg > Investing/CNBC > Yahoo > Finviz).
_SOURCE_PRIORITY = {
    "reuters": 5,             # agencia de cable: máxima prioridad
    "associated press": 5,
    "bloomberg": 4,
    "investing": 3,
    "cnbc": 3,
    "marketwatch": 3,
    "yahoo": 2,
    "finviz": 1,
}


def _source_rank(source: str) -> int:
    s = (source or "").lower()
    for key, rank in _SOURCE_PRIORITY.items():
        if key in s:
            return rank
    return 0


def _title_tokens(title: str) -> set[str]:
    """
    Extrae los tokens significativos de un titular (minúsculas, sin puntuación,
    sin palabras vacías). Sirve para comparar noticias equivalentes que vienen
    de fuentes distintas con titulares ligeramente diferentes.
    """
    t = (title or "").lower()
    t = re.sub(r"[^a-z0-9áéíóúñü ]+", " ", t)
    return {w for w in t.split() if len(w) > 2 and w not in _STOPWORDS}


def _titles_similar(tokens_a: set[str], tokens_b: set[str], threshold: float = 0.6) -> bool:
    """
    ¿Dos titulares se refieren a la misma noticia?
    Usa similitud de Jaccard entre sus tokens + regla de contención
    (si el titular más corto está casi contenido en el otro).
    """
    if not tokens_a or not tokens_b:
        return False
    inter = len(tokens_a & tokens_b)
    if inter == 0:
        return False
    union = len(tokens_a | tokens_b)
    if union and inter / union >= threshold:
        return True
    # Contención: titular corto casi contenido en el largo (ej. una fuente resume)
    smaller = min(len(tokens_a), len(tokens_b))
    if smaller and inter / smaller >= 0.8:
        return True
    return False


def news_signature(title: str) -> str:
    """
    Firma canónica de una noticia (tokens significativos ordenados, separados
    por espacio). Dos titulares idénticos en contenido producen la misma firma.
    Se guarda en el cache de enviadas para no repetir entre ejecuciones.
    """
    tokens = _title_tokens(title)
    if not tokens:
        return (title or "").lower().strip()
    return " ".join(sorted(tokens))


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """
    Quita noticias duplicadas y equivalentes (VARIANTE 2 + prioridad de fuente).

    Una misma noticia publicada por varias fuentes web (Investing, Yahoo,
    Finviz, Bloomberg) tiene titulares ligeramente distintos. Aquí se
    comparan por similitud de tokens (no por título exacto) para que cada
    noticia aparezca UNA SOLA VEZ. Cuando hay duplicado, se conserva la
    fuente de mayor prioridad (Bloomberg > Investing/CNBC > Yahoo > Finviz).
    """
    def _add_source(names: list[str], src: str) -> None:
        """Añade una fuente a la lista sin duplicar (case-insensitive)."""
        s = (src or "").strip()
        if not s:
            return
        if s.lower() not in {n.lower() for n in names}:
            names.append(s)

    kept: list[dict] = []  # {"tokens": set, "item": NewsItem, "sources": list[str]}
    for it in items:
        toks = _title_tokens(it.title)
        dup_idx = None
        for i, k in enumerate(kept):
            if _titles_similar(toks, k["tokens"]):
                dup_idx = i
                break
        if dup_idx is None:
            names: list[str] = []
            _add_source(names, it.source)
            kept.append({"tokens": toks, "item": it, "sources": names})
        else:
            # Duplicado: acumular la fuente de ESTA noticia en el grupo.
            k = kept[dup_idx]
            _add_source(k["sources"], it.source)
            if _source_rank(it.source) > _source_rank(k["item"].source):
                # Esta fuente tiene mayor prioridad → conservar su NewsItem,
                # pero mantener la lista acumulada de fuentes del grupo.
                k["tokens"] = toks
                k["item"] = it

    result: list[NewsItem] = []
    for k in kept:
        item = k["item"]
        names = list(k["sources"])
        # Asegurar que la propia fuente del item conservado esté incluida.
        _add_source(names, item.source)
        item.sources = names
        result.append(item)
    return result


def _save_history(report_text: str, entries: list[dict]) -> None:
    """Guarda el reporte en data/history/."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        json_path = HISTORY_DIR / f"report_{timestamp}.json"
        txt_path = HISTORY_DIR / f"report_{timestamp}.txt"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(
                [{"item": e["item"].to_dict(), "analysis": e["analysis"]} for e in entries],
                f, ensure_ascii=False, indent=2,
            )
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(report_text)
    except Exception as e:
        print(f"⚠️ Error guardando historial: {e}")
