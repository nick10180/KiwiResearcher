import kiwiresearcher.kiwix_fetcher as kf


class FakeHeaders:
    def __init__(self, charset="utf-8") -> None:
        self._charset = charset

    def get_content_charset(self, default=None):
        return self._charset or default


class FakeResponse:
    def __init__(self, body: str, charset: str = "utf-8") -> None:
        self.body = body.encode(charset)
        self.headers = FakeHeaders(charset)

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requested_urls = []

    def open(self, url, timeout=None):
        self.requested_urls.append((url, timeout))
        return self.response


def test_parser_extracts_text_and_links():
    html = """
    <html><head><title>Example</title><style>.hidden{}</style></head>
    <body>
      <p>Intro with a <a href="/wiki/First_Page">first link</a>.</p>
      <div>More text and <a href="/wiki/Second_Page">second link</a>.</div>
      <script>var ignore = true;</script>
    </body></html>
    """
    doc = kf.PageDocument.from_html(
        title="Example", url="http://localhost:8080/wiki/Example", html=html
    )

    assert "Intro with a" in doc.plain_text
    assert "More text" in doc.plain_text
    assert len(doc.links) == 2
    assert doc.links[0].target_title == "First Page"
    assert doc.links[0].anchor_text == "first link"


def test_title_extraction_handles_encoded_titles():
    href = "/wiki/Bronze_Age_Collapse%3F"
    assert kf._extract_title_from_href(href) == "Bronze Age Collapse?"


def test_fetcher_builds_urls_and_fetches(monkeypatch):
    body = "<html><body><p>Hello</p></body></html>"
    opener = FakeOpener(FakeResponse(body))
    fetcher = kf.KiwixFetcher(base_url="http://localhost:8080", opener=opener)

    url, html = fetcher.fetch_html("Test Page")

    assert url == "http://localhost:8080/wiki/Test_Page"
    assert opener.requested_urls == [(url, fetcher.timeout)]
    assert html.strip().startswith("<html>")

    page = fetcher.fetch_page("Test Page")
    assert page.title == "Test Page"
    assert page.plain_text == "Hello"
