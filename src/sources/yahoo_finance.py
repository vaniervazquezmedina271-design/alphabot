"""
Yahoo Finance — noticias financieras vía RSS.
"""
from __future__ import annotations

import feedparser
from typing import Optional

from .base import BaseSource, NewsItem


class YahooFinanceSource(BaseSource):
    name = "yahoo_finance"
    display_name = "Yahoo Finance"

    FEEDS = [
        "https://finance.yahoo.com/news/rssindex",
        "https://finance.yahoo.com/news/category/markets/rssindex",
        "https://finance.yahoo.com/news/category/economy/rssindex",
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
                source="Yahoo Finance",
                time=self._time_from_rfc(published),
                stars=0,
                country="🌍",
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
