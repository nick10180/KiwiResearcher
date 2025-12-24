"""Fetch and normalize pages from a local Kiwix server.

This module provides a lightweight interface for retrieving HTML pages from a
Kiwix Serve instance and converting them into structured page documents with
plain text and extracted links. It avoids heavyweight dependencies by using the
standard library only, making it easy to run in minimal environments.
"""
from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from typing import List, Optional
from urllib.parse import quote, urljoin, urlparse, unquote
import re
import urllib.request


@dataclass
class PageLink:
    """A link found in a page."""

    target_url: str
    anchor_text: str
    target_title: Optional[str]


@dataclass
class PageDocument:
    """Structured representation of a Kiwix page."""

    title: str
    url: str
    html: str
    plain_text: str
    links: List[PageLink]

    @classmethod
    def from_html(cls, title: str, url: str, html: str) -> "PageDocument":
        parser = _PageParser(base_url=url)
        parser.feed(html)
        plain_text = parser.collapsed_text()
        links = parser.links
        return cls(title=title, url=url, html=html, plain_text=plain_text, links=links)


class _PageParser(HTMLParser):
    """Extracts text and links from HTML while skipping noise."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self._base_url = base_url
        self._skip_depth = 0
        self._text_parts: List[str] = []
        self.links: List[PageLink] = []
        self._link_stack: List[dict] = []

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "a":
            href = dict(attrs).get("href")
            self._link_stack.append({"href": href, "text": []})

    def handle_endtag(self, tag: str):
        if tag in {"script", "style"}:
            self._skip_depth = max(self._skip_depth - 1, 0)
            return
        if self._skip_depth:
            return
        if tag == "a" and self._link_stack:
            link_data = self._link_stack.pop()
            href = link_data.get("href")
            anchor_text = " ".join(link_data["text"]).strip()
            if href:
                full_url = urljoin(self._base_url, href)
                target_title = _extract_title_from_href(href)
                self.links.append(
                    PageLink(target_url=full_url, anchor_text=anchor_text, target_title=target_title)
                )

    def handle_data(self, data: str):
        if self._skip_depth:
            return
        stripped = data.strip()
        if not stripped:
            return
        self._text_parts.append(stripped)
        if self._link_stack:
            self._link_stack[-1]["text"].append(stripped)

    def collapsed_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._text_parts)).strip()


def _extract_title_from_href(href: str) -> Optional[str]:
    """Best-effort extraction of a page title from a Wikipedia-style href."""
    parsed = urlparse(href)
    path = parsed.path.lstrip("/")
    if not path:
        return None
    parts = path.split("/")
    if parts and parts[0].lower() == "wiki":
        parts = parts[1:]
    if not parts:
        return None
    raw_title = parts[-1]
    if not raw_title:
        return None
    decoded = unquote(raw_title)
    return decoded.replace("_", " ")


class KiwixFetcher:
    """Fetches pages from a Kiwix Serve instance."""

    def __init__(self, base_url: str, opener: Optional[urllib.request.OpenerDirector] = None, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._opener = opener or urllib.request.build_opener()

    def build_page_url(self, title: str) -> str:
        encoded_title = quote(title.replace(" ", "_"), safe="/:")
        return f"{self.base_url}/wiki/{encoded_title}"

    def fetch_html(self, title: str) -> tuple[str, str]:
        url = self.build_page_url(title)
        with self._opener.open(url, timeout=self.timeout) as response:  # type: ignore[call-arg]
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read().decode(charset, errors="replace")
        return url, html

    def fetch_page(self, title: str) -> PageDocument:
        url, html = self.fetch_html(title)
        return PageDocument.from_html(title=title, url=url, html=html)
