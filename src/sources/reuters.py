"""
Reuters + Associated Press — agencias de cable (las más rápidas y fiables).

Reuters y AP cerraron/limitaron sus RSS públicos, así que sus titulares se
obtienen vía Google News RSS filtrado por dominio (site:reuters.com / apnews.com)
y acotado al último día (when:1d). Es una vía estable y fresca.
"""
from __future__ import annotations

import re

import feedparser

from .base import BaseSource, NewsItem


class ReutersSource(BaseSource):
    name = "reuters"
    display_name = "Reuters / AP"

    # (etiqueta de fuente, feed de Google News RSS)
    FEEDS = [
        ("Reuters",
         "https://news.google.com/rss/search?q=site:reuters.com+when:1d+"
         "(markets+OR+stocks+OR+economy+OR+Fed+OR+earnings+OR+Nasdaq)"
         "&hl=en-US&gl=US&ceid=US:en"),
        ("Associated Press",
         "https://news.google.com/rss/search?q=site:apnews.com+when:1d+"
         "(markets+OR+stocks+OR+economy+OR+Fed+OR+earnings+OR+Nasdaq)"
         "&hl=en-US&gl=US&ceid=US:en"),
    ]

    def fetch(self) -> list[NewsItem]:
        items: list[NewsItem] = []
        for label, url in self.FEEDS:
            items.extend(self._parse_feed(label, url))
        return items

    def _parse_feed(self, label: str, url: str) -> list[NewsItem]:
        try:
            d = feedparser.parse(url)
        except Exception:
            return []

        items: list[NewsItem] = []
        for entry in d.entries[:15]:
            title = self._clean_title((entry.get("title") or "").strip())
            link = (entry.get("link") or entry.get("id") or "").strip()
            if not title:
                continue
            published = entry.get("published") or entry.get("updated") or ""
            items.append(NewsItem(
                title=title,
                url=link,
                source=label,
                time=self._time_from_rfc(published),
                stars=0,
                country="🇺🇸",
                summary=(entry.get("summary") or "")[:300].strip(),
                raw={"published": published},
            ))
        return items

    @staticmethod
    def _clean_title(title: str) -> str:
        """Google News añade ' - Reuters' al final del titular; lo quitamos."""
        # Quitar sufijo ' - Publisher' del final
        return re.sub(r"\s+-\s+[^-]+$", "", title).strip() or title

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
