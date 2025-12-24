"""Basic breadth-first crawler for Kiwix pages."""
from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
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
    edges: List[tuple[str, str]] = field(default_factory=list)
    log: List[str] = field(default_factory=list)


class BasicCrawler:
    """Breadth-first crawler limited by depth and page count."""

    def __init__(self, fetcher: KiwixFetcher, settings: CrawlSettings | None = None):
        self.fetcher = fetcher
        self.settings = settings or CrawlSettings()

    def crawl(self, seed_titles: Iterable[str]) -> CrawlResult:
        queue: deque[tuple[str, int]] = deque((title, 0) for title in seed_titles)
        result = CrawlResult()

        for seed in seed_titles:
            result.log.append(f"Seeded queue with '{seed}' at depth 0")

        while queue and len(result.pages) < self.settings.max_pages:
            title, depth = queue.popleft()
            if title in result.visited_titles:
                result.log.append(f"Skipped already visited '{title}'")
                continue
            if depth > self.settings.max_depth:
                result.log.append(f"Skipped '{title}' beyond max depth {self.settings.max_depth}")
                continue

            page = self.fetcher.fetch_page(title)
            result.pages.append(page)
            result.visited_titles.add(title)
            result.log.append(f"Fetched '{title}' at depth {depth}")

            if depth == self.settings.max_depth:
                continue

            for link in page.links:
                next_title = link.target_title or self._derive_title_from_url(link)
                if not next_title or next_title in result.visited_titles:
                    continue
                queue.append((next_title, depth + 1))
                result.edges.append((title, next_title))
                result.log.append(
                    f"Queued '{next_title}' from '{title}' for depth {depth + 1}"
                )

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


def save_crawl_outputs(result: CrawlResult, output_dir: str | Path) -> None:
    """Persist corpus, graph, and crawl log to disk.

    The corpus is stored as JSON Lines (corpus.jsonl), graph as graph.json,
    and the textual crawl log as run.log. Directories are created as needed.
    """

    base_path = Path(output_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    corpus_path = base_path / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as corpus_file:
        for page in result.pages:
            record = {
                "title": page.title,
                "url": page.url,
                "plain_text": page.plain_text,
                "links": [
                    {
                        "target_url": link.target_url,
                        "anchor_text": link.anchor_text,
                        "target_title": link.target_title,
                    }
                    for link in page.links
                ],
            }
            corpus_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    graph = {
        "nodes": [{"title": page.title, "url": page.url} for page in result.pages],
        "edges": [
            {"source": source, "target": target} for source, target in result.edges
        ],
    }
    graph_path = base_path / "graph.json"
    graph_path.write_text(json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = base_path / "run.log"
    log_path.write_text("\n".join(result.log), encoding="utf-8")
