"""
Estado COMPARTIDO de alertas ya enviadas (una sola fuente de verdad).

Problema que resuelve: la nube olvidaba su memoria en cada ejecución (data/cache
está en .gitignore), por lo que repetía noticias.

Solución: guardar las firmas de lo ya enviado en `data/state/sent_alerts.json`,
que SÍ se rastrea en git. La nube (único emisor en modo cloud-only) lo lee y lo
escribe, sincronizándose por git. Así no repite entre ejecuciones.

Formato: { "firma_de_tokens": timestamp_unix, ... }. Se poda a 48h.

También guarda el GUARD del reporte diario (Sistema 1) en
`data/state/daily_report.json` ({ "date": "YYYY-MM-DD" } en hora de Nueva York)
para que, aunque el cron dispare varias veces en la ventana 7-8 AM NY, el
reporte diario salga UNA sola vez al día.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .config import BASE_DIR

STATE_DIR = Path(BASE_DIR) / "data" / "state"
STATE_FILE = STATE_DIR / "sent_alerts.json"
DAILY_FILE = STATE_DIR / "daily_report.json"
MAX_AGE_SEC = 48 * 3600
_GIT_TIMEOUT = 40


def _in_ci() -> bool:
    return bool(os.environ.get("GITHUB_ACTIONS"))


def _git(*args, timeout: int = _GIT_TIMEOUT):
    """Ejecuta un comando git en el repo. Devuelve CompletedProcess o None."""
    try:
        return subprocess.run(
            ["git", *args], cwd=BASE_DIR,
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return None


def _read_raw() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                if isinstance(d, dict):
                    return d
        except Exception:
            pass
    return {}


def _prune(d: dict) -> dict:
    cutoff = time.time() - MAX_AGE_SEC
    out = {}
    for k, v in d.items():
        try:
            if float(v) >= cutoff:
                out[k] = v
        except (TypeError, ValueError):
            continue
    return out


def _write(d: dict) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


# ============================================================
#  API pública
# ============================================================

def pull() -> None:
    """
    Antes de procesar: traer el estado más reciente.
    - En la nube: el checkout ya trae lo último → no hace nada.
    - En local: git pull (rebase, autostash) para recibir lo que envió la nube.
    """
    if _in_ci():
        return
    _git("pull", "--rebase", "--autostash", "--quiet", timeout=30)


def load_sent_signatures() -> set:
    """Devuelve el conjunto de firmas ya enviadas (últimas 48h)."""
    return set(_prune(_read_raw()).keys())


def record_and_sync(new_sigs: set) -> None:
    """
    Registra las nuevas firmas enviadas en el estado compartido y lo sincroniza
    por git (commit + push), tanto en local como en la nube.

    Estrategia sin conflictos de merge: en cada intento se relee el estado
    (incluyendo lo que haya traído git), se hace la UNIÓN con las nuevas firmas,
    se escribe, se commitea y se hace push. Si el push falla porque el remoto
    avanzó, se reintenta re-sincronizando.
    """
    if not new_sigs:
        return

    # Guardado local inmediato (aunque git falle, esta máquina no repetirá)
    merged = _prune(_read_raw())
    now = time.time()
    for s in new_sigs:
        merged.setdefault(s, now)
    _write(merged)

    # Configurar identidad de git en la nube
    if _in_ci():
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    for _ in range(3):
        # Integrar lo remoto primero
        _git("pull", "--rebase", "--autostash", "--quiet", timeout=30)
        # Re-unir por si el pull trajo firmas nuevas del otro emisor
        merged = _prune(_read_raw())
        for s in new_sigs:
            merged.setdefault(s, now)
        _write(merged)

        _git("add", "data/state/sent_alerts.json")
        commit = _git("commit", "-m", "estado: alertas enviadas (sync)")
        if commit is None:
            return
        if commit.returncode != 0:
            # Nada que commitear (sin cambios) → ya está sincronizado
            return
        push = _git("push")
        if push is not None and push.returncode == 0:
            return
        # push rechazado (remoto avanzó) → el loop reintenta con nuevo pull

    # Si tras los reintentos no se pudo pushear, el estado local igual quedó
    # guardado; se re-intentará en el próximo ciclo. No es fatal.


# ============================================================
#  GUARD DEL REPORTE DIARIO (Sistema 1) — una sola vez al día
# ============================================================

def _ny_today_str() -> str:
    """Fecha de hoy (YYYY-MM-DD) en hora de Nueva York."""
    try:
        from datetime import datetime
        from dateutil import tz
        return datetime.now(tz.gettz("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")


def daily_report_sent_today() -> bool:
    """
    ¿El reporte diario (Sistema 1) ya se envió hoy (hora NY)?

    Lee el guard compartido `data/state/daily_report.json`. Se usa para que,
    aunque el cron dispare varias veces en la ventana 7-8 AM NY, el reporte
    salga UNA sola vez al día. Antes de consultarlo conviene hacer pull() para
    traer el estado más reciente (en la nube el checkout ya lo trae).
    """
    if not DAILY_FILE.exists():
        return False
    try:
        with open(DAILY_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return isinstance(d, dict) and d.get("date") == _ny_today_str()
    except Exception:
        return False


def mark_daily_report_sent() -> None:
    """
    Marca el reporte diario como enviado hoy (hora NY) y sincroniza por git,
    para que ninguna ejecución posterior del cron lo repita el mismo día.
    """
    today = _ny_today_str()
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(DAILY_FILE, "w", encoding="utf-8") as f:
            json.dump({"date": today}, f, ensure_ascii=False)
    except Exception:
        return

    if _in_ci():
        _git("config", "user.name", "github-actions[bot]")
        _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    for _ in range(3):
        _git("pull", "--rebase", "--autostash", "--quiet", timeout=30)
        try:
            with open(DAILY_FILE, "w", encoding="utf-8") as f:
                json.dump({"date": today}, f, ensure_ascii=False)
        except Exception:
            return
        _git("add", "data/state/daily_report.json")
        commit = _git("commit", "-m", "estado: reporte diario enviado (guard)")
        if commit is None:
            return
        if commit.returncode != 0:
            return  # sin cambios que commitear
        push = _git("push")
        if push is not None and push.returncode == 0:
            return
        # push rechazado (remoto avanzó) → reintentar con nuevo pull
