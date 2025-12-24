import json

import kiwiresearcher.crawler as crawler
from kiwiresearcher.kiwix_fetcher import PageDocument, PageLink


class FakeFetcher:
    def __init__(self, pages_by_title):
        self.pages_by_title = pages_by_title
        self.requested = []

    def fetch_page(self, title):
        self.requested.append(title)
        return self.pages_by_title[title]


def make_page(title, links):
    return PageDocument(
        title=title,
        url=f"http://example.com/wiki/{title}",
        html="<html></html>",
        plain_text=title,
        links=links,
    )


def test_crawler_respects_depth_and_max_pages():
    pages = {
        "Root": make_page(
            "Root",
            [
                PageLink(target_url="http://example.com/wiki/A", anchor_text="A", target_title="A"),
                PageLink(target_url="http://example.com/wiki/B", anchor_text="B", target_title="B"),
            ],
        ),
        "A": make_page(
            "A",
            [PageLink(target_url="http://example.com/wiki/C", anchor_text="C", target_title="C")],
        ),
        "B": make_page(
            "B",
            [PageLink(target_url="http://example.com/wiki/D", anchor_text="D", target_title="D")],
        ),
        "C": make_page("C", []),
        "D": make_page("D", []),
    }

    fetcher = FakeFetcher(pages)
    settings = crawler.CrawlSettings(max_depth=1, max_pages=3)
    basic = crawler.BasicCrawler(fetcher, settings)

    result = basic.crawl(["Root"])

    # Should visit Root plus only two more pages due to max_pages
    assert [page.title for page in result.pages] == ["Root", "A", "B"]
    assert set(result.visited_titles) == {"Root", "A", "B"}
    assert "C" not in result.visited_titles


def test_crawler_avoids_revisiting_titles():
    pages = {
        "Root": make_page(
            "Root",
            [
                PageLink(target_url="http://example.com/wiki/A", anchor_text="A", target_title="A"),
                PageLink(target_url="http://example.com/wiki/A", anchor_text="A2", target_title="A"),
            ],
        ),
        "A": make_page("A", []),
    }

    fetcher = FakeFetcher(pages)
    basic = crawler.BasicCrawler(fetcher, crawler.CrawlSettings(max_depth=2, max_pages=5))

    result = basic.crawl(["Root"])

    assert [page.title for page in result.pages] == ["Root", "A"]
    assert fetcher.requested.count("A") == 1


def test_save_crawl_outputs(tmp_path):
    pages = {
        "Root": make_page(
            "Root",
            [PageLink(target_url="http://example.com/wiki/A", anchor_text="A", target_title="A")],
        ),
        "A": make_page("A", []),
    }

    fetcher = FakeFetcher(pages)
    result = crawler.BasicCrawler(fetcher, crawler.CrawlSettings(max_depth=1)).crawl(["Root"])

    crawler.save_crawl_outputs(result, tmp_path)

    corpus_lines = (tmp_path / "corpus.jsonl").read_text(encoding="utf-8").strip().split("\n")
    corpus_records = [json.loads(line) for line in corpus_lines]
    assert corpus_records[0]["title"] == "Root"
    assert corpus_records[0]["links"][0]["target_title"] == "A"

    graph = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
    assert graph["nodes"] == [
        {"title": "Root", "url": "http://example.com/wiki/Root"},
        {"title": "A", "url": "http://example.com/wiki/A"},
    ]
    assert graph["edges"] == [{"source": "Root", "target": "A"}]

    log_text = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "Fetched 'Root'" in log_text
    assert "Queued 'A' from 'Root'" in log_text
