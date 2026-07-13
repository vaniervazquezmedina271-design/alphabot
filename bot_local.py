#!/usr/bin/env python3
"""
bot_local.py — Bot de Telegram corriendo en local (tiempo real).

¿Para qué sirve?
- Revisa Telegram cada 30 segundos (no cada hora como la nube)
- Publica en el canal al INSTANTE cuando le mandas algo
- Procesa comandos, lenguaje natural, audios y multimedia en tiempo real
- La nube (GitHub Actions) sigue funcionando cuando la PC está apagada

Cómo usar:
    python bot_local.py

Detén con Ctrl+C cuando quieras pararlo.

Notas:
- NO usa LLM para publicar (detección de "publica:" es instantánea)
- NO gasta tokens de LLM excepto para audios que no dicen "publica:"
- El offset de Telegram se comparte con la nube (data/cache/telegram_offset.txt)
  → Si la nube procesó un mensaje, el bot local no lo repite, y viceversa
"""
from __future__ import annotations

import sys
import os
import time
import signal

# Forzar flush de print para ver output en tiempo real
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.telegram_bot import process_commands

# ============================================================
#  CONFIGURACIÓN
# ============================================================
INTERVALO = 30  # segundos entre cada revisión de Telegram


def main():
    print("=" * 55)
    print("🤖 AlphaBot — Bot Local (tiempo real)")
    print("=" * 55)
    print(f"   Revisando Telegram cada {INTERVALO} segundos")
    print(f"   Publica al instante cuando le mandas algo")
    print(f"   Detén con Ctrl+C")
    print("=" * 55)
    print()

    # Manejar Ctrl+C limpiamente
    def signal_handler(sig, frame):
        print("\n\n🛑 Bot local detenido.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Loop principal
    ciclo = 0
    while True:
        ciclo += 1
        try:
            n = process_commands()
            if n > 0:
                print(f"  [{time.strftime('%H:%M:%S')}] ✅ {n} mensaje(s) procesado(s)")
            else:
                # Mostrar un heartbeat cada 2 minutos (4 ciclos sin mensajes)
                if ciclo % 4 == 0:
                    print(f"  [{time.strftime('%H:%M:%S')}] 💤 Sin mensajes nuevos...")
        except KeyboardInterrupt:
            signal_handler(None, None)
        except Exception as e:
            print(f"  [{time.strftime('%H:%M:%S')}] ⚠️ Error: {e}")

        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
