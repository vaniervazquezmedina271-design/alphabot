"""Capa de proveedores LLM (multi-proveedor, agnóstica)."""
from .base import LLMProvider, get_provider
from .catalog import CATALOG, get_catalog_entry, RECOMMENDED_MODELS

__all__ = ["LLMProvider", "get_provider", "CATALOG", "get_catalog_entry", "RECOMMENDED_MODELS"]
