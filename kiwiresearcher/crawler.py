"""Basic breadth-first crawler for Kiwix pages."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Iterable, List, Set

from .kiwix_fetcher import KiwixFetcher, PageDocument, PageLink


@dataclass
class CrawlSettings:
    """Settings controlling crawl expansion."""

    max_depth: int = 1
    max_pages: int = 10


@dataclass
class CrawlResult:
    """Result of a crawl run."""

    pages: List[PageDocument] = field(default_factory=list)
    visited_titles: Set[str] = field(default_factory=set)


class BasicCrawler:
    """Breadth-first crawler limited by depth and page count."""

    def __init__(self, fetcher: KiwixFetcher, settings: CrawlSettings | None = None):
        self.fetcher = fetcher
        self.settings = settings or CrawlSettings()

    def crawl(self, seed_titles: Iterable[str]) -> CrawlResult:
        queue: deque[tuple[str, int]] = deque((title, 0) for title in seed_titles)
        result = CrawlResult()

        while queue and len(result.pages) < self.settings.max_pages:
            title, depth = queue.popleft()
            if title in result.visited_titles:
                continue
            if depth > self.settings.max_depth:
                continue

            page = self.fetcher.fetch_page(title)
            result.pages.append(page)
            result.visited_titles.add(title)

            if depth == self.settings.max_depth:
                continue

            for link in page.links:
                next_title = link.target_title or self._derive_title_from_url(link)
                if not next_title or next_title in result.visited_titles:
                    continue
                queue.append((next_title, depth + 1))

        return result

    @staticmethod
    def _derive_title_from_url(link: PageLink) -> str | None:
        # Fallback to extracting from URL path if target_title is absent
        if not link.target_url:
            return None
        # A simple heuristic: take trailing path segment
        parts = link.target_url.rstrip("/").split("/")
        if not parts:
            return None
        candidate = parts[-1].replace("_", " ")
        return candidate or None
