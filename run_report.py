#!/usr/bin/env python3
"""
run_report.py — Ejecuta el agente financiero.

DOS SISTEMAS SEPARADOS:

1. Reporte diario (default): calendario macro de las 7-8am
   python run_report.py                    # reporte diario + envía a Telegram
   python run_report.py --daily            # igual
   python run_report.py --daily --no-send  # solo genera, no envía

2. Alertas en tiempo real: noticias que van saliendo
   python run_report.py --breaking         # procesa noticias del momento
   python run_report.py --all              # ambos sistemas

Opciones:
   --no-reasoning   # desactiva razonamiento profundo (más rápido)
   --no-send        # solo genera, no envía a Telegram (dry-run)

Al inicio de cada ejecución, el agente revisa Telegram:
  - Procesa comandos del usuario (/add, /remove, /list, lenguaje natural, audios)
  - Si el usuario pidió /report o /breaking, ejecuta esa tarea también
"""
from __future__ import annotations

import sys
import os

# En Windows, la consola/redirección usa cp1252 por defecto y los emojis (📊, 🚨)
# provocan UnicodeEncodeError. Forzar UTF-8 para que no crashee.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from src.report import run_and_send, generate_daily_report, run_breaking_alerts


def _is_system1_window() -> bool:
    """
    True si la hora actual en NY está entre 7:00 y 8:59 AM.
    El Sistema 1 solo corre en esta ventana para ahorrar tokens.
    """
    try:
        from dateutil import tz
        from datetime import datetime
        ny_now = datetime.now(tz.gettz("America/New_York"))
        return 7 <= ny_now.hour <= 8
    except Exception:
        # Si no podemos determinar la zona horaria, dejar pasar (mejor ejecutar que fallar)
        return True


def main():
    reasoning = "--no-reasoning" not in sys.argv
    dry_run = "--no-send" in sys.argv
    do_breaking = "--breaking" in sys.argv or "--all" in sys.argv
    do_daily = "--daily" in sys.argv or "--all" in sys.argv or not do_breaking

    print("=" * 55)
    print("📊 AGENTE DE BÚSQUEDA FINANCIERA")
    print(f"   Razonamiento: {'SÍ' if reasoning else 'NO'}")
    print(f"   Sistema diario: {'SÍ' if do_daily else 'NO'}")
    print(f"   Alertas tiempo real: {'SÍ' if do_breaking else 'NO'}")
    print(f"   Envío Telegram: {'NO (dry-run)' if dry_run else 'SÍ'}")
    print("=" * 55)

    # ============================================================
    #  PASO 0: Revisar Telegram (comandos, lenguaje natural, audios)
    # ============================================================
    if not dry_run:
        try:
            from src.telegram_bot import process_commands, pop_trigger
            print("\n💬 Revisando Telegram...")
            n = process_commands()
            if n > 0:
                print(f"  ✅ {n} mensaje(s) procesado(s)")

            # ¿El usuario pidió ejecutar una tarea por Telegram?
            trigger = pop_trigger()
            if trigger == "report":
                do_daily = True
                print("  📅 Telegram solicitó reporte diario → ejecutando")
            elif trigger == "breaking":
                do_breaking = True
                print("  🚨 Telegram solicitó alertas → ejecutando")
        except Exception as e:
            print(f"  ⚠️ Error revisando Telegram: {e}")

    # ============================================================
    #  PASO 0b: Seguimiento de resultados (Sección 1)
    #  Revisa si eventos programados de la mañana ya tienen resultados reales
    #  y envía actualizaciones con el análisis basado en datos reales.
    # ============================================================
    if not dry_run:
        try:
            from src.results_tracker import run_results_tracking
            print("\n📊 Revisando seguimiento de resultados...")
            followed = run_results_tracking()
            if followed > 0:
                print(f"  ✅ {followed} seguimiento(s) de resultados enviados")
        except Exception as e:
            print(f"  ⚠️ Error en seguimiento de resultados: {e}")

    # ============================================================
    #  SISTEMA 1 — Reporte diario (calendario macro)
    # ============================================================
    if do_daily:
        print("\n" + "─" * 55)
        print("📅 SISTEMA 1 — Reporte diario (calendario macro)")
        print("─" * 55)

        # Guard de horario: solo 7-8 AM NY (no gastar tokens todo el día)
        if not _is_system1_window() and not dry_run:
            # Si fue disparado manualmente por Telegram (--no-send no está),
            # pero fuera de ventana → dejar correr (el usuario lo pidió)
            # Solo bloquear si fue trigger automático (cron)
            # Detectar: si do_breaking también está activo, fue --all o cron
            if do_breaking and "--all" not in sys.argv and "--daily" not in sys.argv:
                # Fue disparado por Telegram con /report → permitir
                pass
            else:
                print("⏰ Fuera de ventana (7-8 AM NY). Sistema 1 omitido para ahorrar tokens.")
                do_daily = False

    if do_daily:
        if dry_run:
            report_text, entries = generate_daily_report(reasoning=reasoning)
            print("\n" + "=" * 55)
            print("REPORTE DIARIO (dry-run — NO enviado)")
            print("=" * 55)
            print(report_text)
        else:
            run_and_send(reasoning=reasoning)

    # ============================================================
    #  SISTEMA 2 — Alertas en tiempo real (noticias del momento)
    # ============================================================
    if do_breaking:
        print("\n" + "─" * 55)
        print("🚨 SISTEMA 2 — Alertas en tiempo real")
        print("─" * 55)
        if dry_run:
            from src.report import fetch_news_sources, deduplicate, analyze_single
            from src.formatter import format_breaking_alert
            from src.config import load_config
            from src.watchlist import match_company, get_watchlist_min_score

            cfg = load_config()
            min_score = cfg.get("filter", {}).get("breaking_min_score", 70)
            wl_min_score = get_watchlist_min_score()

            items = fetch_news_sources()
            items = deduplicate(items)

            print(f"\nAnalizando {len(items)} noticias para alto impacto...")
            count = 0
            for item in items[:10]:
                company = match_company(item)
                threshold = wl_min_score if company else min_score
                analysis = analyze_single(item, reasoning=reasoning)
                if analysis and analysis.get("puede_mover_mercado") and analysis.get("confianza", 0) >= threshold:
                    count += 1
                    entry = {"item": item, "analysis": analysis}
                    print(f"\n{'='*55}")
                    print(format_breaking_alert(entry))

            print(f"\n📊 {count} noticias de alto impacto detectadas (de {min(10, len(items))} analizadas)")
        else:
            run_breaking_alerts(reasoning=reasoning)


if __name__ == "__main__":
    main()
