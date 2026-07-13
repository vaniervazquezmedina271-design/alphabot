#!/usr/bin/env python3
"""
bot_local.py — AlphaBot corriendo en local (tiempo real).

Hace TRES cosas mientras tu PC esté encendida:

1. COMANDOS/PUBLICAR (cada 30s): revisa Telegram y responde/publica al instante
   (comandos, lenguaje natural, audios, fotos, documentos, videos).

2. SISTEMA 2 — ALERTAS (cada 5 min por defecto): busca noticias de tu watchlist
   y envía al instante las de alto impacto. En la nube esto solo pasa por hora;
   en local sale mucho más rápido.

3. SISTEMA 1 — REPORTE DIARIO (una vez, entre 7-8 AM NY): genera y envía el
   reporte del calendario económico (Finviz). Usa un marcador para no repetirlo.

La nube (GitHub Actions) sigue funcionando cuando la PC está apagada.
El offset de Telegram se comparte, así que nube y local no se pisan.

Uso:
    python bot_local.py

Variables de entorno opcionales:
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


COMMANDS_SEC = _env_int("BOT_LOCAL_COMMANDS_SEC", 30)   # revisar Telegram
BREAKING_SEC = _env_int("BOT_LOCAL_BREAKING_SEC", 300)  # Sistema 2 (alertas)

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
        run_and_send(reasoning=False)
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
    print(f"   Sistema 2 alertas : cada {BREAKING_SEC}s")
    print(f"   Sistema 1 reporte : 1 vez entre 7-8 AM NY")
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

            # 2) Sistema 2 — alertas (cada BREAKING_SEC)
            if now - last_breaking >= BREAKING_SEC:
                _do_breaking()
                last_breaking = now

            # 3) Sistema 1 — reporte diario (revisar cada ~5 min)
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
