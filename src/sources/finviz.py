"""
Finviz — noticias financieras.
Scraping del listado: https://finviz.com/news.ashx

La estructura HTML cambia con frecuencia. Aquí usamos selectores flexibles
que prueban varias clases conocidas y, como respaldo, un regex sobre los
enlaces con clase nn-tab-link.
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup

from .base import BaseSource, NewsItem

FINVIZ_URL = "https://finviz.com/news.ashx"


class FinvizSource(BaseSource):
    name = "finviz"
    display_name = "Finviz"

    def fetch(self) -> list[NewsItem]:
        raw = self._get(FINVIZ_URL)
        if not raw:
            return []
        soup = BeautifulSoup(raw, "lxml")
        items: list[NewsItem] = []

        # Selectores CSS modernos de Finviz (Jul 2026):
        # Cada fila tiene clase news_table-row y un <a class="nn-tab-link">
        rows = soup.select("tr.news_table-row")
        if not rows:
            # respaldo más amplio: cualquier fila que contenga nn-tab-link
            rows = soup.select("tr:has(a.nn-tab-link)")

        for row in rows[:25]:
            try:
                link = row.select_one("a.nn-tab-link") or row.find("a", href=True)
                if not link:
                    continue
                title = (link.get_text(strip=True) or "").strip()
                url = link.get("href", "")
                if not title or "mailto:" in url:
                    continue

                # hora: celda news_date-cell
                time_el = row.select_one("td.news_date-cell") or row.select_one("td.news_first-time-cell")
                time_str = time_el.get_text(strip=True) if time_el else ""

                # fuente: a veces viene del onclick o del icono svg
                source_name = "Finviz"
                onclick = row.get("onclick", "")
                m = re.search(r"trackAndOpenNews\([^,]+,\s*\d+,\s*'([^']+)'", onclick)
                if m:
                    external_url = m.group(1)
                    # extraer dominio
                    dom = re.search(r"https?://(?:www\.)?([^/]+)", external_url)
                    if dom:
                        source_name = dom.group(1).replace(".com", "").title()

                items.append(NewsItem(
                    title=title,
                    url=url if url.startswith("http") else f"https://finviz.com/{url}",
                    source=f"Finviz · {source_name}",
                    time=time_str,
                    stars=0,
                    country="🇺🇸",
                    raw={"html_source": source_name},
                ))
            except Exception:
                continue
        return items
