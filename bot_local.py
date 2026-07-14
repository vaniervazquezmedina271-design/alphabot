#!/usr/bin/env python3
"""
bot_local.py — AlphaBot corriendo en local (SOLO comandos/publicaciones).

MODO CLOUD-ONLY (por defecto): la NUBE (GitHub Actions) es el ÚNICO emisor de
alertas. El bot local NO emite alertas automáticas para eliminar de raíz las
repeticiones (antes emitían PC + nube sin memoria común). El bot local solo:

1. COMANDOS/PUBLICAR (cada 30s): revisa Telegram y responde/publica al instante
   (comandos, lenguaje natural, audios, fotos, documentos, videos).

2. ACCIONES BAJO DEMANDA: si el usuario manda /report o /breaking por Telegram,
   eso SÍ se ejecuta (es acción explícita del usuario), respetando el estado
   compartido (data/state) para no duplicar.

FLAG DE EMISIÓN LOCAL (opt-in):
    - Env `LOCAL_SEND_ALERTS` ("true"/"false", default "false"), o
    - config.yaml `coordination.local_send_alerts` (default false).
  Con el valor por defecto (cloud-only) el bot local NO manda alertas
  automáticas (ni Sistema 2, ni Sistema 1, ni seguimiento de resultados);
  solo atiende comandos. Si se pone en true, el bot local vuelve a emitir
  automáticamente los tres flujos (modo antiguo PC-emisora).

La nube (GitHub Actions) es la que emite alertas 24/7. El offset de Telegram se
comparte, así que nube y local no se pisan al leer comandos.

Uso:
    python bot_local.py

Variables de entorno opcionales:
    LOCAL_SEND_ALERTS        "true" para que el local también emita (default false)
    BOT_LOCAL_BREAKING_SEC   segundos entre búsquedas del Sistema 2 (default 300)
    BOT_LOCAL_COMMANDS_SEC   segundos entre revisiones de Telegram (default 30)

Detén con Ctrl+C.
"""
from __future__ import annotations

import sys
import os
import time
import signal
from datetime import datetime

# Forzar flush de print para ver output en tiempo real + UTF-8 (emojis en Windows)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.telegram_bot import process_commands, pop_trigger
from src.report import run_breaking_alerts, run_and_send
from src.config import CACHE_DIR

try:
    from src.results_tracker import run_results_tracking
except Exception:
    run_results_tracking = None


# ============================================================
#  CONFIGURACIÓN (segundos)
# ============================================================
def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (ValueError, TypeError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "si", "sí", "on")


def _local_send_alerts() -> bool:
    """
    ¿El bot local debe EMITIR alertas automáticas?

    Por defecto FALSE (modo cloud-only): la nube es el único emisor y el local
    solo atiende comandos. El env `LOCAL_SEND_ALERTS` tiene prioridad; si no
    está definido, se consulta `coordination.local_send_alerts` en config.yaml.
    """
    if os.environ.get("LOCAL_SEND_ALERTS") is not None:
        return _env_bool("LOCAL_SEND_ALERTS", False)
    try:
        from src.config import load_config
        return bool(load_config().get("coordination", {}).get("local_send_alerts", False))
    except Exception:
        return False


COMMANDS_SEC = _env_int("BOT_LOCAL_COMMANDS_SEC", 30)   # revisar Telegram
BREAKING_SEC = _env_int("BOT_LOCAL_BREAKING_SEC", 300)  # Sistema 2 (alertas)
SEND_ALERTS = _local_send_alerts()                       # emisor local (opt-in)

# Marcador para no repetir el reporte diario (Sistema 1) el mismo día
_DAILY_MARKER = CACHE_DIR / "last_daily_local.txt"


def _ny_now() -> datetime:
    from dateutil import tz
    return datetime.now(tz.gettz("America/New_York"))


def _ny_today_str() -> str:
    return _ny_now().strftime("%Y-%m-%d")


def _is_system1_window() -> bool:
    """True si en NY son entre las 7:00 y 8:59 AM."""
    return 7 <= _ny_now().hour <= 8


def _daily_already_sent_today() -> bool:
    try:
        return _DAILY_MARKER.exists() and _DAILY_MARKER.read_text().strip() == _ny_today_str()
    except OSError:
        return False


def _mark_daily_sent() -> None:
    try:
        _DAILY_MARKER.write_text(_ny_today_str())
    except OSError:
        pass


# ============================================================
#  CICLOS DE TRABAJO
# ============================================================

def _do_commands() -> None:
    """Revisa Telegram: comandos, publicar, audios, multimedia."""
    n = process_commands()
    if n > 0:
        print(f"  [{time.strftime('%H:%M:%S')}] ✅ {n} mensaje(s) procesado(s)")

    # Si el usuario pidió /report o /breaking por Telegram, ejecutarlo ya
    trigger = pop_trigger()
    if trigger == "report":
        print(f"  [{time.strftime('%H:%M:%S')}] 📅 /report solicitado → generando reporte")
        run_and_send(reasoning=False, force=True)
    elif trigger == "breaking":
        print(f"  [{time.strftime('%H:%M:%S')}] 🚨 /breaking solicitado → buscando noticias")
        run_breaking_alerts(reasoning=False)


def _do_breaking() -> None:
    """Sistema 2 — alertas en tiempo real (solo tu watchlist)."""
    print(f"  [{time.strftime('%H:%M:%S')}] 🚨 Sistema 2: buscando noticias...")
    try:
        sent = run_breaking_alerts(reasoning=False)
        print(f"  [{time.strftime('%H:%M:%S')}] Sistema 2: {sent} alerta(s) enviada(s)")
    except Exception as e:
        print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Sistema 2 error: {e}")

    # Seguimiento de resultados (Sección 1) si aplica
    if run_results_tracking:
        try:
            run_results_tracking()
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Seguimiento error: {e}")


def _do_daily_if_due() -> None:
    """Sistema 1 — reporte diario, una vez entre 7-8 AM NY."""
    if _is_system1_window() and not _daily_already_sent_today():
        print(f"  [{time.strftime('%H:%M:%S')}] 📅 Sistema 1: ventana 7-8 AM NY → reporte diario")
        try:
            run_and_send(reasoning=False)
            _mark_daily_sent()
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Sistema 1 error: {e}")


def main():
    print("=" * 60)
    print("🤖 AlphaBot — Bot Local (tiempo real, ambos sistemas)")
    print("=" * 60)
    print(f"   Comandos/publicar : cada {COMMANDS_SEC}s")
    if SEND_ALERTS:
        print(f"   Sistema 2 alertas : cada {BREAKING_SEC}s (EMISOR LOCAL ACTIVO)")
        print(f"   Sistema 1 reporte : 1 vez entre 7-8 AM NY")
    else:
        print(f"   Modo CLOUD-ONLY: la NUBE es el único emisor de alertas.")
        print(f"   El bot local solo atiende comandos y /report /breaking manuales.")
    print(f"   Detén con Ctrl+C")
    print("=" * 60)
    print()

    def signal_handler(sig, frame):
        print("\n\n🛑 Bot local detenido.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    last_breaking = 0.0
    last_daily_check = 0.0

    while True:
        now = time.time()
        try:
            # 1) Comandos / publicar (siempre, cada ciclo)
            _do_commands()

            # 2 y 3) EMISIÓN AUTOMÁTICA de alertas: solo si el flag está activo.
            #   Modo cloud-only (default): la nube es el único emisor → el local
            #   NO ejecuta Sistema 2, Sistema 1 ni seguimiento automáticamente.
            if SEND_ALERTS:
                # Sistema 2 — alertas (cada BREAKING_SEC)
                if now - last_breaking >= BREAKING_SEC:
                    _do_breaking()
                    last_breaking = now

                # Sistema 1 — reporte diario (revisar cada ~5 min)
                if now - last_daily_check >= 300:
                    _do_daily_if_due()
                    last_daily_check = now

        except KeyboardInterrupt:
            signal_handler(None, None)
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Error: {e}")

        time.sleep(COMMANDS_SEC)


if __name__ == "__main__":
    main()
