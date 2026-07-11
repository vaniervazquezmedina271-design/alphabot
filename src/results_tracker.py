"""
Results Tracker — Seguimiento de resultados para la Sección 1.

¿Cómo funciona?
1. Cuando el Sistema 1 envía el reporte diario (7-8 AM), guarda cada evento
   programado en un archivo de tracking (data/cache/tracked_events_DATE.json).
2. Cuando el Sistema 2 corre (cada hora), revisa si algún evento programado
   ya ocurrió (la hora del evento ya pasó) y si ya hay resultados reales.
3. Para cada evento con resultados nuevos:
   a. Re-scrapea la fuente del calendario para obtener el valor "actual".
   b. Re-analiza con el LLM usando los datos reales.
   c. Envía un mensaje de seguimiento a Telegram con el resultado real +
      nuevo análisis (beat/miss/in-line + impacto real).
   d. Marca el evento como "seguido" para no repetir.

Esto cumple lo que pidió el usuario:
"después de que se dé cada noticia programada, en ese mismo momento que den
la noticia y se vean los resultados, vuelvas y me digas para cada noticia
que habías mandado lo mismo pero con los resultados dados ya y hagas el
mismo análisis en cada una de ellas."
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from dateutil import tz

from .config import CACHE_DIR
from .sources.base import NewsItem


_NY_TZ = tz.gettz("America/New_York")


def _ny_now():
    return datetime.now(_NY_TZ)


def _ny_today() -> str:
    return _ny_now().strftime("%Y-%m-%d")


def _tracked_file() -> Path:
    """Archivo de eventos tracked para hoy."""
    return CACHE_DIR / f"tracked_events_{_ny_today()}.json"


def load_tracked_events() -> list[dict]:
    """
    Carga los eventos programados que se enviaron en el reporte diario.
    Cada evento tiene:
      - hash: identificador único
      - title: título del evento
      - time: hora programada (ej. "14:00")
      - source: fuente del calendario
      - url: URL de la fuente
      - forecast: valor esperado
      - previous: valor anterior
      - analysis_original: análisis que se envió en la mañana
      - followed: False si aún no se ha enviado el seguimiento
    """
    f = _tracked_file()
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return []
    return []


def save_tracked_events(events: list[dict]) -> None:
    """Guarda la lista de eventos tracked."""
    f = _tracked_file()
    try:
        with open(f, "w", encoding="utf-8") as fh:
            json.dump(events, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def track_events_from_report(entries: list[dict]) -> int:
    """
    Guarda los eventos del reporte diario para hacer seguimiento después.
    Se llama después de enviar el reporte de la mañana.

    entries: lista de {"item": NewsItem, "analysis": dict}
    Devuelve cuántos eventos se registraron para tracking.
    """
    existing = load_tracked_events()
    existing_hashes = {e["hash"] for e in existing}

    count = 0
    for entry in entries:
        item: NewsItem = entry["item"]
        analysis = entry["analysis"]

        # Hash único para el evento
        from .report import get_sent_hash
        h = get_sent_hash(item.title)

        if h in existing_hashes:
            continue  # ya está tracked

        tracked = {
            "hash": h,
            "title": item.title,
            "time": item.time or "",
            "source": item.source or "",
            "url": item.url or "",
            "country": item.country or "",
            "currency": item.currency or "",
            "forecast": item.forecast or "",
            "previous": item.previous or "",
            "actual": item.actual or "",
            "stars": analysis.get("stars", item.stars or 2),
            "analysis_original": analysis,
            "followed": False,
            "tracked_at": _ny_now().strftime("%Y-%m-%d %H:%M"),
        }
        existing.append(tracked)
        count += 1

    if count > 0:
        save_tracked_events(existing)
        print(f"  📌 {count} eventos registrados para seguimiento de resultados")

    return count


def _parse_time_to_minutes(time_str: str) -> Optional[int]:
    """Convierte '14:00' o '14:00 ET' a minutos desde medianoche (840)."""
    if not time_str:
        return None
    import re
    m = re.search(r"(\d{1,2}):(\d{2})", str(time_str))
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _event_has_passed(event: dict) -> bool:
    """¿La hora del evento ya pasó (en NY)?"""
    event_minutes = _parse_time_to_minutes(event.get("time", ""))
    if event_minutes is None:
        # Si no podemos parsear la hora, asumir que ya pasó
        # (mejor revisar que perder un resultado)
        return True

    ny = _ny_now()
    now_minutes = ny.hour * 60 + ny.minute

    # Dar un margen de 15 minutos después de la hora del evento
    # para que el resultado esté disponible
    return now_minutes >= event_minutes + 15


def check_pending_results() -> list[dict]:
    """
    Revisa qué eventos tracked ya pasaron su hora y NO tienen seguimiento enviado.

    Devuelve lista de eventos pendientes de seguimiento.
    """
    events = load_tracked_events()
    pending = []

    for event in events:
        if event.get("followed"):
            continue  # ya se envió el seguimiento
        if not _event_has_passed(event):
            continue  # el evento aún no ocurre

        pending.append(event)

    return pending


def fetch_actual_results(event: dict) -> Optional[str]:
    """
    Re-scrapea las fuentes del calendario para buscar el valor "actual"
    del evento. Compara por título.

    Devuelve el valor actual si lo encuentra, o None.
    """
    from .report import fetch_calendar_sources, deduplicate

    try:
        items = fetch_calendar_sources()
        items = deduplicate(items)

        event_title_lower = event.get("title", "").lower().strip()

        for item in items:
            if item.title.lower().strip() == event_title_lower:
                if item.actual and item.actual.strip():
                    return item.actual.strip()
                break  # encontramos el evento pero sin actual todavía
    except Exception as e:
        print(f"  ⚠️ Error buscando resultados reales: {e}")

    return None


def reanalyze_with_results(event: dict, actual_value: str) -> Optional[dict]:
    """
    Re-analiza el evento con el resultado real usando el LLM.
    Devuelve el nuevo análisis o None.
    """
    from .analyzer import analyze_single

    # Construir un NewsItem con el resultado real
    item = NewsItem(
        title=event.get("title", ""),
        url=event.get("url", ""),
        source=event.get("source", ""),
        time=event.get("time", ""),
        stars=event.get("stars", 2),
        country=event.get("country", ""),
        currency=event.get("currency", ""),
        forecast=event.get("forecast", ""),
        previous=event.get("previous", ""),
        actual=actual_value,
        summary=f"Resultado real: {actual_value}. Forecast era: {event.get('forecast', 'N/A')}. "
                f"Valor anterior: {event.get('previous', 'N/A')}.",
    )

    try:
        analysis = analyze_single(item, reasoning=False)
        if analysis and isinstance(analysis, dict):
            return analysis
    except Exception as e:
        print(f"  ⚠️ Error re-analizando: {e}")

    return None


def mark_event_followed(event_hash: str, actual_value: str, new_analysis: dict) -> None:
    """Marca un evento como seguido (seguimiento ya enviado)."""
    events = load_tracked_events()
    for event in events:
        if event["hash"] == event_hash:
            event["followed"] = True
            event["actual"] = actual_value
            event["analysis_real"] = new_analysis
            event["followed_at"] = _ny_now().strftime("%Y-%m-%d %H:%M")
            break
    save_tracked_events(events)


def run_results_tracking() -> int:
    """
    Ejecuta el seguimiento de resultados para la Sección 1.

    1. Carga eventos tracked del día.
    2. Filtra los que ya pasaron pero no tienen seguimiento.
    3. Busca resultados reales en las fuentes del calendario.
    4. Si hay resultado real → re-analiza con LLM → envía a Telegram.
    5. Marca como seguido.

    Devuelve cuántos seguimientos se enviaron.
    """
    from .formatter import format_results_followup
    from .notifier import send_to_telegram
    from .backup import save_alert_backup
    from .sources.base import NewsItem

    pending = check_pending_results()

    if not pending:
        return 0

    print(f"📊 Seguimiento de resultados: {len(pending)} evento(s) pendiente(s)")

    sent_count = 0
    for event in pending:
        print(f"  🔍 Buscando resultados reales: {event['title'][:50]}...")

        # Buscar valor real
        actual = fetch_actual_results(event)

        if not actual:
            print(f"     ⏳ Resultado aún no disponible")
            continue

        print(f"     ✅ Resultado encontrado: {actual}")

        # Re-analizar con datos reales
        new_analysis = reanalyze_with_results(event, actual)

        if not new_analysis:
            print(f"     ⚠️ No se pudo re-analizar")
            continue

        # Construir entry para el formatter
        item = NewsItem(
            title=event.get("title", ""),
            url=event.get("url", ""),
            source=event.get("source", ""),
            time=event.get("time", ""),
            stars=event.get("stars", 2),
            country=event.get("country", ""),
            currency=event.get("currency", ""),
            forecast=event.get("forecast", ""),
            previous=event.get("previous", ""),
            actual=actual,
        )
        entry = {"item": item, "analysis": event.get("analysis_original", {})}
        results = {"actual": actual, "analisis_real": new_analysis}

        # Formatear y enviar
        followup_text = format_results_followup(entry, results)

        print(f"  📤 Enviando seguimiento a Telegram...")
        ok = send_to_telegram(followup_text, parse_mode="HTML")

        if ok:
            sent_count += 1
            mark_event_followed(event["hash"], actual, new_analysis)

            # Backup del seguimiento
            save_alert_backup(
                {"title": event["title"], "actual": actual, "event": event},
                new_analysis,
                followup_text,
            )
            print(f"     ✅ Seguimiento enviado")

    return sent_count
