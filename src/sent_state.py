"""
Estado COMPARTIDO de alertas ya enviadas (una sola fuente de verdad).

Problema que resuelve: el bot local (PC) y la nube (GitHub Actions) enviaban
alertas por separado y la nube olvidaba su memoria en cada ejecución (data/cache
está en .gitignore), por lo que repetía noticias.

Solución: guardar las firmas de lo ya enviado en `data/state/sent_alerts.json`,
que SÍ se rastrea en git. Local y nube lo leen y lo escriben, sincronizándose por
git. Así ninguno repite, corran juntos o por separado.

Formato: { "firma_de_tokens": timestamp_unix, ... }. Se poda a 48h.
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
