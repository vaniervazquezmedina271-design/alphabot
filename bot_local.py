#!/usr/bin/env python3
"""
bot_local.py — AlphaBot corriendo en local.

DOS CONTROLES SEPARADOS de emisión automática:

1. SISTEMA 1 (reporte diario) — EMISOR LOCAL PUNTUAL (por defecto ACTIVO):
   el usuario enciende la PC ~8 AM (NY) y quiere el reporte antes de las 9 AM.
   El cron de GitHub llega tarde (a veces horas), así que el bot local lo emite
   puntualmente al arrancar la PC dentro de la ventana 7-9 AM NY. La NUBE queda
   como RESPALDO (si la PC está apagada). El guard compartido
   (data/state/daily_report.json) evita duplicados: quien envíe primero marca,
   el otro se salta.
   Control: `local_send_daily` (default TRUE). Env `LOCAL_SEND_DAILY` prioritario.

2. SISTEMA 2 (alertas último minuto) + seguimiento de resultados — SOLO-NUBE
   (por defecto INACTIVO en local). La nube (GitHub Actions) es el único emisor
   para eliminar de raíz las repeticiones (antes emitían PC + nube sin memoria
   común).
   Control: `local_send_alerts` (default FALSE). Env `LOCAL_SEND_ALERTS` prioritario.

Además, SIEMPRE (independiente de los flags):
   COMANDOS/PUBLICAR (cada 30s): revisa Telegram y responde/publica al instante
   (comandos, lenguaje natural, audios, fotos, documentos, videos). Si el usuario
   manda /report o /breaking, eso SÍ se ejecuta (acción explícita), respetando
   el estado compartido (data/state) para no duplicar.

El offset de Telegram se comparte, así que nube y local no se pisan al leer
comandos.

Uso:
    python bot_local.py

Variables de entorno opcionales:
    LOCAL_SEND_DAILY         "false" para NO emitir el reporte diario en local (default true)
    LOCAL_SEND_ALERTS        "true" para que el local también emita Sistema 2 (default false)
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


def _coord_flag(env_name: str, cfg_key: str, default: bool) -> bool:
    """
    Lee un flag de coordinación con prioridad: env > config.yaml > default.
    """
    if os.environ.get(env_name) is not None:
        return _env_bool(env_name, default)
    try:
        from src.config import load_config
        return bool(load_config().get("coordination", {}).get(cfg_key, default))
    except Exception:
        return default


def _local_send_daily() -> bool:
    """
    ¿El bot local debe EMITIR el reporte diario (Sistema 1) automáticamente?

    Por defecto TRUE: el bot local es el emisor puntual del reporte matutino
    (7-9 AM NY); la nube es respaldo. El env `LOCAL_SEND_DAILY` tiene prioridad;
    si no está definido, se consulta `coordination.local_send_daily` en config.yaml.
    """
    return _coord_flag("LOCAL_SEND_DAILY", "local_send_daily", True)


def _local_send_alerts() -> bool:
    """
    ¿El bot local debe EMITIR alertas del Sistema 2 automáticamente?

    Por defecto FALSE (solo-nube): la nube es el único emisor del Sistema 2 y el
    seguimiento de resultados. El env `LOCAL_SEND_ALERTS` tiene prioridad; si no
    está definido, se consulta `coordination.local_send_alerts` en config.yaml.
    """
    return _coord_flag("LOCAL_SEND_ALERTS", "local_send_alerts", False)


COMMANDS_SEC = _env_int("BOT_LOCAL_COMMANDS_SEC", 30)   # revisar Telegram
BREAKING_SEC = _env_int("BOT_LOCAL_BREAKING_SEC", 300)  # Sistema 2 (alertas)
SEND_DAILY = _local_send_daily()                         # emisor local Sistema 1 (default true)
SEND_ALERTS = _local_send_alerts()                       # emisor local Sistema 2 (default false)


def _ny_now() -> datetime:
    from dateutil import tz
    return datetime.now(tz.gettz("America/New_York"))


def _is_system1_window() -> bool:
    """True si en NY son entre las 7:00 y 9:59 AM (ventana matutina puntual)."""
    try:
        return 7 <= _ny_now().hour <= 9
    except Exception:
        # Si falla la zona horaria, dejar pasar (mejor ejecutar que fallar)
        return True


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
    """
    Sistema 1 — reporte diario, una vez entre 7-9 AM NY.

    NO usa marcador local propio: delega en el GUARD COMPARTIDO. `run_and_send`
    (sin force) hace pull del estado, comprueba `daily_report_sent_today()` y solo
    marca `mark_daily_report_sent()` tras un envío exitoso. Así local y nube NO se
    duplican: quien envíe primero marca; el otro se salta.
    """
    if _is_system1_window():
        print(f"  [{time.strftime('%H:%M:%S')}] 📅 Sistema 1: ventana 7-9 AM NY → reporte diario (guard compartido)")
        try:
            run_and_send(reasoning=False)
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Sistema 1 error: {e}")


def main():
    print("=" * 60)
    print("🤖 AlphaBot — Bot Local (Sistema 1 puntual + comandos)")
    print("=" * 60)
    print(f"   Comandos/publicar : cada {COMMANDS_SEC}s (siempre)")
    if SEND_DAILY:
        print(f"   Sistema 1 reporte : EMISOR LOCAL puntual 7-9 AM NY (nube = respaldo)")
    else:
        print(f"   Sistema 1 reporte : SOLO-NUBE (emisión local desactivada)")
    if SEND_ALERTS:
        print(f"   Sistema 2 alertas : cada {BREAKING_SEC}s (EMISOR LOCAL ACTIVO)")
    else:
        print(f"   Sistema 2 alertas : SOLO-NUBE (la nube es el único emisor)")
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
            # 1) Comandos / publicar (SIEMPRE, cada ciclo, sin importar flags)
            _do_commands()

            # 2) Sistema 1 — reporte diario: emisor LOCAL puntual (default ON).
            #    Se apoya en el guard compartido para no duplicar con la nube.
            if SEND_DAILY:
                if now - last_daily_check >= 300:   # revisar cada ~5 min
                    _do_daily_if_due()
                    last_daily_check = now

            # 3) Sistema 2 — alertas + seguimiento: SOLO-NUBE por defecto.
            #    Solo si local_send_alerts está activo (opt-in).
            if SEND_ALERTS:
                if now - last_breaking >= BREAKING_SEC:
                    _do_breaking()
                    last_breaking = now

        except KeyboardInterrupt:
            signal_handler(None, None)
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Error: {e}")

        time.sleep(COMMANDS_SEC)


if __name__ == "__main__":
    main()
