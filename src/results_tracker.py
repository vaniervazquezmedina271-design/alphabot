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
import os
import re
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dateutil import tz

from .config import CACHE_DIR
from .sources.base import NewsItem


_NY_TZ = tz.gettz("America/New_York")

# ============================================================
#  DETECCIÓN DE EVENTOS DE DISCURSO / COMPARECENCIA (PARTE A)
# ============================================================

# Palabras clave (en inglés, como vienen del calendario) que identifican un
# evento de DISCURSO/COMPARECENCIA sin resultado numérico. Se comparan sin
# distinguir acentos ni mayúsculas.
_SPEECH_KEYWORDS = (
    "speech", "speaks", "testimony", "testifies", "testify",
    "remarks", "statement",
)

# Palabras que NO aportan al "tema" del discurso al filtrar titulares.
_SPEECH_STOP = {
    "speech", "speaks", "testimony", "testifies", "testify", "remarks",
    "statement", "and", "the", "for", "chair", "member", "day", "gov",
}


def _strip_accents(text: str) -> str:
    """Quita acentos/diacríticos para comparar sin distinguirlos."""
    try:
        return "".join(
            c for c in unicodedata.normalize("NFD", str(text))
            if unicodedata.category(c) != "Mn"
        )
    except Exception:
        return str(text)


def _is_numeric_value(value) -> bool:
    """¿El valor contiene algún dígito? (forecast/actual numérico)."""
    if value is None:
        return False
    return bool(re.search(r"\d", str(value)))


def _is_speech_event(event: dict) -> bool:
    """
    True si el evento es de DISCURSO/COMPARECENCIA (su "resultado" es la
    reacción del mercado, no un número BEAT/MISS):

    - El nombre (event/title) contiene una palabra clave de discurso
      (sin distinguir acentos/mayúsculas), O
    - El evento NO tiene pronóstico numérico (forecast vacío o no numérico).

    Un evento numérico normal (con forecast numérico y sin palabras clave)
    devuelve False y sigue por el flujo BEAT/MISS existente.
    """
    name = _strip_accents(event.get("title", "")).lower()
    if any(kw in name for kw in _SPEECH_KEYWORDS):
        return True
    if not _is_numeric_value(event.get("forecast", "")):
        return True
    return False


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
        if _is_speech_event(event):
            continue  # los discursos se manejan aparte (run_speech_tracking)
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
    Ejecuta TODO el seguimiento de la Sección 1:
      1. Eventos NUMÉRICOS → flujo BEAT/MISS con datos reales (_run_numeric_tracking).
      2. Eventos de DISCURSO/COMPARECENCIA → reacción del mercado periódica +
         cierre al vencer la ventana (run_speech_tracking).

    Devuelve el total de mensajes de seguimiento enviados.
    """
    total = 0
    try:
        total += _run_numeric_tracking()
    except Exception as e:
        print(f"  ⚠️ Seguimiento numérico error: {e}")
    try:
        total += run_speech_tracking()
    except Exception as e:
        print(f"  ⚠️ Seguimiento de discursos error: {e}")
    return total


def _run_numeric_tracking() -> int:
    """
    Seguimiento de eventos NUMÉRICOS de la Sección 1 (flujo BEAT/MISS original).

    1. Carga eventos tracked del día (excluye discursos, ver check_pending_results).
    2. Filtra los que ya pasaron pero no tienen seguimiento.
    3. Busca resultados reales en las fuentes del calendario.
    4. Si hay resultado real → re-analiza con LLM → envía a Telegram.
    5. Marca como seguido.

    Devuelve cuántos seguimientos se enviaron.
    """
    from .formatter import format_results_followup, format_results_followup_group
    from .notifier import send_to_telegram
    from .backup import save_alert_backup
    from .sources.base import NewsItem

    pending = check_pending_results()

    if not pending:
        return 0

    print(f"📊 Seguimiento de resultados: {len(pending)} evento(s) pendiente(s)")

    # ============================================================
    #  PASO 1 — Recolectar TODOS los seguimientos LISTOS de esta corrida
    #  (los que ya tienen valor "actual" disponible y se re-analizaron).
    #  NO se envía nada todavía: primero se junta todo para decidir si va
    #  agrupado (1 solo mensaje) o individual.
    # ============================================================
    ready: list[dict] = []
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

        ready.append({
            "event": event,
            "actual": actual,
            "new_analysis": new_analysis,
            "entry": entry,
            "results": results,
        })

    if not ready:
        return 0

    # ============================================================
    #  PASO 2 — Enviar. Con MÁS DE 2 (>=3) resultados listos → UN solo
    #  mensaje consolidado, cada evento en su propio <blockquote expandable>
    #  y un único footer. Con 2 → también agrupados. Con 1 → mensaje individual.
    # ============================================================
    sent_count = 0

    def _mark_and_backup(r: dict, followup_text: str) -> None:
        """Marca como seguido y guarda backup por evento (no perder respaldo)."""
        mark_event_followed(r["event"]["hash"], r["actual"], r["new_analysis"])
        save_alert_backup(
            {"title": r["event"]["title"], "actual": r["actual"], "event": r["event"]},
            r["new_analysis"],
            followup_text,
        )

    if len(ready) >= 2:
        # Consolidado: un solo mensaje con todos los desplegables
        group_payload = [{"entry": r["entry"], "results": r["results"]} for r in ready]
        followup_text = format_results_followup_group(group_payload)

        print(f"  📤 Enviando seguimiento CONSOLIDADO ({len(ready)} eventos) a Telegram...")
        ok = send_to_telegram(followup_text, parse_mode="HTML")

        if ok:
            for r in ready:
                sent_count += 1
                _mark_and_backup(r, followup_text)
            print(f"     ✅ {sent_count} seguimientos enviados en un solo mensaje")
    else:
        # Un solo evento → mensaje individual (comportamiento previo)
        r = ready[0]
        followup_text = format_results_followup(r["entry"], r["results"])

        print(f"  📤 Enviando seguimiento a Telegram...")
        ok = send_to_telegram(followup_text, parse_mode="HTML")

        if ok:
            sent_count += 1
            _mark_and_backup(r, followup_text)
            print(f"     ✅ Seguimiento enviado")

    return sent_count


# ============================================================
#  SEGUIMIENTO DE DISCURSOS / COMPARECENCIAS (PARTE C)
#  Opción 3: seguimiento periódico durante el discurso + cierre.
# ============================================================

def _speech_config() -> tuple[float, float, float]:
    """
    Configuración del seguimiento de discursos, con prioridad env > config.yaml
    > default:
      - SPEECH_WINDOW_MIN  (ventana del discurso, min)      default 120
      - SPEECH_UPDATE_MIN  (cadencia entre actualizaciones)  default 30
      - SPEECH_MIN_MOVE_PCT(movimiento mínimo para reportar) default 0.15
    """
    window, update, min_move = 120.0, 30.0, 0.15

    # config.yaml (sección "speech")
    try:
        from .config import load_config
        cfg = load_config().get("speech", {}) or {}
        window = float(cfg.get("window_min", window))
        update = float(cfg.get("update_min", update))
        min_move = float(cfg.get("min_move_pct", min_move))
    except Exception:
        pass

    # env (prioritario)
    def _env_f(name: str, cur: float) -> float:
        v = os.environ.get(name)
        if v is None:
            return cur
        try:
            return float(v)
        except (ValueError, TypeError):
            return cur

    window = _env_f("SPEECH_WINDOW_MIN", window)
    update = _env_f("SPEECH_UPDATE_MIN", update)
    min_move = _env_f("SPEECH_MIN_MOVE_PCT", min_move)
    return window, update, min_move


def _event_start_dt(event: dict) -> datetime:
    """Datetime NY de inicio del discurso (hoy + hora del evento)."""
    minutes = _parse_time_to_minutes(event.get("time", ""))
    ny = _ny_now()
    if minutes is None:
        return ny  # sin hora parseable → asumir "ahora"
    return ny.replace(hour=minutes // 60, minute=minutes % 60, second=0, microsecond=0)


def _parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parsea un timestamp ISO guardado; devuelve datetime tz-aware NY o None."""
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=_NY_TZ)
        return d
    except Exception:
        return None


def _fetch_speech_headlines(event: dict, max_items: int = 4) -> list[dict]:
    """
    Reúne titulares relevantes al discurso reutilizando las fuentes del
    Sistema 2 (fetch_news_sources) y filtra por ponente/tema (nombre del
    evento + genéricos de bancos centrales). Devuelve [{"title","url","source"}].
    """
    try:
        from .report import fetch_news_sources, deduplicate
        items = deduplicate(fetch_news_sources())
    except Exception as e:
        print(f"  ⚠️ No se pudieron traer titulares del discurso: {e}")
        return []

    name = _strip_accents(event.get("title", "")).lower()
    kws: set[str] = set()
    for w in re.split(r"[^a-z0-9]+", name):
        if len(w) > 3 and w not in _SPEECH_STOP:
            kws.add(w)
    # Genéricos de política monetaria / bancos centrales
    kws |= {
        "fed", "fomc", "powell", "rate", "rates", "inflation", "interest",
        "monetary", "hawkish", "dovish", "tapering", "treasury", "yellen",
        "warsh",
    }

    # DEDUP CRUZADA con el Sistema 2: excluir titulares cuyo hash/firma ya esté
    # en el estado COMPARTIDO de alertas enviadas (misma función de hashing que
    # usa sent_state), para NO re-mencionar lo que el Sistema 2 ya alertó.
    try:
        from .report import get_sent_hash
        from .sent_state import load_sent_signatures
        sent_sigs = load_sent_signatures()
    except Exception:
        get_sent_hash = None
        sent_sigs = set()

    scored: list[tuple[int, dict]] = []
    for it in items:
        title = it.title or ""
        # Saltar los ya alertados por el Sistema 2 (dedup cruzada).
        if get_sent_hash is not None and sent_sigs:
            try:
                if get_sent_hash(title) in sent_sigs:
                    continue
            except Exception:
                pass
        low = _strip_accents(title).lower()
        score = sum(1 for k in kws if k in low)
        if score > 0:
            scored.append((score, {
                "title": title,
                "url": it.url or "",
                "source": it.source or "",
            }))
    scored.sort(key=lambda x: -x[0])
    return [h for _s, h in scored[:max_items]]


def _analyze_speech_segment(event: dict, reaction: dict,
                            headlines: list[dict]) -> Optional[dict]:
    """
    UNA llamada al LLM para resumir el tramo del discurso:
      (a) resumen 1-2 frases de lo que se dijo (de los titulares)
      (b) dirección de la reacción (positiva/negativa/mixta) coherente con ETFs
      (c) estrellas 1-5 de magnitud
      (d) breve porqué
    Devuelve dict parseado con {"resumen","direccion","stars","porque"} o None.
    """
    from .llm import chat
    from .analyzer import _parse_json, SYSTEM_ANALYZER

    etf_lines = []
    for _t, d in (reaction.get("etfs") or {}).items():
        if d.get("ok") and d.get("pct") is not None:
            etf_lines.append(f"{d['name']}: {d['pct']:+.2f}%")
    etf_str = "; ".join(etf_lines) or "sin datos de ETFs"
    titulares = "\n".join(f"- {h['title']}" for h in (headlines or [])) or "(sin titulares nuevos)"

    prompt = (
        "Un ponente de la Fed / banco central está dando un discurso o "
        "comparecencia. NO hay un número BEAT/MISS: el resultado es la REACCIÓN "
        "del mercado a lo que dijo. Con los titulares del tramo y el movimiento "
        "de los ETFs, devuelve SOLO un JSON:\n"
        "```json\n"
        '{"resumen": "1-2 frases de lo que se dijo en este tramo", '
        '"direccion": "positiva|negativa|mixta", '
        '"stars": 1-5, '
        '"porque": "1 frase de por qué el mercado reacciona así"}\n'
        "```\n\n"
        f"Evento: {event.get('title', '')}\n"
        f"Reacción de ETFs desde el inicio del discurso: {etf_str}\n"
        f"Sesgo agregado: {reaction.get('bias', 'neutral')}\n"
        f"Titulares del tramo:\n{titulares}"
    )
    try:
        resp = chat(
            [{"role": "system", "content": SYSTEM_ANALYZER},
             {"role": "user", "content": prompt}],
            reasoning=False,
            max_tokens=600,
        )
        parsed = _parse_json(resp)
        if isinstance(parsed, dict):
            return parsed
    except Exception as e:
        print(f"  ⚠️ Error analizando tramo del discurso: {e}")
    return None


def _process_speech_update(event: dict, start: datetime, min_move_pct: float) -> str:
    """
    Procesa UN tramo del discurso. Devuelve "sent" | "skipped".

    AHORRO DE TOKENS: si el movimiento máximo absoluto de los 4 ETFs es
    < min_move_pct Y no hay titular nuevo relevante → NO llama al LLM ni envía.
    """
    from .market_reaction import etf_reaction_since
    from .formatter import format_speech_update
    from .notifier import send_to_telegram
    from .backup import save_alert_backup

    reaction = etf_reaction_since(start)
    max_move = reaction.get("max_abs_move", 0.0)

    headlines = _fetch_speech_headlines(event)
    prev_titles = set(event.get("speech_seen_titles", []))
    new_headlines = [h for h in headlines if h["title"] not in prev_titles]

    # GIRO por tramo: % actual menos % de la actualización anterior (prev_reaction)
    # para cada ETF. Refleja hacia dónde se movió DESDE la última actualización
    # (el mercado puede irse a favor o en contra durante el discurso).
    prev_reaction = event.get("prev_reaction") or {}
    giro: dict[str, float] = {}
    cur_pcts: dict[str, float] = {}
    for tk, d in (reaction.get("etfs") or {}).items():
        if d.get("ok") and d.get("pct") is not None:
            cur_pcts[tk] = d["pct"]
            if tk in prev_reaction and prev_reaction[tk] is not None:
                giro[tk] = d["pct"] - prev_reaction[tk]

    # Ahorro de tokens: poco movimiento y sin titulares nuevos → saltar tramo.
    # Igual se actualiza prev_reaction (y el caller actualiza last_speech_update_at).
    if max_move < min_move_pct and not new_headlines:
        print(f"     ⏭️ Discurso sin novedad (máx {max_move:.2f}% < {min_move_pct}%, sin titulares) → salto")
        if cur_pcts:
            event["prev_reaction"] = cur_pcts
        return "skipped"

    analysis = _analyze_speech_segment(event, reaction, new_headlines or headlines)

    update_num = int(event.get("speech_updates_sent", 0)) + 1
    mins_in = max(0, int((_ny_now() - start).total_seconds() / 60.0))
    text = format_speech_update(
        event, reaction, analysis, new_headlines or headlines,
        update_num, mins_in, giro=giro,
    )

    ok = send_to_telegram(text, parse_mode="HTML")
    if not ok:
        return "skipped"

    # Guardar la reacción actual como prev_reaction para calcular el próximo giro.
    event["prev_reaction"] = cur_pcts
    # Recordar titulares vistos (limitado) para no repetir "novedad".
    seen = list(prev_titles | {h["title"] for h in headlines})
    event["speech_seen_titles"] = seen[-40:]
    try:
        save_alert_backup(
            {"title": event.get("title"), "speech": True, "event": event},
            analysis or {}, text,
        )
    except Exception:
        pass
    return "sent"


def _send_speech_close(event: dict, start: datetime, window_end: datetime) -> bool:
    """Envía el resumen de CIERRE con el movimiento NETO (inicio→fin) de los ETFs."""
    from .market_reaction import etf_reaction_since
    from .formatter import format_speech_close
    from .notifier import send_to_telegram
    from .backup import save_alert_backup

    reaction = etf_reaction_since(start)
    analysis = _analyze_speech_segment(event, reaction, _fetch_speech_headlines(event))
    text = format_speech_close(event, reaction, analysis)

    ok = send_to_telegram(text, parse_mode="HTML")
    if ok:
        try:
            save_alert_backup(
                {"title": event.get("title"), "speech_close": True, "event": event},
                analysis or {}, text,
            )
        except Exception:
            pass
    return ok


def run_speech_tracking() -> int:
    """
    Seguimiento periódico de eventos de DISCURSO/COMPARECENCIA (Opción 3).

    Para cada discurso tracked NO cerrado:
      - Ventana activa: desde la hora del evento hasta SPEECH_WINDOW_MIN después.
      - Cadencia: una actualización como mucho cada SPEECH_UPDATE_MIN.
      - Estado por-evento (en el propio tracked_events): last_speech_update_at,
        speech_updates_sent, speech_closed, speech_seen_titles.
      - Al vencer la ventana → mensaje de CIERRE (una sola vez) + speech_closed.

    Devuelve cuántos mensajes (actualizaciones + cierres) se enviaron.
    """
    events = load_tracked_events()
    speeches = [e for e in events if _is_speech_event(e)]
    if not speeches:
        return 0

    window_min, update_min, min_move_pct = _speech_config()
    now = _ny_now()
    sent = 0
    changed = False

    for event in speeches:
        if event.get("speech_closed"):
            continue

        start = _event_start_dt(event)
        if now < start:
            continue  # el discurso aún no empieza

        window_end = start + timedelta(minutes=window_min)

        # ¿Venció la ventana? → CIERRE (una sola vez)
        if now >= window_end:
            print(f"  🎙️ Cierre de discurso: {event.get('title', '')[:50]}")
            try:
                if _send_speech_close(event, start, window_end):
                    sent += 1
            except Exception as e:
                print(f"     ⚠️ Error en cierre de discurso: {e}")
            # Marcar cerrado pase lo que pase (no reintentar cada 10 min).
            event["speech_closed"] = True
            event["speech_closed_at"] = now.isoformat()
            changed = True
            continue

        # ¿Toca actualización periódica? (cadencia SPEECH_UPDATE_MIN)
        last_update = _parse_iso(event.get("last_speech_update_at"))
        if last_update is not None:
            mins_since = (now - last_update).total_seconds() / 60.0
            if mins_since < update_min:
                continue  # aún no toca (evita reenvíos del bot local cada ~10 min)

        print(f"  🎙️ Discurso activo: {event.get('title', '')[:50]} (min +{int((now - start).total_seconds() / 60)})")
        try:
            result = _process_speech_update(event, start, min_move_pct)
        except Exception as e:
            print(f"     ⚠️ Error en tramo del discurso: {e}")
            result = "skipped"

        # SIEMPRE registrar el intento para respetar la cadencia (aunque se salte).
        event["last_speech_update_at"] = now.isoformat()
        changed = True
        if result == "sent":
            event["speech_updates_sent"] = int(event.get("speech_updates_sent", 0)) + 1
            sent += 1

    if changed:
        save_tracked_events(events)

    return sent
