"""
Watchlist de empresas — gestión y matching.

El usuario gestiona su lista de empresas seguidas por Telegram (/add, /remove, /list).
La watchlist se guarda en config.yaml y se commitea al repo en GitHub Actions
para que persista entre ejecuciones.

Cuando el Sistema 2 busca noticias, las que mencionan una empresa de la watchlist
reciben prioridad: se analizan primero y con un umbral de confianza más bajo
(55 en vez de 70), porque el usuario las considera importantes.
"""
from __future__ import annotations

import os
import subprocess
from typing import Optional

from .config import load_config, save_config, BASE_DIR


# ============================================================
#  DICCIONARIO NOMBRE → TICKER (para lenguaje natural)
#  Amplio: cubre las empresas más conocidas del S&P 500 + índices
# ============================================================

NAME_TO_TICKER: dict[str, tuple[str, str, list[str]]] = {
    # --- Big Tech ---
    "apple": ("AAPL", "Apple", ["iPhone", "Tim Cook", "MacBook"]),
    "microsoft": ("MSFT", "Microsoft", ["Satya Nadella", "Windows", "Azure"]),
    "tesla": ("TSLA", "Tesla", ["Elon Musk", "Model 3", "Model Y", "Cybertruck"]),
    "nvidia": ("NVDA", "Nvidia", ["Jensen Huang", "GeForce"]),
    "amazon": ("AMZN", "Amazon", ["AWS", "Jeff Bezos", "Prime"]),
    "google": ("GOOGL", "Alphabet", ["YouTube", "Sundar Pichai", "Android"]),
    "alphabet": ("GOOGL", "Alphabet", ["YouTube", "Google"]),
    "meta": ("META", "Meta Platforms", ["Facebook", "Instagram", "Zuckerberg", "WhatsApp"]),
    "facebook": ("META", "Meta Platforms", ["Zuckerberg", "Instagram"]),
    "netflix": ("NFLX", "Netflix", []),
    # --- Finanzas ---
    "jpmorgan": ("JPM", "JPMorgan Chase", ["Jamie Dimon", "Chase"]),
    "chase": ("JPM", "JPMorgan Chase", ["Jamie Dimon"]),
    "bank of america": ("BAC", "Bank of America", ["BofA"]),
    "goldman sachs": ("GS", "Goldman Sachs", []),
    "morgan stanley": ("MS", "Morgan Stanley", []),
    "visa": ("V", "Visa", []),
    "mastercard": ("MA", "Mastercard", []),
    "wells fargo": ("WFC", "Wells Fargo", []),
    "blackrock": ("BLK", "Blackrock", []),
    # --- Salud ---
    "johnson": ("JNJ", "Johnson & Johnson", ["J&J"]),
    "pfizer": ("PFE", "Pfizer", []),
    "unitedhealth": ("UNH", "UnitedHealth Group", []),
    "eli lilly": ("LLY", "Eli Lilly", []),
    "abbvie": ("ABBV", "AbbVie", []),
    "merck": ("MRK", "Merck", []),
    # --- Consumo ---
    "coca cola": ("KO", "Coca-Cola", ["Coke"]),
    "cocacola": ("KO", "Coca-Cola", ["Coke"]),
    "pepsi": ("PEP", "PepsiCo", []),
    "mcdonalds": ("MCD", "McDonald's", []),
    "starbucks": ("SBUX", "Starbucks", []),
    "nike": ("NKE", "Nike", []),
    "walmart": ("WMT", "Walmart", []),
    "costco": ("COST", "Costco", []),
    "home depot": ("HD", "Home Depot", []),
    "disney": ("DIS", "Walt Disney", ["Marvel", "ESPN"]),
    # --- Energía ---
    "exxon": ("XOM", "Exxon Mobil", []),
    "chevron": ("CVX", "Chevron", []),
    "shell": ("SHEL", "Shell", []),
    # --- Industriales/Tech ---
    "boeing": ("BA", "Boeing", []),
    "caterpillar": ("CAT", "Caterpillar", []),
    "salesforce": ("CRM", "Salesforce", []),
    "oracle": ("ORCL", "Oracle", []),
    "adobe": ("ADBE", "Adobe", []),
    "cisco": ("CSCO", "Cisco", []),
    "intel": ("INTC", "Intel", []),
    "amd": ("AMD", "Advanced Micro Devices", []),
    "qualcomm": ("QCOM", "Qualcomm", []),
    "broadcom": ("AVGO", "Broadcom", []),
    "tesla motors": ("TSLA", "Tesla", ["Elon Musk"]),
    "uber": ("UBER", "Uber", []),
    "airbnb": ("ABNB", "Airbnb", []),
    "coinbase": ("COIN", "Coinbase", []),
    "palantir": ("PLTR", "Palantir", []),
    "shopify": ("SHOP", "Shopify", []),
    # --- Índices (ETFs) ---
    "sp500": ("SPY", "S&P 500 ETF", ["SPY", "S&P"]),
    "s&p": ("SPY", "S&P 500 ETF", ["SPY"]),
    "spdr": ("SPY", "S&P 500 ETF", []),
    "nasdaq": ("QQQ", "Nasdaq 100 ETF", ["QQQ"]),
    "dow": ("DIA", "Dow Jones ETF", ["DIA", "Dow Jones"]),
    "dow jones": ("DIA", "Dow Jones ETF", ["DJIA"]),
    "russell": ("IWM", "Russell 2000 ETF", ["IWM"]),
    "vix": ("VIX", "Volatility Index", ["Fear Index"]),
    # --- Cripto ---
    "bitcoin": ("BTC", "Bitcoin", ["BTC"]),
    "ethereum": ("ETH", "Ethereum", ["ETH"]),
}


def resolve_ticker(text: str) -> tuple[str, str, list[str]] | None:
    """
    Resuelve un nombre o ticker de empresa a su forma canónica.
    Busca en el diccionario NAME_TO_TICKER por nombre, alias o ticker.
    Devuelve (ticker, name, aliases) o None si no encuentra.
    """
    lower = text.lower().strip()
    if not lower:
        return None

    # 1. ¿Es un ticker directo conocido? (ej: "AAPL")
    for name, (ticker, comp_name, aliases) in NAME_TO_TICKER.items():
        if lower == ticker.lower():
            return (ticker, comp_name, aliases)

    # 2. ¿Es un nombre conocido? (ej: "apple", "jpmorgan", "coca cola")
    # Buscar coincidencia exacta primero, luego por inclusión
    for name, (ticker, comp_name, aliases) in NAME_TO_TICKER.items():
        if lower == name:
            return (ticker, comp_name, aliases)
    # Luego buscar si el nombre está contenido en el texto (o viceversa)
    for name, (ticker, comp_name, aliases) in NAME_TO_TICKER.items():
        if name in lower or lower in name:
            return (ticker, comp_name, aliases)

    # 3. Buscar en aliases
    for name, (ticker, comp_name, aliases) in NAME_TO_TICKER.items():
        for alias in aliases:
            if alias.lower() in lower:
                return (ticker, comp_name, aliases)

    return None


# ============================================================
#  CARGA Y GUARDADO
# ============================================================

def load_watchlist() -> list[dict]:
    """Devuelve la lista de empresas seguidas desde config.yaml."""
    cfg = load_config()
    wl = cfg.get("watchlist", {})
    if not wl.get("enabled", True):
        return []
    return wl.get("companies", [])


def _save_watchlist(companies: list[dict]) -> None:
    """Guarda la lista actualizada en config.yaml."""
    cfg = load_config()
    cfg.setdefault("watchlist", {})
    cfg["watchlist"]["companies"] = companies
    save_config(cfg)
    # En GitHub Actions, commitear para que persista entre runs
    _commit_if_ci()


def _commit_if_ci() -> None:
    """Si corre en GitHub Actions, commitea config.yaml para que persista."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"],
                       check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
                       check=True, capture_output=True)
        subprocess.run(["git", "add", "config.yaml"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "📝 Watchlist actualizada por Telegram"],
                       check=True, capture_output=True)
        subprocess.run(["git", "push"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass  # nada que commitear o error de red — no es crítico


# ============================================================
#  GESTIÓN (usado por los comandos de Telegram)
# ============================================================

def add_company(ticker_or_name: str, name: str = "", aliases: list[str] | None = None) -> str:
    """
    Añade una empresa a la watchlist.
    Acepta ticker (AAPL) o nombre (Apple) — resuelve automáticamente.
    name: nombre legible opcional (si no se da, se infiere del diccionario)
    aliases: nombres alternativos para matching (se añaden a los del diccionario)
    Devuelve mensaje de confirmación para Telegram.
    """
    raw = ticker_or_name.strip()
    if not raw:
        return "❌ Especifica un ticker o nombre. Ej: /add AAPL o /add Apple"

    # Resolver nombre → ticker usando el diccionario
    resolved = resolve_ticker(raw)
    if resolved:
        ticker, dict_name, dict_aliases = resolved
        # Si el usuario no dio nombre, usar el del diccionario
        if not name:
            name = dict_name
        # Combinar aliases del diccionario con los del usuario
        user_aliases = [a.strip() for a in aliases if a.strip()] if aliases else []
        aliases = list(set(dict_aliases + user_aliases))
    else:
        # No está en el diccionario → usar como ticker directo
        ticker = raw.upper()
        if not name:
            name = ticker

    companies = load_watchlist()

    # ¿Ya existe?
    for c in companies:
        if c["ticker"].upper() == ticker:
            return f"⚠️ {ticker} ya está en tu watchlist."

    entry = {
        "ticker": ticker,
        "name": name.strip() if name else ticker,
        "aliases": [a.strip() for a in aliases if a.strip()] if aliases else [],
    }
    companies.append(entry)
    _save_watchlist(companies)

    alias_str = f" (aliases: {', '.join(entry['aliases'])})" if entry["aliases"] else ""
    return f"✅ Añadida: {ticker} — {entry['name']}{alias_str}"


def remove_company(ticker_or_name: str) -> str:
    """
    Quita una empresa de la watchlist.
    Acepta ticker (AAPL) o nombre (Apple) — resuelve automáticamente.
    Devuelve mensaje de confirmación.
    """
    raw = ticker_or_name.strip()
    if not raw:
        return "❌ Especifica un ticker o nombre. Ej: /remove AAPL o /remove Apple"

    # Resolver nombre → ticker
    resolved = resolve_ticker(raw)
    ticker = resolved[0] if resolved else raw.upper()

    companies = load_watchlist()

    # Buscar por ticker O por nombre
    new_list = []
    found_ticker = None
    for c in companies:
        if c["ticker"].upper() == ticker.upper():
            found_ticker = c["ticker"]
            continue
        # También buscar por nombre (ej: quitar "Apple" encuentra AAPL)
        if c.get("name", "").lower() == raw.lower():
            found_ticker = c["ticker"]
            continue
        new_list.append(c)

    if found_ticker is None:
        return f"⚠️ {raw} no estaba en tu watchlist."

    _save_watchlist(new_list)
    return f"✅ Quitada: {found_ticker}"


def list_companies() -> str:
    """Devuelve texto formateado con la watchlist para Telegram."""
    companies = load_watchlist()
    if not companies:
        return "📋 Tu watchlist está vacía.\nUsa /add TICKER Nombre,alias1 para añadir empresas."

    lines = [f"📋 *Watchlist* ({len(companies)} empresas):\n"]
    for c in companies:
        alias_str = ""
        if c.get("aliases"):
            alias_str = f" — _{', '.join(c['aliases'])}_"
        lines.append(f"• `{c['ticker']}` {c.get('name', c['ticker'])}{alias_str}")

    lines.append(f"\nUmbral de alerta: {get_watchlist_min_score()}% (normal: 70%)")
    return "\n".join(lines)


def get_watchlist_min_score() -> int:
    """Umbral reducido para alertas de empresas en watchlist."""
    return load_config().get("watchlist", {}).get("min_score_watchlist", 55)


# ============================================================
#  MATCHING (¿la noticia menciona una empresa de la watchlist?)
# ============================================================

# Tickers que también son palabras comunes en inglés/español.
# Para estos NO se busca el ticker "a pelo" (daría falsos positivos como
# "now", "low", "spy", "coin", "meta"...). Solo se detectan por nombre o alias.
COMMON_WORD_TICKERS = {
    "now", "low", "c", "v", "ma", "dia", "spy", "coin", "meta",
    "uso", "all", "on", "it", "are", "so", "hd", "mu",
}

# ETFs de materias primas / apalancados con alias genéricos (oil, gold, silver,
# uranium, semiconductor, small caps). Estos alias generan mucho ruido, así que
# a las noticias que matchean SOLO por estos se les exige más confianza.
NOISY_ETF_TICKERS = {"USO", "SLV", "GLD", "URA", "SOXL", "TNA"}


def is_noisy_etf(ticker: str) -> bool:
    """True si el ticker es un ETF de materia prima/apalancado con alias genéricos."""
    return (ticker or "").upper() in NOISY_ETF_TICKERS


def match_company(item) -> Optional[dict]:
    """
    ¿La noticia menciona alguna empresa de la watchlist?
    Busca ticker, nombre y aliases en el título y resumen.

    Para tickers que son palabras comunes (NOW, LOW, C, V, MA, SPY, COIN,
    META, USO...) NO se busca el ticker suelto, solo el nombre/alias, para
    evitar falsos positivos.

    Devuelve la empresa encontrada (dict) o None.
    """
    companies = load_watchlist()
    if not companies:
        return None

    # Buscar SOLO en el TÍTULO (el sujeto real de la noticia).
    # El resumen suele traer menciones de pasada (ej. "Elon Musk", "Dow Jones
    # consensus", "Nasdaq-100") que colaban noticias ajenas a la watchlist.
    # Además se exige coincidencia por PALABRA COMPLETA (no subcadena).
    title = (getattr(item, "title", "") or "").lower()
    if not title.strip():
        return None

    for c in companies:
        ticker = c["ticker"].lower()
        name = (c.get("name") or "").lower()
        aliases = [a.lower() for a in c.get("aliases", [])]

        # 1. Ticker como palabra completa (solo si no es palabra común ambigua)
        if ticker not in COMMON_WORD_TICKERS and len(ticker) >= 2:
            if _word_match(title, ticker):
                return c

        # 2. Nombre y aliases como PALABRA COMPLETA en el título
        for kw in [name] + aliases:
            if kw and len(kw) >= 3 and _word_match(title, kw):
                return c

    return None


def _word_match(text: str, word: str) -> bool:
    """Busca 'word' en 'text' como palabra completa (no subcadena)."""
    import re
    # \b funciona para letras, pero los tickers pueden tener números
    pattern = rf"\b{re.escape(word)}\b"
    return bool(re.search(pattern, text, re.IGNORECASE))


# ============================================================
#  CONTEXTO PARA EL LLM
# ============================================================

def get_watchlist_prompt_context() -> str:
    """
    Genera texto para añadir al system prompt del LLM:
    'El usuario sigue de cerca: AAPL (Apple), TSLA (Tesla), ...'
    Así el LLM presta atención especial a estas empresas.
    """
    companies = load_watchlist()
    if not companies:
        return ""

    items = []
    for c in companies:
        ticker = c["ticker"]
        name = c.get("name", ticker)
        aliases = c.get("aliases", [])
        if aliases:
            items.append(f"{ticker} ({name}, también conocido como: {', '.join(aliases)})")
        else:
            items.append(f"{ticker} ({name})")

    return (
        "\n\n## EMPRESAS DE INTERÉS DEL USUARIO\n"
        "El usuario sigue de cerca estas empresas. Presta especial atención a "
        "noticias que las mencionen y considéralas de mayor impacto:\n"
        + ", ".join(items) + "\n"
    )
