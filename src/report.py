"""
Report — orquestador del pipeline.

DOS SISTEMAS SEPARADOS:

1. REPORTE DIARIO (8am): SOLO calendario económico (Forex Factory, Yahoo, Finviz).
   Eventos programados con hora fija y estrellas (IPC, Fed, BCE, NFP...).
   Se agrupan en un solo mensaje. NO usa noticias en tiempo real.

2. ALERTAS EN TIEMPO REAL: noticias que van saliendo (CNBC, Yahoo, Bloomberg, Finviz).
   NO se acumulan: cada una se envía al instante cuando aparece.
   Solo alto impacto: mega-contratos, fusiones, movimientos grandes, Trump, etc.
"""
from __future__ import annotations

import json
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
from .analyzer import analyze_batch, analyze_single
from .formatter import format_daily_report, format_breaking_alert
from .notifier import send_to_telegram
from .watchlist import match_company, get_watchlist_min_score, load_watchlist
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
    "investing": InvestingSource,
    "yahoo_finance": YahooFinanceSource,
    "finviz": FinvizSource,
    "bloomberg_rss": BloombergRSSSource,
}

# Registro completo para compatibilidad con el dashboard
ALL_SOURCES = {**CALENDAR_SOURCES, **NEWS_SOURCES}


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
            print(f"  📅 {src.display_name}: {len(items)} eventos")
        except Exception as e:
            print(f"  ⚠️ {name}: error {e}")

    return all_items


def _is_us_relevant(item: NewsItem) -> bool:
    """
    Filtro PRELIMINAR (no estricto) para el calendario macro.
    Descarta eventos claramente regionales que NO afectan al mercado americano
    (PIB de UK, tasa de Japón, inflación de la zona euro sin impacto USA).

    Las NOTICIAS en tiempo real NO se filtran aquí: el LLM decide si afectan a USA.
    Una noticia de China sobre aranceles a Apple pasaría este filtro por título,
    pero aunque no lo pase, el analyzer (LLM) tiene la última palabra.

    Esto solo evita gastar tokens del LLM en eventos obvios de otra región.
    """
    currency = (item.currency or "").upper().strip()
    country = (item.country or "").strip()

    # Eventos de USA → siempre relevantes
    if currency == "USD" or country in ("🇺🇸", "US", "USA"):
        return True

    # Fuentes de NOTICIAS en tiempo real → siempre relevantes (el LLM decide después)
    # Pero las fuentes de CALENDARIO (Forex Factory, Yahoo Calendar, Finviz Calendar) sí se filtran
    # porque traen eventos de todos los países.
    source = (item.source or "").lower()
    is_calendar_source = "calendar" in source or "forex factory" in source
    # Si no es fuente de calendario, es una noticia → pasa siempre (el LLM decide)
    if not is_calendar_source:
        if any(s in source for s in ["cnbc", "marketwatch", "yahoo", "bloomberg", "finviz"]):
            return True

    # Eventos internacionales que SUELEN afectar a USA (por título)
    title = (item.title or "").lower()
    intl_relevant = [
        "opec", "china tariff", "chinese tariff", "trade war",
        "european union", "eu regulation", "eu tech",
        "sanctions", "semiconductor", "chips",
        "brexit", "uk economy",  # a veces afecta
    ]
    if any(kw in title for kw in intl_relevant):
        return True

    # Eventos macro de otros países (UK GDP, Japan rate, EZ CPI) → descartar
    # El LLM no los verá, pero rara vez mueven la bolsa USA
    return False


def generate_daily_report(reasoning: bool = True) -> tuple[str, list[dict]]:
    """
    SISTEMA 1 — Reporte diario de eventos macro programados.
    Usa SOLO el calendario económico (Forex Factory, Yahoo, Finviz).
    Scrapea calendarios → filtra USA → filtra estrellas → analiza → formatea.

    Devuelve (texto_formateado, lista_de_entradas).
    """
    cfg = load_config()
    min_stars = cfg.get("filter", {}).get("min_stars", 2)

    print("📅 Scrapeando calendarios macro (Sistema 1)...")
    calendar_items = fetch_calendar_sources()
    calendar_items = deduplicate(calendar_items)

    # FILTRO 1 (preliminar): descartar eventos claramente regionales que no afectan a USA
    # El LLM tiene la última palabra, esto solo ahorra tokens.
    relevant_calendar = [it for it in calendar_items if _is_us_relevant(it)]
    print(f"  🇺🇸 Calendario relevante: {len(relevant_calendar)} de {len(calendar_items)} eventos")

    # FILTRO 2: eventos con estrellas (2-3) del calendario
    # Solo calendario económico. Sin relleno de noticias ni eventos de menor impacto.
    items = [it for it in relevant_calendar if it.stars >= min_stars]

    if not items:
        return "📊 No hay eventos macro de alto impacto programados hoy para el mercado americano.", []

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
    report_text = format_daily_report(entries)

    # Guardar historial + backup automático
    _save_history(report_text, entries)
    save_report_backup(report_text, entries)

    # Registrar eventos para seguimiento de resultados (Sección 1)
    # Después de que cada evento ocurra, se enviará un mensaje con los resultados reales
    track_events_from_report(entries)

    return report_text, entries


def run_and_send(reasoning: bool = True) -> bool:
    """SISTEMA 1 — Genera el reporte diario y lo envía a Telegram."""
    report_text, entries = generate_daily_report(reasoning)
    print(f"\n📊 Reporte generado ({len(report_text)} chars, {len(entries)} eventos)")

    ok = send_to_telegram(report_text)
    if ok:
        print("✅ Reporte enviado a Telegram.")
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
            print(f"  📰 {src.display_name}: {len(items)} noticias")
        except Exception as e:
            print(f"  ⚠️ {name}: error {e}")

    return all_items


def get_sent_hash(title: str) -> str:
    """Hash de una noticia para saber si ya fue enviada."""
    return hashlib.md5(title.lower().strip()[:100].encode()).hexdigest()


def _ny_today() -> str:
    """Fecha de hoy en zona horaria de Nueva York (no UTC del servidor)."""
    try:
        from dateutil import tz
        ny_now = datetime.now(tz.gettz("America/New_York"))
        return ny_now.strftime("%Y-%m-%d")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d")


def load_sent_alerts() -> set:
    """Carga las noticias ya enviadas hoy (para no repetir)."""
    today = _ny_today()
    cache_file = CACHE_DIR / f"sent_alerts_{today}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_sent_alerts(sent: set) -> None:
    """Guarda las noticias enviadas hoy."""
    today = _ny_today()
    cache_file = CACHE_DIR / f"sent_alerts_{today}.json"
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(list(sent), f)
    except Exception:
        pass


# ============================================================
#  CACHE DE NOTICIAS ANALIZADAS (ahorra tokens: no re-analizar)
# ============================================================

def load_analyzed_cache() -> dict:
    """
    Cache de TODAS las noticias analizadas hoy (no solo enviadas).
    Devuelve {hash: analysis_dict}.
    Evita re-analizar con el LLM noticias que ya fueron procesadas.
    """
    today = _ny_today()
    cache_file = CACHE_DIR / f"analyzed_{today}.json"
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


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
    Cada noticia NUEVA se analiza individualmente:
      - Si es de alto impacto → se envía AL INSTANTE a Telegram
      - Si no → se descarta (no se acumula)

    Optimizaciones de tokens:
      - Cache de analizadas: no re-analiza noticias ya procesadas hoy
      - Watchlist: empresas seguidas tienen umbral reducido (55 vs 70)
      - Prioridad: noticias de empresas en watchlist se analizan primero

    max_news: máximo de noticias a analizar por ejecución (las más recientes).
    Devuelve el número de alertas enviadas.
    """
    cfg = load_config()
    min_score = cfg.get("filter", {}).get("breaking_min_score", 70)
    wl_min_score = get_watchlist_min_score()

    print("🚨 Scrapeando noticias en tiempo real (Sistema 2)...")
    items = fetch_news_sources()
    items = deduplicate(items)

    # Priorizar: noticias que mencionan empresas de la watchlist van primero
    wl_companies = load_watchlist()
    if wl_companies:
        wl_items = []
        other_items = []
        for item in items:
            if match_company(item):
                wl_items.append(item)
            else:
                other_items.append(item)
        # Watchlist primero, luego el resto
        items = wl_items + other_items
        if wl_items:
            print(f"  🎯 {len(wl_items)} noticias coinciden con tu watchlist (prioridad)")

    items = items[:max_news]  # solo las más recientes (watchlist prioritarias incluidas)

    sent_hashes = load_sent_alerts()
    analyzed_cache = load_analyzed_cache()
    sent_count = 0
    cache_hits = 0
    llm_calls = 0

    for item in items:
        h = get_sent_hash(item.title)
        if h in sent_hashes:
            continue  # ya enviada, saltar

        # ¿Ya analizada hoy? → usar cache, NO llamar al LLM
        if h in analyzed_cache:
            analysis = analyzed_cache[h]
            cache_hits += 1
            print(f"  ♻️ Cache (sin gastar tokens): {item.title[:45]}...")
        else:
            # Analizar individualmente con LLM
            company = match_company(item)
            tag = f" 🎯{company['ticker']}" if company else ""
            print(f"  🔍 Analizando: {item.title[:45]}...{tag}")
            analysis = analyze_single(item, reasoning=False)
            llm_calls += 1

            if not analysis or not isinstance(analysis, dict):
                continue

            # Guardar en cache para no re-analizar después
            analyzed_cache[h] = analysis
            save_analyzed_cache(analyzed_cache)

        # Filtro: ¿puede mover el mercado Y tiene confianza suficiente?
        puede_mover = analysis.get("puede_mover_mercado", False)
        confianza = analysis.get("confianza", 0)

        # Umbral dinámico: empresas en watchlist tienen umbral más bajo
        company = match_company(item)
        threshold = wl_min_score if company else min_score

        if puede_mover and confianza >= threshold:
            # ¡ALERTA! Enviar al instante
            entry = {"item": item, "analysis": analysis}
            alert_text = format_breaking_alert(entry)

            tag = f" 🎯{company['ticker']}" if company else ""
            print(f"  🚨 ALTO IMPACTO ({confianza}%, umbral {threshold}){tag} → enviando a Telegram")
            ok = send_to_telegram(alert_text)
            if ok:
                sent_count += 1
                sent_hashes.add(h)
                save_sent_alerts(sent_hashes)
                # Backup automático de la alerta enviada
                save_alert_backup(item.to_dict(), analysis, alert_text)
        else:
            print(f"  ✗ Descartada (impacto={confianza}%, umbral={threshold}, mover={puede_mover})")

    print(f"\n📊 {sent_count} alertas enviadas | {llm_calls} llamadas LLM | {cache_hits} cache hits (tokens ahorrados)")
    return sent_count


# ============================================================
#  COMPATIBILIDAD — para el dashboard y pruebas
# ============================================================

def fetch_all_sources() -> list[NewsItem]:
    """Scrapea TODAS las fuentes (calendario + noticias). Para el dashboard."""
    return fetch_calendar_sources() + fetch_news_sources()


def deduplicate(items: list[NewsItem]) -> list[NewsItem]:
    """Quita noticias duplicadas por título similar."""
    seen = set()
    unique = []
    for it in items:
        key = it.title.lower().strip()[:80]
        if key not in seen:
            seen.add(key)
            unique.append(it)
    return unique


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
