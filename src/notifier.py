"""
Notificador — envía mensajes a Telegram.
Usa requests simple (no depende de python-telegram-bot para enviar).
Se parte en múltiples mensajes si excede 4096 chars.

Soporta dos modos de formato:
  - Markdown (legacy): para mensajes antiguos y compatibilidad
  - HTML (default para reportes): soporta <blockquote expandable>, <b>, <i>, <a>
"""
from __future__ import annotations

import re
import time

import requests

from .config import get_env

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_LEN = 4096


def send_to_telegram(text: str, chat_id: str = None, token: str = None,
                     parse_mode: str = "HTML") -> bool:
    """
    Envía un mensaje a Telegram. Si excede MAX_LEN, lo parte.
    Devuelve True si todos los fragmentos se enviaron OK.

    parse_mode: "HTML" (default, soporta blockquote expandable), "Markdown", o None.

    Comportamiento de fallos (para NO volver a fallar en silencio):
      - Si el intento con parse_mode devuelve 429 (rate limit), respeta
        `retry_after` y reintenta UNA vez con el mismo formato.
      - Si el intento con parse_mode devuelve otro !=200, reintenta SIN
        parse_mode pero con las etiquetas HTML ELIMINADAS (fallback legible,
        no etiquetas literales).
      - SIEMPRE imprime status + body cuando una respuesta no es 200.
      - Solo devuelve True si TODOS los fragmentos se entregaron (200).
    """
    token = token or get_env("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or get_env("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("❌ Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en .env")
        return False

    url = TELEGRAM_API.format(token=token)

    # Partir si es muy largo
    chunks = _split_message(text, MAX_LEN)
    all_ok = True
    for chunk in chunks:
        try:
            # Limpiar formato problemático según el parse_mode
            if parse_mode == "HTML":
                clean = _sanitize_html(chunk)
            elif parse_mode == "Markdown":
                clean = _sanitize_markdown(chunk)
            else:
                clean = chunk

            payload = {
                "chat_id": chat_id,
                "text": clean,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True,
            }
            resp = requests.post(url, json=payload, timeout=15)

            # --- Rate limit (429): respetar retry_after y reintentar 1 vez ---
            if resp.status_code == 429:
                wait = _retry_after_seconds(resp)
                print(f"⚠️ Telegram 429 (rate limit). Reintentando en {wait}s... "
                      f"body: {resp.text[:200]}")
                time.sleep(wait)
                resp = requests.post(url, json=payload, timeout=15)

            if resp.status_code != 200:
                # El envío con formato falló: registrar el error crudo (antes se
                # perdía en silencio) y reintentar SIN parse_mode, pero con las
                # etiquetas HTML ELIMINADAS para que el fallback sea legible.
                print(f"⚠️ Telegram {resp.status_code} con parse_mode={parse_mode}: "
                      f"{resp.text[:300]}")

                fallback_payload = {
                    "chat_id": chat_id,
                    "text": _strip_tags(chunk),
                    "disable_web_page_preview": True,
                }
                resp2 = requests.post(url, json=fallback_payload, timeout=15)
                if resp2.status_code != 200:
                    print(f"❌ Telegram error {resp2.status_code} (fallback texto plano): "
                          f"{resp2.text[:300]}")
                    all_ok = False
                else:
                    print("ℹ️ Entregado en texto plano (fallback sin formato HTML).")
        except Exception as e:
            print(f"❌ Error enviando a Telegram: {e}")
            all_ok = False

    return all_ok


def _retry_after_seconds(resp) -> int:
    """
    Extrae los segundos de espera de una respuesta 429 de Telegram.
    Busca en el JSON (parameters.retry_after) y en el header Retry-After.
    Devuelve un valor acotado (1-30s) para no bloquear demasiado.
    """
    wait = 1
    try:
        data = resp.json()
        wait = int(data.get("parameters", {}).get("retry_after", 0)) or wait
    except Exception:
        pass
    try:
        header = resp.headers.get("Retry-After")
        if header:
            wait = max(wait, int(header))
    except Exception:
        pass
    return max(1, min(wait, 30))


def _strip_tags(text: str) -> str:
    """
    Elimina las etiquetas HTML que usamos para Telegram, dejando texto legible.
    Se usa como fallback cuando el envío con parse_mode=HTML falla: en vez de
    mostrar '<blockquote expandable>...<b>...</b>' literal, muestra solo el texto.

    - Convierte enlaces <a href="url">texto</a> en 'texto (url)'.
    - Quita el resto de etiquetas (<b>, <i>, <blockquote ...>, etc.).
    - Desescapa entidades HTML (&amp; &lt; &gt; ...).
    """
    import html as _html

    # <a href="url">texto</a> → texto (url)
    text = re.sub(
        r'<a\s+href="([^"]*)"[^>]*>(.*?)</a>',
        lambda m: f"{m.group(2)} ({m.group(1)})" if m.group(1) else m.group(2),
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Quitar cualquier otra etiqueta <...>
    text = re.sub(r"<[^>]+>", "", text)
    # Desescapar entidades HTML
    text = _html.unescape(text)
    return text


def send_photo_to_telegram(image_path: str, caption: str = "",
                           chat_id: str = None, token: str = None,
                           parse_mode: str = "HTML") -> bool:
    """
    Envía una imagen (foto) a Telegram con un caption opcional (máx 1024 chars).
    Devuelve True si se envió. Si falla con parse_mode, reintenta sin él.
    """
    token = token or get_env("TELEGRAM_BOT_TOKEN")
    chat_id = chat_id or get_env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("❌ Falta TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en .env")
        return False

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    cap = (caption or "")[:1024]
    try:
        with open(image_path, "rb") as img:
            files = {"photo": img}
            data = {"chat_id": chat_id, "caption": cap, "parse_mode": parse_mode}
            resp = requests.post(url, data=data, files=files, timeout=30)
        if resp.status_code != 200:
            # Reintento sin parse_mode (omitir la clave, no pasar None)
            with open(image_path, "rb") as img:
                files = {"photo": img}
                data = {"chat_id": chat_id, "caption": cap}
                resp = requests.post(url, data=data, files=files, timeout=30)
        return resp.status_code == 200
    except Exception as e:
        print(f"❌ Error enviando foto a Telegram: {e}")
        return False


def test_telegram_connection(token: str = None, chat_id: str = None) -> tuple[bool, str]:
    """Envía un mensaje de prueba y devuelve (éxito, mensaje)."""
    ok = send_to_telegram(
        "🤖 <b>Market Daily Bot</b> conectado correctamente.\n"
        "Este es un mensaje de prueba.",
        chat_id=chat_id, token=token,
        parse_mode="HTML",
    )
    if ok:
        return True, "✅ Mensaje de prueba enviado a Telegram."
    return False, "❌ No se pudo enviar. Revisa el token y el chat_id."


def _split_message(text: str, max_len: int) -> list[str]:
    """Parte un mensaje largo sin cortar palabras a mitad."""
    if len(text) <= max_len:
        return [text]

    chunks = []
    while len(text) > max_len:
        # Buscar punto de corte cercano a max_len
        cut = max_len
        for sep in ["\n\n", "\n", ". ", " "]:
            pos = text.rfind(sep, 0, max_len)
            if pos > max_len * 0.5:
                cut = pos + len(sep)
                break
        chunks.append(text[:cut])
        text = text[cut:]
    if text.strip():
        chunks.append(text)
    return _balance_blockquotes(chunks)


def _balance_blockquotes(chunks: list[str]) -> list[str]:
    """
    Asegura que cada fragmento tenga las etiquetas <blockquote> balanceadas.

    Al partir un mensaje largo (ej. el reporte diario con muchos eventos, cada
    uno en su <blockquote expandable>), el corte puede caer DENTRO de un
    blockquote. Sin balancear, Telegram fallaría el parseo HTML de ese
    fragmento. Aquí: si un fragmento deja un blockquote abierto, se cierra al
    final; y el siguiente se reabre al principio.
    """
    open_tag = "<blockquote expandable>"
    close_tag = "</blockquote>"
    fixed: list[str] = []
    carry_open = False
    for chunk in chunks:
        if carry_open:
            chunk = open_tag + chunk
        opens = chunk.count("<blockquote")
        closes = chunk.count(close_tag)
        if opens > closes:
            chunk = chunk + close_tag
            carry_open = True
        else:
            carry_open = False
        fixed.append(chunk)
    return fixed


def _sanitize_html(text: str) -> str:
    """
    Limpia texto HTML para Telegram.
    Telegram soporta: <b>, <i>, <u>, <s>, <code>, <pre>, <a href>, <blockquote>, <blockquote expandable>
    NO soporta <br> dentro de blockquote en algunas versiones → reemplazar por \n
    """
    # Reemplazar <br> por salto de línea real (Telegram a veces no renderiza <br> en blockquote)
    text = text.replace("<br>", "\n")
    # Quitar enlaces rotos: [texto](url) → texto (por si quedó Markdown mezclado)
    text = re.sub(r"\[([^\]]+)\]\(([^\)]*)\)", r'\1', text)
    return text


def _sanitize_markdown(text: str) -> str:
    """
    Limpia el texto para que Telegram no rompa con Markdown.
    Escapa guiones bajos _ sueltos que no son formato, y caracteres especiales.
    """
    # Si hay paréntesis de enlace roto [texto] sin (url), quitar corchetes
    text = re.sub(r"\[([^\]]+)\]\([^\)]*\)", r"\1", text)
    # Escapar guiones bajos sueltos (no los de negrita/cursiva)
    text = re.sub(r"(?<![*\w])_(?![*\w])", " ", text)
    return text
