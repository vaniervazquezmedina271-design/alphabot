"""
Sistema de backup automático.
Guarda TODO lo que el agente genera por si hay algún problema:
  - Reportes diarios (texto + JSON)
  - Alertas enviadas a Telegram
  - Comandos recibidos por Telegram
  - Cambios en la watchlist
  - Estado de cada ejecución (log)

Todo se guarda en data/backup/ con fecha y hora.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import BASE_DIR, CACHE_DIR, HISTORY_DIR

BACKUP_DIR = BASE_DIR / "data" / "backup"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def _ny_now() -> datetime:
    """Hora actual en Nueva York (para nombrar archivos consistentemente)."""
    try:
        from dateutil import tz
        return datetime.now(tz.gettz("America/New_York"))
    except Exception:
        return datetime.now()


def _timestamp() -> str:
    """Timestamp para nombrar archivos: YYYY-MM-DD_HH-MM-SS"""
    return _ny_now().strftime("%Y-%m-%d_%H-%M-%S")


def save_report_backup(report_text: str, entries: list[dict]) -> Path:
    """
    Guarda un reporte diario generado (texto + JSON).
    Devuelve la ruta del archivo .txt guardado.
    """
    ts = _timestamp()
    txt_path = BACKUP_DIR / f"report_{ts}.txt"
    json_path = BACKUP_DIR / f"report_{ts}.json"

    try:
        txt_path.write_text(report_text, encoding="utf-8")
        json_path.write_text(
            json.dumps(
                [{"item": e["item"].to_dict(), "analysis": e["analysis"]} for e in entries],
                ensure_ascii=False, indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  💾 Reporte guardado en backup: {txt_path.name}")
    except Exception as e:
        print(f"  ⚠️ Error guardando backup de reporte: {e}")

    return txt_path


def save_alert_backup(item_dict: dict, analysis: dict, alert_text: str) -> Path:
    """
    Guarda una alerta enviada a Telegram.
    Devuelve la ruta del archivo guardado.
    """
    ts = _timestamp()
    path = BACKUP_DIR / f"alert_{ts}.txt"
    json_path = BACKUP_DIR / f"alert_{ts}.json"

    try:
        path.write_text(alert_text, encoding="utf-8")
        json_path.write_text(
            json.dumps({"item": item_dict, "analysis": analysis}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"  ⚠️ Error guardando backup de alerta: {e}")

    return path


def save_telegram_log(message: str, response: str) -> None:
    """Guarda un registro de comandos recibidos por Telegram y sus respuestas."""
    ts = _timestamp()
    today = _ny_now().strftime("%Y-%m-%d")
    log_path = BACKUP_DIR / f"telegram_log_{today}.txt"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n[{ts}] USUARIO: {message}\n")
            f.write(f"[{ts}] AGENTE: {response}\n")
            f.write("─" * 40 + "\n")
    except Exception:
        pass


def save_execution_log(log_text: str) -> None:
    """Guarda el log completo de una ejecución del agente."""
    ts = _timestamp()
    today = _ny_now().strftime("%Y-%m-%d")
    log_path = BACKUP_DIR / f"execution_{today}.log"

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*55}\n")
            f.write(f"EJECUCIÓN: {ts}\n")
            f.write(f"{'='*55}\n")
            f.write(log_text)
            f.write("\n")
    except Exception:
        pass


def backup_config() -> None:
    """Hace una copia de seguridad de config.yaml (por si se corrompe)."""
    from .config import CONFIG_PATH
    ts = _timestamp()
    backup_path = BACKUP_DIR / f"config_backup_{ts}.yaml"
    try:
        if CONFIG_PATH.exists():
            shutil.copy2(CONFIG_PATH, backup_path)
    except Exception:
        pass


def cleanup_old_backups(days: int = 30) -> int:
    """
    Borra backups más antiguos de N días para no llenar el disco.
    Devuelve cuántos archivos borró.
    """
    cutoff = datetime.now().timestamp() - (days * 86400)
    deleted = 0
    for f in BACKUP_DIR.glob("*"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except Exception:
            pass
    return deleted


def list_backups(limit: int = 20) -> list[dict]:
    """Lista los backups recientes para mostrar en el dashboard."""
    files = sorted(BACKUP_DIR.glob("*"), key=lambda f: f.stat().st_mtime, reverse=True)
    result = []
    for f in files[:limit]:
        stat = f.stat()
        result.append({
            "name": f.name,
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "type": f.suffix.lstrip("."),
        })
    return result
