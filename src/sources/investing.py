"""
CNBC + MarketWatch — noticias financieras vía RSS.
Reemplaza a Investing.com (bloqueado por Cloudflare 403).

Estas son fuentes americanas de primera calidad, ideales para el mercado USA.
"""
from __future__ import annotations

import feedparser

from .base import BaseSource, NewsItem


class InvestingSource(BaseSource):
    """
    Mantiene el nombre 'investing' en config.yaml por compatibilidad,
    pero ahora scrapea CNBC + MarketWatch (fuentes USA confiables vía RSS).
    """
    name = "investing"
    display_name = "CNBC + MarketWatch"

    FEEDS = [
        # CNBC — mercados y economía (USA)
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",  # Markets
        "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",   # Economy
        # MarketWatch — titulares principales
        "http://feeds.marketwatch.com/marketwatch/topstories/",
    ]

    def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for url in self.FEEDS:
            items.extend(self._parse_feed(url))
        return items

    def _parse_feed(self, url: str) -> list[NewsItem]:
        try:
            d = feedparser.parse(url)
        except Exception:
            return []

        # Determinar nombre de fuente del feed
        feed_title = (d.feed.get("title") or "").lower()
        if "cnbc" in feed_title:
            source_name = "CNBC"
        elif "marketwatch" in feed_title:
            source_name = "MarketWatch"
        else:
            source_name = "CNBC"

        items: list[NewsItem] = []
        for entry in d.entries[:20]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or entry.get("id") or "").strip()
            if not title:
                continue
            published = entry.get("published") or entry.get("updated") or ""
            items.append(NewsItem(
                title=title,
                url=link,
                source=source_name,
                time=self._time_from_rfc(published),
                stars=0,
                country="🇺🇸",
                summary=(entry.get("summary") or "")[:300].strip(),
                raw={"published": published},
            ))
        return items

    @staticmethod
    def _time_from_rfc(rfc_str: str) -> str:
        if not rfc_str:
            return ""
        try:
            from dateutil import parser as dtp
            dt = dtp.parse(rfc_str)
            return dt.strftime("%H:%M")
        except Exception:
            return ""
