"""
Interfaz de lenguaje natural — el usuario habla con el agente en español normal.
No usa comandos, solo conversación.

Ejemplos de lo que el usuario puede decir:
  "dame el reporte de hoy"
  "hay noticias importantes ahora?"
  "qué afecta a NVIDIA?"
  "envíame las alertas a telegram"
  "cambia el modelo a gemini"
  "busca noticias de apple"
"""
from __future__ import annotations

import re
from typing import Optional

from .llm import chat
from .config import load_config
from .report import generate_daily_report, run_breaking_alerts
from .notifier import send_to_telegram
from .sources.base import NewsItem


def process_message(user_input: str) -> str:
    """
    Procesa un mensaje en lenguaje natural del usuario.
    Devuelve la respuesta del agente (en español, natural).
    """
    msg = user_input.lower().strip()

    # --- DETECCIÓN DE INTENCIÓN ---

    # Reporte diario
    if any(w in msg for w in ["reporte", "reporte de hoy", "dame el reporte",
                               "noticias de hoy", "que hay hoy", "qué hay hoy",
                               "eventos de hoy", "calendario"]):
        return _handle_daily_report(msg)

    # Alertas en tiempo real
    if any(w in msg for w in ["alerta", "alertas", "noticias ahora", "que esta pasando",
                               "qué está pasando", "ultimas noticias", "últimas noticias",
                               "noticias del momento", "algo importante"]):
        return _handle_breaking_alerts(msg)

    # Enviar a Telegram
    if any(w in msg for w in ["telegram", "envia", "envía", "mandalo", "mándalo",
                               "enviar a mi canal", "enviar al canal"]):
        return _handle_send_telegram(msg)

    # Buscar empresa específica
    ticker_match = _extract_ticker(msg)
    if ticker_match or any(w in msg for w in ["buscar", "analiza", "analice",
                                                "que pasa con", "qué pasa con",
                                                "noticias de", "informacion de"]):
        return _handle_search(msg, ticker_match)

    # Cambiar modelo
    if any(w in msg for w in ["cambia el modelo", "cambiar modelo", "usa gemini",
                               "usa openai", "cambiar proveedor", "otro modelo"]):
        return _handle_change_model(msg)

    # Ayuda
    if any(w in msg for w in ["ayuda", "help", "que puedes hacer", "qué puedes hacer",
                               "comandos", "opciones"]):
        return _help_text()

    # Estado del agente
    if any(w in msg for w in ["estado", "como estas", "cómo estás", "funcionando",
                               "conectado", "status"]):
        return _handle_status()

    # Si no reconoce la intención, usa el LLM para responder naturalmente
    return _handle_general_chat(user_input)


# ============================================================
#  HANDLERS
# ============================================================

def _handle_daily_report(msg: str) -> str:
    """Genera el reporte diario."""
    try:
        report, entries = generate_daily_report(reasoning=False)
        if entries:
            return report
        return "📊 No hay eventos macro de alto impacto programados hoy."
    except Exception as e:
        return f"❌ Error al generar el reporte: {e}"


def _handle_breaking_alerts(msg: str) -> str:
    """Procesa alertas en tiempo real."""
    try:
        count = run_breaking_alerts(reasoning=False, max_news=15)
        if count > 0:
            return f"🚨 {count} alertas de alto impacto enviadas a tu Telegram."
        return "📊 No hay noticias de alto impacto en este momento para el mercado americano."
    except Exception as e:
        return f"❌ Error al buscar alertas: {e}"


def _handle_send_telegram(msg: str) -> str:
    """Envía contenido a Telegram."""
    # Si dice "envía el reporte", genera y envía
    if "reporte" in msg:
        report, entries = generate_daily_report(reasoning=False)
        ok = send_to_telegram(report)
        return "✅ Reporte enviado a Telegram." if ok else "❌ Error al enviar."
    return "¿Qué quieres que envíe a Telegram? Puedes decir 'envía el reporte' o 'envía las alertas'."


def _handle_search(msg: str, ticker: Optional[str]) -> str:
    """Busca noticias de una empresa o tema específico."""
    tema = ticker or msg.replace("buscar", "").replace("analiza", "").replace(
        "analice", "").replace("noticias de", "").replace("informacion de", "").strip()

    if not tema:
        return "¿Qué empresa o tema quieres que analice? Ejemplo: 'busca noticias de NVIDIA'"

    try:
        prompt = f"""Busca y analiza noticias recientes sobre: {tema}
        Enfócate en el mercado americano (bolsa de EE.UU.).
        Devuelve un resumen conciso con:
        - Sentimiento actual (positivo/negativo/neutral)
        - 2-3 puntos clave
        - Posible impacto en el precio
        """
        resp = chat([
            {"role": "system", "content": "Eres un analista del mercado de valores americano. Responde en español, conciso."},
            {"role": "user", "content": prompt}
        ], max_tokens=800, reasoning=False)
        return resp
    except Exception as e:
        return f"❌ Error al buscar: {e}"


def _handle_change_model(msg: str) -> str:
    """Cambia el modelo activo."""
    return ("Para cambiar el modelo, abre el dashboard con `streamlit run app.py` "
            "y ve a la pestaña 'Proveedores'. Ahí puedes buscar, pegar tu API key "
            "y elegir cualquier modelo.")


def _handle_status() -> str:
    """Devuelve el estado del agente."""
    cfg = load_config()
    active = cfg.get("active", {})
    from .config import get_env
    groq = bool(get_env("GROQ_API_KEY"))
    tg = bool(get_env("TELEGRAM_BOT_TOKEN"))

    return (f"🤖 **Estado del agente:**\n"
            f"• Modelo: {active.get('model', '?')}\n"
            f"• Proveedor: {active.get('provider', '?')}\n"
            f"• Groq API: {'✅' if groq else '❌'}\n"
            f"• Telegram: {'✅' if tg else '❌'}\n"
            f"• Fuentes: FinViz, Yahoo Finance, Investing, Bloomberg\n"
            f"• Enfoque: Mercado americano (bolsa USA)")


def _handle_general_chat(user_input: str) -> str:
    """Responde preguntas generales usando el LLM."""
    try:
        resp = chat([
            {"role": "system", "content": "Eres un asistente financiero del mercado americano. Responde en español, conciso y claro. Si te preguntan algo fuera de finanzas, redirige al tema."},
            {"role": "user", "content": user_input}
        ], max_tokens=800, reasoning=False)
        return resp
    except Exception as e:
        return f"❌ No pude procesar tu mensaje. Error: {e}"


def _extract_ticker(msg: str) -> Optional[str]:
    """Extrae un ticker potencial del mensaje (palabra en MAYÚSCULAS de 2-5 letras)."""
    match = re.search(r'\b[A-Z]{2,5}\b', msg.upper())
    if match:
        word = match.group()
        # Filtrar palabras comunes que no son tickers
        if word not in ["EL", "LA", "DE", "EN", "QUE", "PARA", "CON", "POR"]:
            return word
    return None


def _help_text() -> str:
    """Texto de ayuda."""
    return """🤖 **Cómo hablar con el agente**

Puedes decirme cosas como:

📊 **Reporte diario:**
  • "dame el reporte de hoy"
  • "qué hay hoy en el calendario"

🚨 **Alertas en tiempo real:**
  • "hay noticias importantes ahora?"
  • "últimas noticias del mercado"

🔍 **Buscar empresa:**
  • "busca noticias de NVIDIA"
  • "qué pasa con AAPL?"
  • "analiza Microsoft"

📲 **Telegram:**
  • "envía el reporte a telegram"
  • "envía las alertas"

ℹ️ **Estado:**
  • "cómo estás?"
  • "estado del agente"

Solo háblame normal, en español. Yo entiendo lo que necesitas."""
