"""
Generación de imagen profesional para las alertas de precio (matplotlib).
Tema oscuro tipo terminal financiera. Devuelve la ruta del PNG generado.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .config import CACHE_DIR

# Paleta (estilo terminal financiera oscura)
_BG = "#0d1117"
_PANEL = "#0d1117"
_GRID = "#222c3a"
_UP = "#2ebd85"      # verde
_DOWN = "#f6465d"    # rojo
_TXT = "#e6edf3"
_SUB = "#8b949e"


def _ny_now():
    try:
        from dateutil import tz
        return datetime.now(tz.gettz("America/New_York"))
    except Exception:
        return datetime.now()


def render_price_movers_image(movers: list, threshold: float,
                              name_by_ticker: dict | None = None) -> str | None:
    """
    movers: lista de tuplas (ticker, pct, price).
    Devuelve la ruta del PNG, o None si falla.
    El nombre de la empresa NO va en la imagen (va en el texto/caption),
    para que las barras queden limpias sin solapamientos.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Ordenar por MAGNITUD ascendente: el mayor movimiento queda arriba
        data = sorted(movers, key=lambda m: abs(float(m[1])))
        tickers = [m[0] for m in data]
        pcts = [float(m[1]) for m in data]
        prices = [float(m[2]) for m in data]
        n = len(data)
        if n == 0:
            return None

        fig_h = max(2.6, 0.72 * n + 1.9)
        fig, ax = plt.subplots(figsize=(8.5, fig_h), dpi=200)
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_PANEL)

        colors = [_UP if p >= 0 else _DOWN for p in pcts]
        ypos = list(range(n))
        ax.barh(ypos, pcts, color=colors, height=0.6, zorder=3, edgecolor="none")

        ax.axvline(0, color=_SUB, lw=1.1, zorder=2)

        ax.set_yticks(ypos)
        ax.set_yticklabels(tickers, color=_TXT, fontsize=13, fontweight="bold")
        ax.tick_params(axis="y", length=0, pad=8)
        ax.tick_params(axis="x", colors=_SUB, labelsize=9)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(_GRID)
        ax.grid(axis="x", color=_GRID, lw=0.7, zorder=0)

        xmax = (max((abs(p) for p in pcts), default=1) or 1) * 1.9
        ax.set_xlim(-xmax, xmax)
        ax.set_ylim(-0.7, n - 0.3)

        # Etiqueta corta al final de la barra: % + precio (sin nombre)
        off = xmax * 0.03
        for i, (p, pr) in enumerate(zip(pcts, prices)):
            signo = "+" if p >= 0 else ""
            etq = f"{signo}{p:.1f}%   ${pr:,.2f}"
            ha = "left" if p >= 0 else "right"
            ax.text(p + (off if p >= 0 else -off), i, etq,
                    va="center", ha=ha, color=_TXT, fontsize=11, fontweight="bold")

        # Título y subtítulo
        ny = _ny_now()
        fecha = ny.strftime("%d/%m/%Y · %H:%M ET")
        fig.text(0.02, 0.965, "MOVIMIENTOS FUERTES", color=_TXT,
                 fontsize=17, fontweight="bold", ha="left", va="top")
        fig.text(0.02, 0.915, f"Watchlist · {fecha} · umbral \u00b1{threshold:.0f}%",
                 color=_SUB, fontsize=10.5, ha="left", va="top")
        fig.text(0.98, 0.965, "AlphaBot", color=_UP, fontsize=13,
                 fontweight="bold", ha="right", va="top")

        ax.set_xlabel("% del día vs cierre anterior", color=_SUB, fontsize=9.5)

        plt.subplots_adjust(left=0.12, right=0.97, top=0.86, bottom=0.11)

        path = CACHE_DIR / "price_movers.png"
        fig.savefig(str(path), facecolor=_BG, bbox_inches="tight", pad_inches=0.35)
        plt.close(fig)
        return str(path)
    except Exception as e:
        print(f"  ⚠️ Error generando imagen de precios: {e}")
        return None
