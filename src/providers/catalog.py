"""
Catálogo preconfigurado de proveedores LLM y modelos recomendados.

El usuario solo tiene que: buscar el proveedor -> elegir -> pegar API key -> guardar.
El base_url y api_type ya vienen cargados para cada proveedor.
"""
from typing import Optional


# ============================================================
#  CATÁLOGO DE PROVEEDORES
#  Cada entrada ya trae todo menos la API key.
#  - api_type: "openai" (OpenAI-compatible) | "anthropic" | "gemini"
#  - key_env:  nombre de la variable de entorno donde va la API key
# ============================================================
CATALOG = [
    {
        "name": "OpenRouter",
        "api_type": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "logo": "🔀",
        "website": "https://openrouter.ai",
        "note": "Acceso a 300+ modelos con una sola key. Hermes 4, DeepSeek, Llama, etc.",
    },
    {
        "name": "OpenAI",
        "api_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "key_env": "OPENAI_API_KEY",
        "logo": "🟢",
        "website": "https://platform.openai.com",
        "note": "GPT-4o, GPT-4o-mini, o1, o3 y familia.",
    },
    {
        "name": "Anthropic",
        "api_type": "anthropic",
        "base_url": "",
        "key_env": "ANTHROPIC_API_KEY",
        "logo": "🟣",
        "website": "https://console.anthropic.com",
        "note": "Claude 3.5 Sonnet, Haiku, Opus.",
    },
    {
        "name": "Google Gemini",
        "api_type": "gemini",
        "base_url": "",
        "key_env": "GEMINI_API_KEY",
        "logo": "✨",
        "website": "https://aistudio.google.com",
        "note": "Gemini 2.0 Flash, Pro, etc. Tier gratuito disponible.",
    },
    {
        "name": "Groq",
        "api_type": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "logo": "⚡",
        "website": "https://console.groq.com",
        "note": "Inferencia ultra-rápida. Llama, Mixtral. Tier gratuito.",
    },
    {
        "name": "Together AI",
        "api_type": "openai",
        "base_url": "https://api.together.xyz/v1",
        "key_env": "TOGETHER_API_KEY",
        "logo": "🤝",
        "website": "https://api.together.xyz",
        "note": "Llama, Qwen, DeepSeek. Crédito gratuito de bienvenida.",
    },
    {
        "name": "DeepSeek",
        "api_type": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "key_env": "DEEPSEEK_API_KEY",
        "logo": "🐳",
        "website": "https://platform.deepseek.com",
        "note": "DeepSeek V3/R1. Muy barato, excelente razonamiento.",
    },
    {
        "name": "Mistral",
        "api_type": "openai",
        "base_url": "https://api.mistral.ai/v1",
        "key_env": "MISTRAL_API_KEY",
        "logo": "🌬️",
        "website": "https://console.mistral.ai",
        "note": "Mistral Large, Codestral. Tier gratuito.",
    },
    {
        "name": "Fireworks AI",
        "api_type": "openai",
        "base_url": "https://api.fireworks.ai/inference/v1",
        "key_env": "FIREWORKS_API_KEY",
        "logo": "🎆",
        "website": "https://fireworks.ai",
        "note": "Modelos open-source optimizados.",
    },
    {
        "name": "Cerebras",
        "api_type": "openai",
        "base_url": "https://api.cerebras.ai/v1",
        "key_env": "CEREBRAS_API_KEY",
        "logo": "🧠",
        "website": "https://cerebras.ai",
        "note": "Inferencia rapidísima con Llama.",
    },
    {
        "name": "Ollama (local)",
        "api_type": "openai",
        "base_url": "http://localhost:11434/v1",
        "key_env": "",
        "logo": "🦙",
        "website": "https://ollama.com",
        "note": "Modelos locales gratuitos. Requiere tener Ollama instalado y corriendo.",
    },
    {
        "name": "LM Studio (local)",
        "api_type": "openai",
        "base_url": "http://localhost:1234/v1",
        "key_env": "",
        "logo": "🖥️",
        "website": "https://lmstudio.ai",
        "note": "Servidor local de modelos. Requiere LM Studio corriendo.",
    },
]


# ============================================================
#  MODELOS RECOMENDADOS (curados)
#  Aparecen como accesos rápidos en el dashboard.
#  El resto de modelos se cargan dinámicamente vía API GET /models.
# ============================================================
RECOMMENDED_MODELS = [
    # --- Hermes 4 (de pago, con API del usuario) ---
    {
        "provider": "OpenRouter",
        "model": "nousresearch/hermes-4-14b",
        "label": "Hermes 4 14B",
        "logo": "🧠",
        "free": False,
        "note": "Razonamiento híbrido. Rápido y económico. Ideal por defecto.",
    },
    {
        "provider": "OpenRouter",
        "model": "nousresearch/hermes-4-70b",
        "label": "Hermes 4 70B",
        "logo": "🧠",
        "free": False,
        "note": "Más potencia de razonamiento. Balance calidad/precio.",
    },
    {
        "provider": "OpenRouter",
        "model": "nousresearch/hermes-4-405b",
        "label": "Hermes 4 405B",
        "logo": "🧠",
        "free": False,
        "note": "Máxima potencia. Coste más alto.",
    },
    # --- Top 3 gratuitos recomendados ---
    {
        "provider": "OpenRouter",
        "model": "deepseek/deepseek-r1:free",
        "label": "DeepSeek R1 (gratis)",
        "logo": "🐳",
        "free": True,
        "note": "Mejor razonamiento gratuito. Cade cadena de pensamiento.",
    },
    {
        "provider": "OpenRouter",
        "model": "google/gemini-2.0-flash-exp:free",
        "label": "Gemini 2.0 Flash (gratis)",
        "logo": "✨",
        "free": True,
        "note": "Rápido y capaz. Buen contexto.",
    },
    {
        "provider": "OpenRouter",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "label": "Llama 3.3 70B (gratis)",
        "logo": "🦙",
        "free": True,
        "note": "Potente modelo abierto de Meta.",
    },
]


def get_catalog_entry(provider_name: str) -> Optional[dict]:
    """Devuelve la entrada del catálogo para un proveedor por nombre."""
    for entry in CATALOG:
        if entry["name"].lower() == provider_name.lower():
            return entry
    return None


def search_catalog(query: str) -> list:
    """
    Busca proveedores en el catálogo por nombre (insensible a mayúsculas).
    Devuelve una lista de entradas que coinciden.
    """
    q = query.lower().strip()
    if not q:
        return CATALOG
    return [
        e for e in CATALOG
        if q in e["name"].lower() or q in e.get("note", "").lower()
    ]
