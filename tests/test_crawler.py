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
