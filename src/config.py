"""
Gestión de configuración.
- Lee/escribe config.yaml (puente entre dashboard y agente).
- Carga .env (API keys, Telegram).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# --- rutas base ---
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"
ENV_PATH = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
HISTORY_DIR = DATA_DIR / "history"

for d in (DATA_DIR, CACHE_DIR, HISTORY_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- configuración por defecto ---
DEFAULT_CONFIG: dict[str, Any] = {
    "active": {
        "provider": "OpenRouter",
        "model": "nousresearch/hermes-4-14b",
        "temperature": 0.3,
        "max_tokens": 1500,
        "reasoning": True,
    },
    "sources": {
        "forex_factory": {"enabled": True},
        "yahoo_calendar": {"enabled": True},
        "finviz_calendar": {"enabled": True},
        "investing": {"enabled": True},
        "yahoo_finance": {"enabled": True},
        "finviz": {"enabled": True},
        "bloomberg_rss": {"enabled": True},
    },
    "filter": {
        "min_stars": 2,
        "breaking_min_score": 70,
    },
    "failover": {
        "enabled": True,
        "providers": [],   # se llena desde config.yaml (Cerebras, Gemini, etc.)
    },
    "watchlist": {
        "enabled": True,
        "min_score_watchlist": 55,   # umbral reducido para empresas seguidas (normal 70)
        "companies": [
            {"ticker": "AAPL", "name": "Apple", "aliases": ["Apple Inc", "iPhone", "Tim Cook"]},
            {"ticker": "TSLA", "name": "Tesla", "aliases": ["Elon Musk"]},
            {"ticker": "NVDA", "name": "Nvidia", "aliases": []},
            {"ticker": "MSFT", "name": "Microsoft", "aliases": []},
            {"ticker": "AMZN", "name": "Amazon", "aliases": []},
            {"ticker": "META", "name": "Meta", "aliases": ["Facebook"]},
            {"ticker": "GOOGL", "name": "Google", "aliases": ["Alphabet"]},
        ],
    },
    "schedule": {
        "report_time": "08:00",
        "timezone": "America/New_York",
    },
    "telegram": {"parse_mode": "Markdown"},
    "language": "es",
}

_loaded = False


def load_env() -> None:
    """Carga el .env (siempre refresca para capturar cambios)."""
    load_dotenv(ENV_PATH, override=True)


def load_config() -> dict:
    """Lee config.yaml (merge con defaults)."""
    load_env()
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
        # merge superficial por secciones
        for k, v in user.items():
            if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                cfg[k] = {**cfg[k], **v}
            else:
                cfg[k] = v
    return cfg


def save_config(cfg: dict) -> None:
    """Escribe config.yaml."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)


def update_active(**kwargs) -> None:
    """Actualiza campos del bloque 'active' y guarda."""
    cfg = load_config()
    cfg["active"].update(kwargs)
    save_config(cfg)


def get_active() -> dict:
    return load_config().get("active", {})


def set_env_var(key: str, value: str) -> None:
    """Añade/actualiza una variable en el archivo .env."""
    load_env()
    lines = []
    if ENV_PATH.exists():
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    found = False
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        for line in lines:
            if line.strip().startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                found = True
            else:
                f.write(line)
        if not found:
            f.write(f"{key}={value}\n")
    os.environ[key] = value


def get_env(key: str, default: str = "") -> str:
    load_env()
    return os.environ.get(key, default)
