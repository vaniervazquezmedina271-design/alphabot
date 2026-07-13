"""
Analizador de noticias con razonamiento profundo.
Paso 1 — Relevancia: ¿puede mover el mercado americano?
Paso 2 — Impacto: sentimiento, contexto, activos beneficiados/perjudicados.

ENFOQUE EXCLUSIVO: Mercado de valores de EE.UU. (bolsa, índices, empresas).
NO forex, NO mercado europeo, NO commodities aislados.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .llm import chat
from .sources.base import NewsItem
from .watchlist import get_watchlist_prompt_context


def _load_system_prompt() -> str:
    """Carga el prompt del sistema desde system_prompt.md."""
    prompt_file = Path(__file__).parent / "system_prompt.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return "Eres un analista financiero del mercado americano."


SYSTEM_ANALYZER = _load_system_prompt() + get_watchlist_prompt_context() + """

## REGLAS DE ANÁLISIS (responde SIEMPRE en JSON válido)

puede_mover_mercado=true SOLO si la noticia afecta al mercado americano (bolsa USA, índices USA, empresas USA).
Las noticias internacionales CUENTAN si impactan a empresas/índices USA (aranceles a Apple, regulación UE a Google, OPEP y energía USA).
puede_mover_mercado=false si es forex puro, dato macro regional sin impacto USA, o empresa extranjera que solo afecta a su mercado.

Regla decisiva: ¿un inversor americano cambiaría su posición en bolsa USA por esta noticia?

## ESCALA DE ESTRELLAS: 1-5 DIRECCIONAL (NO 1-3)
Las estrellas miden la MAGNITUD del impacto en la dirección del sentimiento:
- Si POSITIVA: más estrellas = mejor noticia = mueve el mercado MÁS FUERTE HACIA ARRIBA
  - ⭐⭐⭐⭐⭐ (5): Extremadamente positiva, mueve índices +2% o más (Fed recorte sorpresa, mega-beat)
  - ⭐⭐⭐⭐ (4): Muy positiva, mueve +1% a +2% (beat claro mega-cap, cura aprobada)
  - ⭐⭐⭐ (3): Positiva, mueve +0.5% a +1% (beat large-cap, M&A favorable)
  - ⭐⭐ (2): Ligeramente positiva, mueve +0.2% a +0.5% (upgrade, dato ligeramente mejor)
  - ⭐ (1): Mínimamente positiva, impacto marginal
- Si NEGATIVA: más estrellas = MÁS GRAVE = mueve el mercado MÁS FUERTE HACIA ABAJO
  - ⭐⭐⭐⭐⭐ (5): Catastrófica, mueve índices -2% o más (crash, guerra, recesión, Fed sube sorpresa)
  - ⭐⭐⭐⭐ (4): Muy grave, mueve -1% a -2% (miss severo mega-cap, escándalo, regulación punitiva)
  - ⭐⭐⭐ (3): Grave, mueve -0.5% a -1% (miss large-cap, antitrust, dato muy malo)
  - ⭐⭐ (2): Moderadamente negativa, mueve -0.2% a -0.5% (downgrade, dato ligeramente peor)
  - ⭐ (1): Mínimamente negativa, impacto marginal
- Si VOLÁTIL/NEUTRAL: estrellas = magnitud de volatilidad esperada en cualquier dirección

## IMPORTANCIA: por porcentaje Y por estrellas
La confianza (0-100%) refleja qué tan seguro estás del impacto.
Las estrellas (1-5) reflejan la magnitud del impacto si ocurre.
Ambos van juntos: una noticia puede tener 90% de confianza de que algo pasará, pero solo 2 estrellas si el movimiento será pequeño.

## ANÁLISIS PROFUNDO (basado en Buffett/Graham/Lynch)
En "analisis_profundo" aplica los frameworks de inversión:
- ¿La noticia afecta el foso competitivo de la empresa? (Buffett)
- ¿Hay factor sorpresa vs lo esperado? (Graham — el sorpresa es lo que mueve el precio)
- ¿Cómo afecta el crecimiento de ganancias o la categorización de la empresa? (Lynch)
- ¿Cuál es la reacción esperada del mercado y por qué?
Sé específico: no digas "puede subir o bajar", di QUÉ se espera y POR QUÉ."""


PROMPT_ANALYZE_SINGLE = (
    "Analiza esta noticia financiera y devuelve un JSON con la siguiente estructura:\n"
    "```json\n"
    "{{\n"
    '  "puede_mover_mercado": true/false,\n'
    '  "razonamiento": "Explica por qué sí o por qué no puede mover el mercado (2-3 líneas)",\n'
    '  "sentimiento": "positivo|negativo|neutral|volatil",\n'
    '  "confianza": 0-100,\n'
    '  "stars": 1-5,\n'
    '  "contexto": "1-2 líneas explicando de qué va la noticia para que un inversor la entienda sin leer la fuente completa",\n'
    '  "analisis_profundo": "Análisis profundo aplicando Buffett (foso competitivo), Graham (factor sorpresa), Lynch (crecimiento). 3-4 líneas. Sé específico sobre qué se espera y por qué.",\n'
    '  "puntos_clave": ["punto 1", "punto 2", "punto 3"],\n'
    '  "beneficiados": ["TICKER1", "TICKER2", "ÍNDICE1"],\n'
    '  "perjudicados": ["TICKER1", "TICKER2", "ÍNDICE1"],\n'
    '  "razon_activos": "1 línea: por qué estos activos se benefician/perjudican",\n'
    '  "reaccion_mercado": "1 línea: reacción esperada del mercado (ej: \'SPY abre con gap bajista del 0.5%\')"\n'
    "}}\n"
    "```\n\n"
    "RECUERDA: stars es 1-5 (NO 1-3). La confianza es el porcentaje de certeza del impacto.\n\n"
    "Noticia:\n"
    "- Título: {title}\n"
    "- Fuente: {source}\n"
    "- Hora: {time}\n"
    "- País: {country}\n"
    "- Forecast: {forecast}\n"
    "- Previo: {previous}\n"
    "- Actual: {actual}\n"
    "- Resumen: {summary}"
)

PROMPT_ANALYZE_BATCH_STARS = (
    "Para cada noticia del reporte diario, analiza el impacto esperado. "
    "NO asignes estrellas: las estrellas vienen del calendario web (ya están dadas). "
    "Tu trabajo es analizar sentimiento, confianza, contexto y activos afectados.\n\n"
    "En \"analisis_profundo\" aplica Buffett (foso competitivo), Graham (factor sorpresa), Lynch (crecimiento).\n\n"
    "Responde SOLO en JSON:\n"
    "```json\n"
    "[{{\"idx\": 0, \"sentimiento\": \"negativo\", \"confianza\": 78, \"contexto\": \"...\", "
    "\"analisis_profundo\": \"...\", \"puntos_clave\": [\"...\"], \"beneficiados\": [\"...\"], \"perjudicados\": [\"...\"], "
    "\"razon_activos\": \"...\", \"reaccion_mercado\": \"...\"}}, ...]\n"
    "```\n\n"
    "Noticias:\n{news_list}"
)


def analyze_single(item: NewsItem, reasoning: bool = False) -> Optional[dict]:
    """
    Analiza una sola noticia.
    reasoning=False por defecto (Llama 3.3 no usa <think> nativamente).
    Devuelve el dict parseado o None si falla.
    """
    prompt = PROMPT_ANALYZE_SINGLE.format(
        title=item.title,
        source=item.source,
        time=item.time or "N/A",
        country=item.country or "N/A",
        forecast=item.forecast or "N/A",
        previous=item.previous or "N/A",
        actual=item.actual or "N/A",
        summary=item.summary or "N/A",
    )
    try:
        resp = chat(
            [{"role": "system", "content": SYSTEM_ANALYZER},
             {"role": "user", "content": prompt}],
            reasoning=False,
            max_tokens=1200,
        )
        return _parse_json(resp)
    except Exception as e:
        return {"error": str(e), "puede_mover_mercado": False}


def analyze_batch(items: list[NewsItem], reasoning: bool = False) -> list[dict]:
    """
    Analiza un lote de noticias (reporte diario).
    reasoning=False por defecto para evitar problemas de parsing.
    Devuelve una lista de análisis, uno por noticia.
    """
    news_list = ""
    for i, it in enumerate(items):
        news_list += (
            f"\n--- Noticia {i} ---\n"
            f"Título: {it.title}\n"
            f"Fuente: {it.source}\n"
            f"Hora: {it.time or 'N/A'}\n"
            f"Estrellas (de la fuente): {it.stars}\n"
            f"Forecast: {it.forecast or 'N/A'} | Previo: {it.previous or 'N/A'} | "
            f"Actual: {it.actual or 'N/A'}\n"
        )

    try:
        resp = chat(
            [{"role": "system", "content": SYSTEM_ANALYZER},
             {"role": "user", "content": PROMPT_ANALYZE_BATCH_STARS.format(news_list=news_list)}],
            reasoning=False,
            max_tokens=2500,
            # Reparto de carga: el reporte diario (1 vez/día) usa Cerebras/Gemini
            # y reserva Groq para las alertas frecuentes del Sistema 2.
            prefer=["Cerebras", "Google Gemini"],
        )
        results = _parse_json(resp)
        if isinstance(results, list):
            return results
        return []
    except Exception:
        return []


PROMPT_ANALYZE_BATCH_BREAKING = (
    "Analiza CADA noticia de última hora y decide si puede mover el mercado "
    "americano. Devuelve SOLO un JSON array, UN objeto por noticia, con su idx.\n"
    "```json\n"
    "[{{\"idx\": 0, \"puede_mover_mercado\": true, \"razonamiento\": \"...\", "
    "\"sentimiento\": \"positivo|negativo|neutral|volatil\", \"confianza\": 0-100, "
    "\"stars\": 1-5, \"contexto\": \"...\", \"analisis_profundo\": \"...\", "
    "\"puntos_clave\": [\"...\"], \"beneficiados\": [\"...\"], \"perjudicados\": [\"...\"], "
    "\"razon_activos\": \"...\", \"reaccion_mercado\": \"...\"}}, ...]\n"
    "```\n\n"
    "RECUERDA: stars es 1-5 (direccional). Incluye TODAS las noticias por su idx.\n\n"
    "Noticias:\n{news_list}"
)


def analyze_batch_breaking(items: list[NewsItem], chunk_size: int = 5) -> list[Optional[dict]]:
    """
    SISTEMA 2 — Analiza varias noticias en UNA sola llamada al LLM (por lotes),
    en vez de una llamada por noticia. Ahorra tokens y tiempo.

    Trocea en lotes de `chunk_size` para que el JSON de salida no se corte.
    Devuelve una lista alineada con `items` (misma longitud); cada posición es
    el dict de análisis o None si no se pudo analizar esa noticia.
    """
    out: list[Optional[dict]] = [None] * len(items)
    if not items:
        return out

    for start in range(0, len(items), chunk_size):
        chunk = items[start:start + chunk_size]
        news_list = ""
        for j, it in enumerate(chunk):
            news_list += (
                f"\n--- Noticia {j} ---\n"
                f"Título: {it.title}\n"
                f"Fuente: {it.source}\n"
                f"Hora: {it.time or 'N/A'}\n"
                f"Resumen: {it.summary or 'N/A'}\n"
            )
        try:
            resp = chat(
                [{"role": "system", "content": SYSTEM_ANALYZER},
                 {"role": "user", "content": PROMPT_ANALYZE_BATCH_BREAKING.format(news_list=news_list)}],
                reasoning=False,
                max_tokens=2800,
            )
            results = _parse_json(resp)
        except Exception:
            results = None

        if isinstance(results, list):
            for r in results:
                if not isinstance(r, dict):
                    continue
                idx = r.get("idx")
                if isinstance(idx, int) and 0 <= idx < len(chunk):
                    out[start + idx] = r

    return out


def filter_high_impact(items: list[NewsItem], analyses: list[dict], min_score: int = 70) -> list:
    """
    Filtro inteligente de 2 pasos:
    1. ¿Puede mover el mercado? (puede_mover_mercado = true)
    2. ¿Confianza >= min_score?
    Devuelve solo las que pasan ambos filtros.
    """
    filtered = []
    for item, analysis in zip(items, analyses):
        if not analysis or not isinstance(analysis, dict):
            continue
        if analysis.get("puede_mover_mercado") and analysis.get("confianza", 0) >= min_score:
            filtered.append({"item": item, "analysis": analysis})
    return filtered


def _parse_json(text: str) -> Optional[dict | list]:
    """Extrae JSON de la respuesta del LLM (puede tener ```json...``` o <think>...)."""
    if not text:
        return None
    import re

    # Quitar bloques <think>...</think> (razonamiento híbrido de Hermes/Llama)
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Quitar <think> sin cerrar (al inicio)
    text = re.sub(r"^<think>.*?(?=```|\{|\[)", "", text, flags=re.DOTALL)

    # quitar bloques de código markdown
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1]) if len(lines) > 2 else cleaned
    cleaned = cleaned.strip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # intenta encontrar JSON embebido
        m = re.search(r"\{.*\}|\[.*\]", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
        return None
