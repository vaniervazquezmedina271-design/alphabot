"""
Bot de Telegram interactivo — comunicación natural + audios.

El usuario puede comunicarse de TRES formas:
1. Comandos directos: /add AAPL Apple,iPhone  (rápido, sin gastar tokens)
2. Lenguaje natural: "agrega Apple a mi lista" (usa LLM para interpretar)
3. Audios de voz: el agente transcribe con Groq Whisper y procesa el texto

Comandos directos (sin LLM):
  /add AAPL Apple,iPhone     — añade empresa a la watchlist
  /remove TSLA               — quita empresa de la watchlist
  /list                      — muestra la watchlist actual
  /report                    — genera y envía el reporte diario AHORA
  /breaking                  — busca noticias de última hora AHORA
  /publica <texto>           — publica un mensaje en el canal
  /status                    — estado del agente (proveedor, failover)
  /help                      — lista de comandos

Lenguaje natural (con LLM):
  "agrega Apple a mi lista"
  "ya no sigas a Tesla"
  "muéstrame mi lista"
  "genera el reporte de hoy"
  "qué hay de nuevo en el mercado"
  "publica: reunión a las 3pm"
  "qué proveedor estás usando"
"""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

import requests

from .config import get_env, CACHE_DIR, BASE_DIR
from .notifier import send_to_telegram

TELEGRAM_API = "https://api.telegram.org/bot{token}"
OFFSET_FILE: Path = CACHE_DIR / "telegram_offset.txt"
TRIGGER_FILE: Path = CACHE_DIR / "telegram_trigger.txt"
VOICE_DIR: Path = CACHE_DIR / "voice"
VOICE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
#  LECTURA DE MENSAJES (texto + audios)
# ============================================================

def _load_offset() -> int:
    if OFFSET_FILE.exists():
        try:
            return int(OFFSET_FILE.read_text().strip())
        except (ValueError, OSError):
            pass
    return 0


def _save_offset(offset: int) -> None:
    try:
        OFFSET_FILE.write_text(str(offset))
    except OSError:
        pass


def fetch_updates() -> list[dict]:
    """
    Llama a getUpdates de Telegram.
    Devuelve mensajes nuevos desde la última revisión.
    Soporta: texto, audios de voz, fotos, documentos, videos, animaciones, reenvíos.

    Cada mensaje tiene "type" y según el tipo campos adicionales.
    Todos incluyen: chat_id, update_id, message_id, caption (si existe).
    """
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    user_id = get_env("TELEGRAM_USER_ID")
    # Chats autorizados: el canal (TELEGRAM_CHAT_ID) + el chat privado del usuario (TELEGRAM_USER_ID)
    authorized_chats = {c for c in [chat_id, user_id] if c}
    if not token:
        return []

    last_offset = _load_offset()
    url = f"{TELEGRAM_API.format(token=token)}/getUpdates"

    try:
        resp = requests.get(url, params={
            "offset": last_offset + 1,
            "timeout": 5,
            "allowed_updates": json.dumps(["message"]),
        }, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️ Telegram getUpdates error {resp.status_code}")
            return []
        data = resp.json()
    except Exception as e:
        print(f"  ⚠️ Telegram getUpdates: {e}")
        return []

    if not data.get("ok"):
        return []

    messages = []
    max_update_id = last_offset

    for update in data.get("result", []):
        update_id = update.get("update_id", 0)
        if update_id <= last_offset:
            continue

        msg = update.get("message", {})
        from_chat_id = str(msg.get("chat", {}).get("id", ""))
        message_id = msg.get("message_id", 0)
        caption = (msg.get("caption") or "").strip()
        is_forward = "forward_origin" in msg or "forward_from" in msg or "forward_from_chat" in msg

        # Seguridad: solo responder a chats autorizados (canal + chat privado del usuario)
        if authorized_chats and from_chat_id not in authorized_chats:
            print(f"  ⚠️ Mensaje de chat no autorizado: {from_chat_id}")
            max_update_id = max(max_update_id, update_id)
            continue

        # Detectar tipo de mensaje
        if msg.get("voice"):
            file_id = msg["voice"].get("file_id", "")
            if file_id:
                messages.append({
                    "type": "voice",
                    "file_id": file_id,
                    "chat_id": from_chat_id,
                    "update_id": update_id,
                    "message_id": message_id,
                    "caption": caption,
                })
        elif msg.get("photo"):
            # photo es un array de tamaños; el último es el más grande
            photo = msg["photo"][-1]
            messages.append({
                "type": "photo",
                "file_id": photo.get("file_id", ""),
                "chat_id": from_chat_id,
                "update_id": update_id,
                "message_id": message_id,
                "caption": caption,
                "is_forward": is_forward,
            })
        elif msg.get("document"):
            doc = msg["document"]
            messages.append({
                "type": "document",
                "file_id": doc.get("file_id", ""),
                "file_name": doc.get("file_name", "documento"),
                "mime_type": doc.get("mime_type", ""),
                "chat_id": from_chat_id,
                "update_id": update_id,
                "message_id": message_id,
                "caption": caption,
                "is_forward": is_forward,
            })
        elif msg.get("video"):
            vid = msg["video"]
            messages.append({
                "type": "video",
                "file_id": vid.get("file_id", ""),
                "chat_id": from_chat_id,
                "update_id": update_id,
                "message_id": message_id,
                "caption": caption,
                "is_forward": is_forward,
            })
        elif msg.get("animation"):
            anim = msg["animation"]
            messages.append({
                "type": "animation",
                "file_id": anim.get("file_id", ""),
                "chat_id": from_chat_id,
                "update_id": update_id,
                "message_id": message_id,
                "caption": caption,
                "is_forward": is_forward,
            })
        elif msg.get("text"):
            messages.append({
                "type": "text",
                "content": msg["text"].strip(),
                "chat_id": from_chat_id,
                "update_id": update_id,
                "message_id": message_id,
                "is_forward": is_forward,
            })

        max_update_id = max(max_update_id, update_id)

    if max_update_id > last_offset:
        _save_offset(max_update_id)

    return messages


# ============================================================
#  TRANSCRIPCIÓN DE AUDIOS (Groq Whisper — gratis)
# ============================================================

def _download_voice_file(file_id: str) -> Path | None:
    """Descarga un archivo de audio de Telegram."""
    token = get_env("TELEGRAM_BOT_TOKEN")
    if not token:
        return None

    # Paso 1: obtener la ruta del archivo
    try:
        resp = requests.get(
            f"{TELEGRAM_API.format(token=token)}/getFile",
            params={"file_id": file_id},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("ok"):
            return None
        file_path = data["result"]["file_path"]
    except Exception:
        return None

    # Paso 2: descargar el archivo
    download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
    local_path = VOICE_DIR / f"{file_id}.ogg"
    try:
        resp = requests.get(download_url, timeout=30)
        if resp.status_code != 200:
            return None
        local_path.write_bytes(resp.content)
        return local_path
    except Exception:
        return None


def _transcribe_audio(audio_path: Path) -> str | None:
    """
    Transcribe un audio usando Groq Whisper (gratis, ultra-rápido).
    Devuelve el texto transcrito o None si falla.
    """
    groq_key = get_env("GROQ_API_KEY")
    if not groq_key:
        return None

    try:
        from openai import OpenAI
        client = OpenAI(api_key=groq_key, base_url="https://api.groq.com/openai/v1")

        with open(audio_path, "rb") as audio_file:
            resp = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=audio_file,
                language="es",   # el usuario habla español
            )
        return resp.text.strip()
    except Exception as e:
        print(f"  ⚠️ Transcripción de audio falló: {e}")
        return None


# Regex robusto para detectar orden de publicar.
# Funciona con cualquier puntuación después de la palabra clave:
#   "publica: ..."  "publica, ..."  "publica ..."  "Pública. ..."  "posta ..." etc.
# Insensible a acentos: "Pública" == "publica" == "Publica"
import unicodedata as _unicodedata

_PUBLISH_RE = re.compile(
    r'^(?:publica(?:r)?|posta|comparte|anuncia|envia\s+al\s+canal)'
    r'\s*[:\,\.；；]?\s*(.*)',
    re.IGNORECASE | re.DOTALL,
)


def _strip_accents(s: str) -> str:
    """Quita acentos del texto para comparación insensible a tildes."""
    return ''.join(
        c for c in _unicodedata.normalize('NFD', s)
        if _unicodedata.category(c) != 'Mn'
    )


def _extract_publish_text(text: str) -> str | None:
    """
    Detecta intención de publicar y extrae el mensaje a publicar.
    Devuelve:
      - None  → no es orden de publicar
      - ""    → orden de publicar pero sin contenido (pedir qué publicar)
      - "..." → el texto a publicar
    """
    stripped = text.strip()
    # Normalizar acentos para el match (Pública → publica, envía → envia)
    normalized = _strip_accents(stripped)
    m = _PUBLISH_RE.match(normalized)
    if not m:
        return None
    # El grupo 1 del regex ya contiene el texto a publicar (sin acentos).
    # Pero queremos conservar los acentos del mensaje original.
    # El match del keyword en el texto normalizado tiene la misma longitud
    # que en el original (los acentos son combining chars que se eliminan,
    # pero la posición del grupo 1 es la misma).
    # Para preservar acentos, recortamos el texto original desde la posición
    # donde termina el keyword + puntuación.
    keyword_end = len(normalized) - len(m.group(1))
    # Ajustar: el keyword_end puede no coincidir exactamente con el original
    # si había acentos. Buscar el keyword en el original por longitud aproximada.
    # Simplificación: usar el texto del grupo 1 pero buscarlo en el original.
    msg = m.group(1).strip()
    if not msg:
        return ""
    # Buscar el mensaje sin acentos en el texto original sin acentos y
    # usar esa posición para extraer del original (con acentos).
    norm_msg_start = normalized.find(msg)
    if norm_msg_start >= 0:
        return stripped[norm_msg_start:].strip()
    return msg


# ============================================================
#  PROCESAMIENTO DE COMANDOS
# ============================================================

def process_commands() -> int:
    """
    Lee mensajes pendientes y los procesa (texto, audio, foto, documento, video).
    Devuelve cuántos procesó.

    Comportamiento:
    - Media (foto/doc/video/animación) → auto-publicar en el canal
    - Audio de voz → transcribir y procesar (si dice "publica:" → publicar)
    - Texto → procesar como comando/NLP/publica
    """
    messages = fetch_updates()
    if not messages:
        return 0

    from . import watchlist as wl

    count = 0
    for msg in messages:
        chat_id = msg["chat_id"]
        msg_type = msg["type"]

        # ─── MEDIA: foto, documento, video, animación → auto-publicar ───
        if msg_type in ("photo", "document", "video", "animation"):
            caption = msg.get("caption", "")
            ok = _forward_media_to_channel(msg)
            if ok:
                tipo_nombre = {"photo": "Foto", "document": "Documento",
                               "video": "Video", "animation": "Animación"}[msg_type]
                cap_str = f"\n\n📝 {caption}" if caption else ""
                _send_response(chat_id, f"✅ {tipo_nombre} publicado en el canal{cap_str}")
            else:
                _send_response(chat_id, "❌ No se pudo publicar el medio. Revisa la conexión.")
            count += 1
            continue

        # ─── AUDIO DE VOZ → transcribir y procesar ───
        if msg_type == "voice":
            _send_response(chat_id, "🎤 Transcribiendo audio...")
            audio_path = _download_voice_file(msg["file_id"])
            if not audio_path:
                _send_response(chat_id, "❌ No pude descargar el audio.")
                count += 1
                continue

            text = _transcribe_audio(audio_path)
            if not text:
                _send_response(chat_id, "❌ No pude transcribir el audio. ¿Está configurada GROQ_API_KEY?")
                count += 1
                continue

            _send_response(chat_id, f"🎤 Transcripción: \"{text}\"\n\nProcesando...")

            # Si el audio dice "publica..." → publicar en el canal
            msg_text = _extract_publish_text(text)
            if msg_text is not None:
                if msg_text:
                    ok = _publish_to_channel(msg_text)
                    if ok:
                        _send_response(chat_id, f"✅ Publicado en el canal:\n\n{msg_text}")
                    else:
                        _send_response(chat_id, "❌ No se pudo publicar. Revisa la conexión.")
                else:
                    _send_response(chat_id, "❌ ¿Qué quieres que publique? Dime después de 'publica:'")
                count += 1
                continue

            # Procesar el texto transcrito (comando, acción conocida, o auto-publicar)
            response = _process_message(text, wl)
            _send_response(chat_id, response)
            count += 1
            continue

        # ─── TEXTO → comando / NLP / publica ───
        if msg_type == "text":
            text = msg["content"]
            response = _process_message(text, wl)
            _send_response(chat_id, response)
            count += 1
            continue

        count += 1

    return count


def _process_message(text: str, wl) -> str:
    """
    Procesa un mensaje de texto (escrito o transcrito de audio).

    El usuario le dice al bot QUÉ hacer:
    1. ¿Empieza con / ? → comando directo (sin LLM)
    2. ¿Es "publica: ..." ? → publicar en el canal
    3. ¿Es una acción conocida (agrega, quita, reporte, etc.)? → ejecutar
    4. Cualquier otra cosa → usar LLM para interpretar la intención
    """
    if not text:
        return "Envía /help o escribe lo que necesites."

    text_stripped = text.strip()
    parts = text_stripped.split()
    first_word = parts[0].lower() if parts else ""

    # 1. ¿Empieza con / ? → comando directo (sin LLM, sin gastar tokens)
    if first_word.startswith("/"):
        return _handle_command(text_stripped, wl)

    # 2. ¿Es "publica: ..." ? → publicar (extraer el texto después)
    msg_text = _extract_publish_text(text_stripped)
    if msg_text is not None:
        if msg_text:
            ok = _publish_to_channel(msg_text)
            if ok:
                return f"✅ Publicado en el canal:\n\n{msg_text}"
            else:
                return "❌ No se pudo publicar. Revisa la conexión."
        return "❌ ¿Qué quieres que publique? Escribe el mensaje después de 'publica:'"

    # 3+4. Lenguaje natural → interpretar con NLP (patrones rápidos o LLM)
    return _handle_natural_language(text_stripped, wl)


def _handle_command(text: str, wl) -> str:
    """Enruta un comando directo (empieza con /). Sin LLM."""
    parts = text.strip().split()
    cmd = parts[0].lower().split("@")[0]  # quitar @botname

    if cmd == "/add":
        return _cmd_add(parts)
    elif cmd in ("/remove", "/rm"):
        return _cmd_remove(parts)
    elif cmd in ("/list", "/ls"):
        return wl.list_companies()
    elif cmd == "/status":
        return _cmd_status()
    elif cmd in ("/help", "/start"):
        return _cmd_help()
    elif cmd == "/report":
        _trigger_task("report")
        return "📅 Generando reporte diario ahora..."
    elif cmd == "/breaking":
        _trigger_task("breaking")
        return "🚨 Buscando noticias de última hora ahora..."
    elif cmd in ("/publica", "/pub", "/post", "/publicar"):
        return _cmd_publish(parts)
    else:
        return f"❓ Comando no reconocido: {cmd}\nEnvía /help para ver los disponibles."


# ============================================================
#  LENGUAJE NATURAL (con LLM)
# ============================================================

NLP_SYSTEM_PROMPT = """Eres un asistente que interpreta mensajes del usuario para controlar un agente financiero y administrar un canal de Telegram.
Devuelves SIEMPRE un JSON válido con la acción a ejecutar.

Acciones disponibles:
- publish: publicar un mensaje en el canal de Telegram. Params: mensaje (el texto a publicar). Usa esta acción cuando el usuario quiera publicar, enviar, compartir, postear o anunciar algo en el canal.
- add: añadir empresa a la watchlist. Params: ticker (símbolo bursátil), name (nombre), aliases (lista)
- remove: quitar empresa de la watchlist. Params: ticker
- list: mostrar la watchlist
- report: generar reporte diario ahora
- breaking: buscar noticias de última hora ahora
- status: mostrar estado del agente
- help: mostrar ayuda
- chat: conversación general sobre finanzas/mercado (no es una acción específica)

Formato de respuesta:
```json
{
  "accion": "publish|add|remove|list|report|breaking|status|help|chat",
  "mensaje": "texto a publicar en el canal (solo si accion=publish)",
  "ticker": "AAPL",
  "name": "Apple",
  "aliases": ["iPhone"],
  "respuesta": "Mensaje amigable para el usuario confirmando lo que entendiste"
}
```

CLAVE: Si el usuario dice algo que suena a mensaje para el canal (buenos días, anuncios, recordatorios, saludos a la comunidad, comentarios del mercado, etc.), usa "publish" y pon TODO el mensaje del usuario en "mensaje".
Si el usuario hace una pregunta general sobre el mercado o finanzas, usa "chat" y responde en "respuesta".
Si pide añadir una empresa pero no das el ticker exacto, infiérelo (Apple=AAPL, Tesla=TSLA, etc).
Responde en español, tono cercano pero profesional."""

# El diccionario de nombres→tickers ahora vive en watchlist.py (NAME_TO_TICKER)
# y se usa vía resolve_ticker(). Aquí solo los patrones de detección de intención.


def _try_quick_nlp(text: str, wl) -> str | None:
    """
    Intenta interpretar el mensaje sin LLM (ahorro de tokens).
    Detecta patrones comunes: "agrega X", "quita X", "muéstrame la lista", etc.
    Devuelve la respuesta o None si no puede (entonces usa LLM).
    """
    lower = text.lower().strip()

    # Mostrar lista
    if any(p in lower for p in ["lista", "muestr", "ver mi", "cuales sigo", "cuáles sigo",
                                 "mi watchlist", "mis empresas"]):
        return wl.list_companies()

    # Estado
    if any(p in lower for p in ["estado", "status", "qué proveedor", "que proveedor",
                                 "cómo estás", "como estas", "funcionando"]):
        return _cmd_status()

    # Ayuda
    if any(p in lower for p in ["ayuda", "help", "comandos", "qué puedes", "que puedes",
                                 "qué haces", "que haces"]):
        return _cmd_help()

    # Generar reporte
    if any(p in lower for p in ["reporte", "report", "informe", "calendario",
                                 "eventos de hoy", "qué hay hoy", "que hay hoy"]):
        _trigger_task("report")
        return "📅 Generando reporte diario ahora..."

    # Buscar noticias
    if any(p in lower for p in ["noticias", "última hora", "ultima hora", "novedades",
                                 "qué hay de nuevo", "que hay de nuevo", "breaking",
                                 "qué pasó", "que paso"]):
        _trigger_task("breaking")
        return "🚨 Buscando noticias de última hora ahora..."

    # Publicar mensaje en el canal — manejado por _extract_publish_text() en _process_message()

    # Añadir empresa — buscar por nombre conocido usando el diccionario ampliado
    add_patterns = ["agrega", "añade", "anade", "sigue", "sigas", "seguir", "incluir",
                    "incluye", "añadir", "anadir", "pon", "meter", "mete", "monitoriza",
                    "vigila", "rastrea", "quiero que sigas", "añademe", "anademe",
                    "agregame", "agrégame", "añádeme"]
    if any(lower.startswith(p) or f" {p} " in f" {lower} " for p in add_patterns):
        # Intentar resolver cualquier empresa mencionada con el diccionario ampliado
        from .watchlist import NAME_TO_TICKER
        for name_key in NAME_TO_TICKER:
            if name_key in lower:
                return wl.add_company(name_key)
        # También intentar resolver el texto completo (ej: "añade COIN")
        # Qitar las palabras de acción y probar con el resto
        words = lower.split()
        for w in words:
            if w in add_patterns:
                continue
            resolved = wl.resolve_ticker(w) if hasattr(wl, 'resolve_ticker') else None
            # resolve_ticker está en el módulo watchlist, no en el objeto wl
            from .watchlist import resolve_ticker as _resolve
            resolved = _resolve(w)
            if resolved:
                return wl.add_company(w)
        return None  # no reconocemos la empresa → dejar al LLM

    # Quitar empresa
    remove_patterns = ["quita", "elimina", "borra", "remueve", "saca", "deja de seguir",
                       "no sigas", "ya no", "dejar de", "quitar", "eliminar"]
    if any(lower.startswith(p) or f" {p} " in f" {lower} " for p in remove_patterns):
        from .watchlist import NAME_TO_TICKER
        for name_key in NAME_TO_TICKER:
            if name_key in lower:
                return wl.remove_company(name_key)
        # Intentar resolver palabra por palabra
        words = lower.split()
        for w in words:
            if w in remove_patterns:
                continue
            from .watchlist import resolve_ticker as _resolve
            resolved = _resolve(w)
            if resolved:
                return wl.remove_company(w)
        return None

    return None  # no pudo interpretar → usar LLM


def _handle_natural_language(text: str, wl) -> str:
    """
    Interpreta un mensaje en lenguaje natural.
    Primero intenta sin LLM (patrones comunes). Si no puede, usa el LLM.
    """
    # Intento 1: patrones rápidos (sin gastar tokens)
    quick = _try_quick_nlp(text, wl)
    if quick is not None:
        return quick

    # Intento 2: usar LLM para interpretar
    try:
        from .llm import chat as llm_chat
        from .watchlist import list_companies

        # Dar contexto al LLM sobre la watchlist actual
        current_list = list_companies()
        context = f"Watchlist actual del usuario:\n{current_list}\n\nMensaje del usuario:\n{text}"

        resp = llm_chat(
            [{"role": "system", "content": NLP_SYSTEM_PROMPT},
             {"role": "user", "content": context}],
            temperature=0.1,
            max_tokens=500,
            reasoning=False,
        )

        # Parsear la respuesta del LLM
        import re
        # Extraer JSON
        m = re.search(r"\{.*\}", resp, re.DOTALL)
        if not m:
            return "🤔 No entendí qué quieres. Envía /help para ver qué puedo hacer."

        data = json.loads(m.group())
        action = data.get("accion", "chat")
        reply = data.get("respuesta", "")

        # Ejecutar la acción detectada por el LLM
        if action == "publish" and data.get("mensaje"):
            msg_text = data["mensaje"]
            ok = _publish_to_channel(msg_text)
            if ok:
                return f"✅ Publicado en el canal:\n\n{msg_text}"
            else:
                return "❌ No se pudo publicar. Revisa la conexión."
        elif action == "add" and data.get("ticker"):
            ticker = data["ticker"].upper()
            name = data.get("name", ticker)
            aliases = data.get("aliases", [])
            result = wl.add_company(ticker, name, aliases)
            return result
        elif action == "remove" and data.get("ticker"):
            result = wl.remove_company(data["ticker"].upper())
            return result
        elif action == "list":
            return wl.list_companies()
        elif action == "report":
            _trigger_task("report")
            return reply or "📅 Generando reporte diario ahora..."
        elif action == "breaking":
            _trigger_task("breaking")
            return reply or "🚨 Buscando noticias de última hora ahora..."
        elif action == "status":
            return _cmd_status()
        elif action == "help":
            return _cmd_help()
        else:
            # chat general
            return reply or "🤔 No entendí qué quieres. Envía /help para ver qué puedo hacer."

    except Exception as e:
        # Si el LLM falla (rate limit, etc.), fallback a mensaje genérico
        return (f"🤔 No pude procesar tu mensaje ahora mismo.\n"
                f"Puedes usar comandos directos: /add, /remove, /list, /report, /breaking, /status, /help")


# ============================================================
#  COMANDOS DIRECTOS (handlers)
# ============================================================

def _cmd_add(parts: list[str]) -> str:
    """
    Formato: /add TICKER o /add Nombre (ej: /add AAPL o /add Apple o /add coca cola)
    Opcional: /add AAPL Apple,iPhone (ticker + nombre y aliases con coma)
    """
    from . import watchlist as wl
    if len(parts) < 2:
        return ("❌ Uso: /add TICKER o /add Nombre\n"
                "Ej: /add AAPL o /add Apple o /add coca cola\n"
                "Opcional: /add AAPL Apple,iPhone (nombre + aliases)")

    # Unir todo lo que viene después de /add
    full_arg = " ".join(parts[1:])

    # ¿Hay comas? → separar en nombre + aliases
    if "," in full_arg:
        items = [s.strip() for s in full_arg.split(",") if s.strip()]
        arg = items[0]
        name = items[1] if len(items) > 1 else ""
        aliases = items[2:] if len(items) > 2 else []
        return wl.add_company(arg, name, aliases)
    else:
        # Sin comas → todo es el ticker o nombre
        return wl.add_company(full_arg)


def _cmd_remove(parts: list[str]) -> str:
    """Formato: /remove TICKER o /remove Nombre (ej: /remove TSLA o /remove Tesla o /remove coca cola)"""
    from . import watchlist as wl
    if len(parts) < 2:
        return "❌ Uso: /remove TICKER o /remove Nombre\nEj: /remove TSLA o /remove Tesla"
    full_arg = " ".join(parts[1:])
    return wl.remove_company(full_arg)


# ============================================================
#  PUBLICAR MENSAJES EN EL CANAL
# ============================================================

def _publish_to_channel(text: str) -> bool:
    """
    Publica un mensaje de texto en el canal de Telegram con formato AlphaBot.
    Si el texto es largo (>300 chars), usa <blockquote expandable> automáticamente.
    Devuelve True si se envió correctamente.
    """
    from .formatter import _ny_now, _saludo, SEPARATOR

    ny = _ny_now()
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia = dias[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")
    hora = ny.strftime("%H:%M")

    # Escapar HTML
    import html as _html
    import re
    clean_text = _html.escape(text, quote=False)

    # Convertir *negrita* de Markdown a <b>negrita</b> de HTML
    clean_text = re.sub(r"\*(.+?)\*", r"<b>\1</b>", clean_text)

    # Convertir enlaces planos en <a> clickeables
    url_pattern = r'(https?://[^\s<]+)'
    clean_text = re.sub(url_pattern, r'<a href="\1">\1</a>', clean_text)

    # Si el texto es largo → usar blockquote expandable
    if len(clean_text) > 300:
        body = f"<blockquote expandable>{clean_text}</blockquote>"
    else:
        body = clean_text

    message = (
        f"📢 <b>MENSAJE</b>\n"
        f"{dia} {fecha} · {hora}\n"
        f"{SEPARATOR}\n\n"
        f"{body}\n\n"
        f"{SEPARATOR}\n"
        f"🤖 AlphaBot · {_saludo()}"
    )

    return send_to_telegram(message, parse_mode="HTML")


def _forward_media_to_channel(msg: dict) -> bool:
    """
    Reenvía un medio (foto, documento, video, animación) al canal con formato AlphaBot.
    Usa copyMessage de Telegram para preservar el medio original,
    luego envía un mensaje separado con el header/footer.
    """
    token = get_env("TELEGRAM_BOT_TOKEN")
    chat_id = get_env("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    from .formatter import _ny_now, _saludo, SEPARATOR

    ny = _ny_now()
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dia = dias[ny.weekday()]
    fecha = ny.strftime("%d/%m/%Y")
    hora = ny.strftime("%H:%M")
    caption = msg.get("caption", "")

    # Escapar caption
    import html as _html
    import re
    clean_caption = _html.escape(caption, quote=False) if caption else ""
    clean_caption = re.sub(r"\*(.+?)\*", r"<b>\1</b>", clean_caption)

    tipo_nombre = {"photo": "📷 Foto", "document": "📄 Documento",
                   "video": "🎬 Video", "animation": "🎞️ Animación"}
    tipo_label = tipo_nombre.get(msg["type"], "📢 Contenido")

    # Header + caption (si existe)
    header_msg = (
        f"{tipo_label}\n"
        f"{dia} {fecha} · {hora}\n"
        f"{SEPARATOR}"
    )
    if clean_caption:
        header_msg += f"\n{clean_caption}"

    # 1. Enviar header + caption al canal
    ok1 = send_to_telegram(header_msg, parse_mode="HTML")

    # 2. Copiar el medio original al canal usando copyMessage
    url = f"{TELEGRAM_API.format(token=token)}/copyMessage"
    try:
        payload = {
            "chat_id": chat_id,
            "from_chat_id": chat_id,
            "message_id": msg["message_id"],
        }
        resp = requests.post(url, json=payload, timeout=15)
        ok2 = resp.status_code == 200
    except Exception:
        ok2 = False

    # 3. Enviar footer
    footer_msg = f"{SEPARATOR}\n🤖 AlphaBot · {_saludo()}"
    send_to_telegram(footer_msg, parse_mode="HTML")

    return ok1 and ok2


def _cmd_publish(parts: list[str]) -> str:
    """
    Formato: /publica <texto> o /pub <texto>
    Publica el texto en el canal de Telegram.
    """
    if len(parts) < 2:
        return ("❌ Uso: /publica <texto>\n"
                "Ej: /publica Reunión de mercado a las 3pm\n"
                "También puedes decir: publica: reunión a las 3pm\n"
                "O envíame una foto/documento y lo publico automáticamente.")

    # Todo lo que viene después del comando
    text = " ".join(parts[1:])

    ok = _publish_to_channel(text)
    if ok:
        return f"✅ Publicado en el canal:\n\n{text}"
    else:
        return "❌ No se pudo publicar. Revisa la conexión."


def _cmd_status() -> str:
    from .config import load_config
    from .llm import get_failover_chain

    cfg = load_config()
    active = cfg.get("active", {})
    chain = get_failover_chain()
    companies = cfg.get("watchlist", {}).get("companies", [])

    lines = [
        "🤖 *Estado del Agente*\n",
        f"• Proveedor activo: `{active.get('provider', '?')}`",
        f"• Modelo: `{active.get('model', '?')}`",
        f"• Failover: {len(chain)} proveedor(es) disponible(s)",
    ]

    if len(chain) > 1:
        names = []
        for p in chain[1:]:
            label = p.model or p.__class__.__name__
            names.append(f"`{label}`")
        lines.append(f"  → {' → '.join(names)}")

    lines.append(f"• Watchlist: {len(companies)} empresa(s)")
    lines.append(f"• Umbral normal: {cfg.get('filter', {}).get('breaking_min_score', 70)}%")
    lines.append(f"• Umbral watchlist: {cfg.get('watchlist', {}).get('min_score_watchlist', 55)}%")

    return "\n".join(lines)


def _cmd_help() -> str:
    return (
        "🤖 *AlphaBot — Ayuda*\n\n"
        "Puedes escribirme normal o usar comandos:\n\n"
        "📋 *Watchlist (por ticker o nombre):*\n"
        "• `/add AAPL` o `/add Apple` o \"agrega Apple\"\n"
        "• `/remove TSLA` o `/remove Tesla` o \"quita Tesla\"\n"
        "• `/list` o \"muéstrame mi lista\"\n\n"
        "📊 *Tareas:*\n"
        "• `/report` o \"genera el reporte\"\n"
        "• `/breaking` o \"qué hay de nuevo\"\n\n"
        "📢 *Publicar en el canal:*\n"
        "• `/publica <texto>` o \"publica: <texto>\"\n"
        "• Envíame una *foto, documento o video* y lo publico automáticamente\n"
        "• Si el texto es largo, se pone en desplegable\n"
        "• También puedes mandarme un audio diciendo \"publica: ...\"\n\n"
        "ℹ️ *Info:*\n"
        "• `/status` o \"qué proveedor usas\"\n"
        "• `/help`\n\n"
        "🎤 *Audios de voz: transcribo y proceso.*\n"
        "💡 El agente revisa Telegram al inicio de cada ejecución horaria."
    )


# ============================================================
#  EJECUCIÓN DIFERIDA DE TAREAS (/report, /breaking)
# ============================================================

def _trigger_task(task: str) -> None:
    try:
        TRIGGER_FILE.write_text(task)
    except OSError:
        pass


def pop_trigger() -> str | None:
    """Lee y borra la tarea pendiente disparada por Telegram."""
    if TRIGGER_FILE.exists():
        try:
            task = TRIGGER_FILE.read_text().strip()
            TRIGGER_FILE.unlink()
            return task if task in ("report", "breaking") else None
        except OSError:
            pass
    return None


# ============================================================
#  ENVÍO DE RESPUESTAS
# ============================================================

def _send_response(chat_id: str, text: str) -> None:
    token = get_env("TELEGRAM_BOT_TOKEN")
    if not token or not chat_id:
        return

    url = f"{TELEGRAM_API.format(token=token)}/sendMessage"
    try:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code != 200:
            # Fallback a texto plano: omitir parse_mode (no pasar None)
            payload.pop("parse_mode", None)
            requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print(f"  ⚠️ Error respondiendo a Telegram: {e}")
