"""
Bloomberg — noticias vía RSS (esquiva el paywall).
"""
from __future__ import annotations

import feedparser

from .base import BaseSource, NewsItem


class BloombergRSSSource(BaseSource):
    name = "bloomberg_rss"
    display_name = "Bloomberg (RSS)"

    FEEDS = [
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.bloomberg.com/economics/news.rss",
        "https://feeds.bloomberg.com/politics/news.rss",
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
        for entry in d.entries[:15]:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or entry.get("id") or "").strip()
            if not title:
                continue
            published = entry.get("published") or entry.get("updated") or ""
            items.append(NewsItem(
                title=title,
                url=link,
                source="Bloomberg",
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
