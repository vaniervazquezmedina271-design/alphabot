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
            if resp.status_code != 200:
                # Si falla, reintentar sin parse_mode (texto plano)
                # NO pasar parse_mode=None → omitir la clave completamente
                payload.pop("parse_mode", None)
                resp2 = requests.post(url, json=payload, timeout=15)
                if resp2.status_code != 200:
                    print(f"❌ Telegram error {resp2.status_code}: {resp2.text[:200]}")
                    all_ok = False
                # else: éxito con texto plano, all_ok se mantiene True
        except Exception as e:
            print(f"❌ Error enviando a Telegram: {e}")
            all_ok = False

    return all_ok


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
    return chunks


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
