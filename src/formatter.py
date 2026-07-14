"""
Formatter — genera los mensajes de Telegram en formato HTML.

DOS SECCIONES:

1. SECTOR ECONÓMICO DEL DÍA (Sistema 1 — reporte diario)
   - Encabezado con día + fecha
   - Cada noticia: número, estrellas (DEL CALENDARIO WEB, no inventadas), título, meta
   - Detalle colapsable con <blockquote expandable>: resumen + análisis + activos + enlace
   - Solo 2+ estrellas (según el calendario)
   - Footer: AlphaBot + saludo según hora

2. ÚLTIMO MINUTO (Sistema 2 — alertas en tiempo real)
   - Encabezado con día + fecha
   - Estrellas 1-5 direccionales (positivas: más=mejor; negativas: más=más grave)
   - Detalle colapsable con <blockquote expandable>: resumen + análisis + activos + enlace
   - Footer: AlphaBot + saludo según hora

3. SEGUIMIENTO DE RESULTADOS (Sección 1 — actualización con datos reales)
   - Datos: Forecast vs Anterior vs Actual + BEAT/MISS/EN LÍNEA
   - Detalle colapsable con <blockquote expandable>: análisis + activos + reacción
   - Footer: AlphaBot + saludo según hora

Usa parse_mode=HTML en Telegram (no Markdown) para soportar <blockquote expandable>.
"""
from __future__ import annotations

import html
from datetime import datetime

from dateutil import tz

from .sources.base import NewsItem

# Zona horaria de Nueva York para fechas consistentes
_NY_TZ = tz.gettz("America/New_York")

# Etiquetas de sentimiento con emoji
SENT_EMOJI = {
    "positivo": "🟢",
    "negativo": "📉",
    "negativo_bajista": "🔴",
    "neutral": "➡️",
    "volatil": "⚠️",
}

SENT_LABEL = {
    "positivo": "🟢 Positivo",
    "negativo": "🔴 Negativo",
    "negativo_bajista": "🔴 Negativo",
    "neutral": "➡️ Neutral",
    "volatil": "⚠️ Volátil",
}

SEPARATOR = "━━━━━━━━━━━━━━━━━━━━"

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def _esc(text) -> str:
    """Escapa texto para HTML de Telegram."""
    if not text:
        return ""
    return html.escape(str(text), quote=False)


def _ny_now():
    """Hora actual en Nueva York."""
    return datetime.now(_NY_TZ)


def _stars_str(stars: int) -> str:
    """Genera la cadena de estrellas."""
    stars = max(0, min(5, stars))
    return "⭐" * stars


def _saludo() -> str:
    """Genera el saludo según la hora de Nueva York."""
    hora = _ny_now().hour
    if 5 <= hora < 12:
        return "buen día"
    elif 12 <= hora < 19:
        return "buenas tardes"
    else:
        return "buenas noches"


def _footer() -> str:
    """Footer estándar: AlphaBot + saludo según la hora."""
    return f"🤖 AlphaBot · {_saludo()}"


def format_daily_report(entries: list[dict], report_time: str = None) -> str:
    """
    SECCIÓN 1 — Formatea el reporte diario completo para Telegram.

    Usa <blockquote expandable> para que cada noticia se vea colapsada
    por defecto (titular visible, detalle plegable con "Mostrar más").

    Las estrellas vienen DEL CALENDARIO WEB (item.stars), no las inventa el LLM.

    entries: lista de dicts con {"item": NewsItem, "analysis": dict}
    report_time: hora del reporte (por defecto la actual)
    """
    if not entries:
        return "📊 No hay eventos de alto impacto hoy."

    ny = _ny_now()
    dia = DIAS[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")

    lines = [
        "📊 <b>SECTOR ECONÓMICO DEL DÍA</b>",
        f"{dia} {fecha}",
        SEPARATOR,
    ]

    for i, entry in enumerate(entries, 1):
        lines.append(_format_news_collapsible(i, entry["item"], entry["analysis"]))
        lines.append(SEPARATOR)

    # Conteo
    high = sum(1 for e in entries if e["item"].stars >= 3)
    total = len(entries)
    lines.append(f"{high} de alto impacto · {total} eventos")
    lines.append(_footer())

    text = "\n".join(lines)

    # Telegram tiene límite de 4096 chars
    if len(text) > 4000:
        text = text[:3950] + "\n... (truncado)"

    return text


def format_breaking_alert(entry: dict, alert_time: str = None) -> str:
    """
    SECCIÓN 2 — Formatea una alerta de última hora (Modelo A).

    Estructura:
    - Encabezado + día + fecha (siempre visible)
    - Estrellas 1-5 + título (siempre visible)
    - Meta: fuente + hora + bandera + sentimiento + confianza% (siempre visible)
    - <blockquote expandable> con: resumen + análisis + activos + enlace (plegable)
    - Footer: AlphaBot + saludo

    Las estrellas son direccionales:
    - Positiva: más estrellas = mejor noticia (mayor impacto alcista)
    - Negativa: más estrellas = más grave (mayor impacto bajista)
    """
    item: NewsItem = entry["item"]
    a = entry["analysis"]
    ny = _ny_now()
    dia = DIAS[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")

    stars = a.get("stars", 3)
    star_str = _stars_str(stars)

    # --- PARTE SIEMPRE VISIBLE ---
    lines = [
        "🚨 <b>ÚLTIMO MINUTO</b>",
        f"{dia} {fecha}",
        SEPARATOR,
        "",
        f"{star_str} <b>{_esc(item.title)}</b>",
    ]

    # Meta: fuente + hora + bandera + sentimiento + confianza
    sent = (a.get("sentimiento") or "volatil").lower()
    conf = a.get("confianza", 0)
    sent_label = SENT_LABEL.get(sent, sent)
    fuente = _esc(item.source or "—")
    hora_item = _esc(item.time or alert_time or ny.strftime("%H:%M"))
    pais = _esc(item.country or "🇺🇸")
    lines.append(f"📰 {fuente} · 🕐 {hora_item} ET · {pais} · {sent_label} · {conf}%")

    # Agrupación de fuentes: si la misma noticia la traían varias webs, listarlas.
    fuentes = [s for s in (getattr(item, "sources", None) or []) if s]
    if len(fuentes) > 1:
        fuentes_str = ", ".join(_esc(s) for s in fuentes)
        lines.append(f"📰 {len(fuentes)} fuentes: {fuentes_str}")

    # --- DETALLE PLEGABLE (blockquote expandable) ---
    detail_parts = []

    # Resumen
    resumen = a.get("contexto") or a.get("context") or a.get("resumen") or ""
    if resumen:
        detail_parts.append("📝 <b>Resumen:</b>")
        detail_parts.append(_esc(resumen))
        detail_parts.append("")

    # Análisis profundo
    analisis = a.get("analisis_profundo") or a.get("analisis") or ""
    if not analisis:
        pts = a.get("puntos_clave") or a.get("puntos", [])
        razon = a.get("razon_activos") or a.get("razon", "")
        partes = []
        if pts:
            partes.append(" ".join(str(p) for p in pts[:3]))
        if razon:
            partes.append(razon)
        analisis = " ".join(partes)

    if analisis:
        detail_parts.append("📈 <b>Análisis:</b>")
        detail_parts.append(_esc(analisis))
        detail_parts.append("")

    # Beneficiados / Perjudicados
    ben = a.get("beneficiados") or []
    per = a.get("perjudicados") or []
    if ben or per:
        ben_str = ", ".join(_esc(b) for b in ben[:8]) if ben else "—"
        per_str = ", ".join(_esc(p) for p in per[:8]) if per else "—"
        detail_parts.append(f"🟢 <b>Beneficiados:</b> {ben_str}")
        detail_parts.append(f"🔴 <b>Perjudicados:</b> {per_str}")
        detail_parts.append("")

    # Enlace de la fuente — SIEMPRE incluir si hay URL
    if item.url:
        detail_parts.append(f'🔗 <a href="{_esc(item.url)}">Leer noticia completa</a>')
        detail_parts.append(f'📱 Publicado por: {_esc(item.source or "—")}')

    # Envolver el detalle en blockquote expandable
    if detail_parts:
        detail_html = "\n".join(detail_parts)
        lines.append(f"<blockquote expandable>{detail_html}</blockquote>")

    # --- FOOTER ---
    lines.append(SEPARATOR)
    lines.append(_footer())

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3950] + "\n... (truncado)"
    return text


def format_results_followup(entry: dict, results: dict) -> str:
    """
    SECCIÓN 1 — Seguimiento de resultados.

    Formatea un mensaje de actualización para una noticia programada
    cuyos resultados reales ya salieron. Re-analiza con datos reales.

    Estructura:
    - Encabezado + día + fecha + hora (siempre visible)
    - Título del evento + fuente + hora (siempre visible)
    - Datos: Forecast / Anterior / Actual + BEAT/MISS/EN LÍNEA (siempre visible)
    - <blockquote expandable> con: análisis con datos reales + activos + reacción (plegable)
    - Footer: AlphaBot + saludo

    entry: {"item": NewsItem, "analysis": dict} (análisis original)
    results: {"actual": str, "analisis_real": dict} (resultado real + nuevo análisis)
    """
    item: NewsItem = entry["item"]
    a_original = entry["analysis"]
    a_real = results.get("analisis_real", {})
    ny = _ny_now()
    dia = DIAS[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")
    hora = ny.strftime("%H:%M")

    stars_real = a_real.get("stars", a_original.get("stars", 3))
    star_str = _stars_str(stars_real)

    lines = [
        "📊 <b>RESULTADOS — SECTOR ECONÓMICO</b>",
        f"{dia} {fecha} · {hora}",
        SEPARATOR,
        "",
        f"🔄 <b>Actualización:</b> {_esc(item.title)}",
        f"📰 {_esc(item.source)} · 🕐 {_esc(item.time or 'N/A')} ET",
        SEPARATOR,
    ]

    # Datos esperados vs reales (SIEMPRE visible)
    forecast = item.forecast or a_original.get("forecast", "N/A")
    previous = item.previous or a_original.get("previous", "N/A")
    actual = results.get("actual") or item.actual or a_real.get("actual", "N/A")

    lines.append("📋 <b>Datos:</b>")
    lines.append(f"   Forecast: {_esc(forecast)}")
    lines.append(f"   Anterior: {_esc(previous)}")
    lines.append(f"   <b>Actual: {_esc(actual)}</b>")
    lines.append("")

    # Sorpresa (beat/miss/in-line) — SIEMPRE visible
    sorpresa = a_real.get("sorpresa") or _determine_surprise(forecast, actual)
    if sorpresa == "beat":
        lines.append("✅ <b>Resultado: SUPERÓ expectativas (BEAT)</b>")
    elif sorpresa == "miss":
        lines.append("❌ <b>Resultado: FALLO expectativas (MISS)</b>")
    else:
        lines.append("➡️ <b>Resultado: EN LÍNEA con expectativas</b>")

    # --- DETALLE PLEGABLE (blockquote expandable) ---
    detail_parts = []

    # Análisis con datos reales
    analisis_real = a_real.get("analisis_profundo") or a_real.get("analisis") or ""
    if not analisis_real:
        pts = a_real.get("puntos_clave") or a_real.get("puntos", [])
        razon = a_real.get("razon_activos") or a_real.get("razon", "")
        partes = []
        if pts:
            partes.append(" ".join(str(p) for p in pts[:3]))
        if razon:
            partes.append(razon)
        analisis_real = " ".join(partes)

    if analisis_real:
        detail_parts.append("📈 <b>Análisis con resultados reales:</b>")
        detail_parts.append(_esc(analisis_real))
        detail_parts.append("")

    # Beneficiados / Perjudicados reales
    ben = a_real.get("beneficiados") or []
    per = a_real.get("perjudicados") or []
    if ben or per:
        ben_str = ", ".join(_esc(b) for b in ben[:8]) if ben else "—"
        per_str = ", ".join(_esc(p) for p in per[:8]) if per else "—"
        detail_parts.append(f"🟢 <b>Beneficiados:</b> {ben_str}")
        detail_parts.append(f"🔴 <b>Perjudicados:</b> {per_str}")
        detail_parts.append("")

    # Reacción esperada del mercado
    reaccion = a_real.get("reaccion_mercado") or ""
    if reaccion:
        detail_parts.append(f"📊 <b>Reacción esperada:</b> {_esc(reaccion)}")
        detail_parts.append("")

    # Enlace de la fuente — SIEMPRE incluir si hay URL
    if item.url:
        detail_parts.append(f'🔗 <a href="{_esc(item.url)}">Ver fuente</a>')
        detail_parts.append(f'📱 Publicado por: {_esc(item.source or "—")}')

    # Envolver el detalle en blockquote expandable
    if detail_parts:
        detail_html = "\n".join(detail_parts)
        lines.append(f"<blockquote expandable>{detail_html}</blockquote>")

    # --- FOOTER ---
    lines.append(SEPARATOR)
    lines.append(f"{star_str} Seguimiento de resultados")
    lines.append(_footer())

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:3950] + "\n... (truncado)"
    return text


def _format_news_collapsible(num: int, item: NewsItem, a: dict) -> str:
    """
    Formatea una noticia individual de la Sección 1 con <blockquote expandable>.

    LAS ESTRELLAS VIENEN DEL CALENDARIO WEB (item.stars), NO del LLM.
    El titular + meta quedan visibles; el detalle (resumen + análisis + activos + enlace)
    va colapsado por defecto con botón "Mostrar más".
    """
    # ESTRELLAS DEL CALENDARIO WEB — no las inventa el LLM
    stars = item.stars or 0
    star_str = _stars_str(stars)

    # Encabezado SIEMPRE visible
    header = (
        f"\n<b>{num}.</b> {star_str} {_esc(item.title)}\n"
        f"🕐 {_esc(item.time or 'N/A')} ET · 📰 {_esc(item.source)} · {_esc(item.country or '🇺🇸')}"
    )

    # Detalle colapsable
    detail_parts = []

    # Datos del calendario (forecast/previous/actual si existen)
    if item.forecast or item.previous or item.actual:
        detail_parts.append("📋 <b>Datos:</b>")
        if item.forecast:
            detail_parts.append(f"   Forecast: {_esc(item.forecast)}")
        if item.previous:
            detail_parts.append(f"   Anterior: {_esc(item.previous)}")
        if item.actual:
            detail_parts.append(f"   <b>Actual: {_esc(item.actual)}</b>")
        detail_parts.append("")

    # Resumen
    resumen = a.get("contexto") or a.get("context") or a.get("resumen") or ""
    if resumen:
        detail_parts.append("📝 <b>Resumen:</b>")
        detail_parts.append(_esc(resumen))
        detail_parts.append("")

    # Análisis
    analisis = a.get("analisis_profundo") or a.get("analisis") or ""
    if not analisis:
        pts = a.get("puntos_clave") or a.get("puntos", [])
        razon = a.get("razon_activos") or a.get("razon", "")
        partes = []
        if pts:
            partes.append(" ".join(str(p) for p in pts[:3]))
        if razon:
            partes.append(razon)
        analisis = " ".join(partes)

    if analisis:
        detail_parts.append("📈 <b>Análisis:</b>")
        detail_parts.append(_esc(analisis))
        detail_parts.append("")

    # Beneficiados / Perjudicados
    ben = a.get("beneficiados") or []
    per = a.get("perjudicados") or []
    if ben or per:
        ben_str = ", ".join(_esc(b) for b in ben[:8]) if ben else "—"
        per_str = ", ".join(_esc(p) for p in per[:8]) if per else "—"
        detail_parts.append(f"🟢 <b>Beneficiados:</b> {ben_str}")
        detail_parts.append(f"🔴 <b>Perjudicados:</b> {per_str}")
        detail_parts.append("")

    # Enlace de la fuente — SIEMPRE incluir si hay URL (no filtrar Forex Factory)
    if item.url:
        detail_parts.append(f'🔗 <a href="{_esc(item.url)}">Leer noticia completa</a>')
        detail_parts.append(f'📱 Publicado por: {_esc(item.source)}')

    # Si no hay detalle, no usar blockquote
    if not detail_parts:
        return header

    # Unir detalle con saltos de línea reales (\n) dentro del blockquote
    # Telegram renderiza mejor \n que <br> dentro de <blockquote expandable>
    detail_html = "\n".join(detail_parts)

    return f"{header}\n<blockquote expandable>{detail_html}</blockquote>"


def _determine_surprise(forecast: str, actual: str) -> str:
    """
    Determina si el resultado real superó, falló o estuvo en línea
    con el forecast. Intenta parsear valores numéricos.
    """
    if not forecast or not actual or forecast == "N/A" or actual == "N/A":
        return "in_line"

    try:
        # Limpiar strings: quitar %, $, comas, espacios
        import re
        f_clean = re.sub(r"[^\d.\-]", "", str(forecast))
        a_clean = re.sub(r"[^\d.\-]", "", str(actual))

        if not f_clean or not a_clean:
            return "in_line"

        f_val = float(f_clean)
        a_val = float(a_clean)

        if f_val == 0:
            return "in_line"

        diff_pct = abs((a_val - f_val) / abs(f_val)) * 100

        if diff_pct < 2:
            return "in_line"
        return "beat" if a_val > f_val else "miss"
    except (ValueError, ZeroDivisionError):
        return "in_line"


# ============================================================
#  COMPATIBILIDAD — mantener funciones antiguas para el dashboard
# ============================================================

def _format_news(num: int, item: NewsItem, a: dict) -> str:
    """Alias para compatibilidad con código viejo que llama _format_news."""
    return _format_news_collapsible(num, item, a)


def _format_assets(a: dict) -> str:
    """Compatibilidad — formatea activos en texto plano."""
    ben = a.get("beneficiados") or []
    per = a.get("perjudicados") or []
    if not ben and not per:
        return ""
    lines = [""]
    if ben:
        lines.append(f"🟢 {', '.join(ben[:8])}")
    if per:
        lines.append(f"🔴 {', '.join(per[:8])}")
    return "\n".join(lines)
