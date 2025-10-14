"""tests.test_sitemaps"""

# ruff: noqa: S108, SLF001

from unittest.mock import mock_open, patch

from harvester.sitemaps import SitemapsParser


def test_sitemaps_parser_init():
    parser = SitemapsParser(["https://example.com/sitemap.xml"])
    assert parser.sitemaps == ["https://example.com/sitemap.xml"]
    assert parser.sitemap_from_date is None
    assert parser.sitemap_to_date is None
    assert parser._pages is None


def test_sitemaps_parser_init_with_multiple_sitemaps():
    parser = SitemapsParser(
        ["https://example.com/sitemap.xml", "https://example.com/news/sitemap.xml"]
    )
    assert parser.sitemaps == [
        "https://example.com/sitemap.xml",
        "https://example.com/news/sitemap.xml",
    ]


def test_sitemaps_parser_parse(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(["https://example.com/sitemap.xml"])
        parser.parse()

        assert len(parser._pages) == 3
        page_urls = {page.url for page in parser._pages}
        assert page_urls == {
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        }


def test_sitemaps_parser_parse_sitemap_components():
    parser = SitemapsParser(["https://example.com/sitemap.xml"])
    root, path = parser._parse_sitemap_components("https://example.com/sitemap.xml")

    assert root == "https://example.com"
    assert path == "/sitemap.xml"


def test_sitemaps_parser_parse_with_multiple_paths(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ) as mock_tree_func:
        parser = SitemapsParser(
            [
                "https://example.com/sitemap.xml",
                "https://example.com/news/sitemap.xml",
            ]
        )
        parser.parse()

        mock_tree_func.assert_called_once_with(
            "https://example.com",
            extra_known_paths={"/sitemap.xml", "/news/sitemap.xml"},
        )


def test_sitemaps_parser_parse_with_multiple_domains(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ) as mock_tree_func:
        parser = SitemapsParser(
            [
                "https://example.com/sitemap.xml",
                "https://other.com/sitemap.xml",
            ]
        )
        parser.parse()

        assert mock_tree_func.call_count == 2
        mock_tree_func.assert_any_call(
            "https://example.com",
            extra_known_paths={"/sitemap.xml"},
        )
        mock_tree_func.assert_any_call(
            "https://other.com",
            extra_known_paths={"/sitemap.xml"},
        )


def test_sitemaps_parser_pages_no_filters(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(["https://example.com/sitemap.xml"])
        pages = parser.pages()

        assert len(pages) == 3


def test_sitemaps_parser_pages_with_from_date_filter(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(
            ["https://example.com/sitemap.xml"],
            sitemap_from_date="2025-02-01",
        )
        pages = parser.pages()

        assert len(pages) == 2
        page_urls = {page.url for page in pages}
        assert page_urls == {"https://example.com/page2", "https://example.com/page3"}


def test_sitemaps_parser_pages_with_to_date_filter(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(
            ["https://example.com/sitemap.xml"],
            sitemap_to_date="2025-02-01",
        )
        pages = parser.pages()

        assert len(pages) == 1
        assert pages[0].url == "https://example.com/page1"


def test_sitemaps_parser_pages_with_both_date_filters(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(
            ["https://example.com/sitemap.xml"],
            sitemap_from_date="2025-02-01",
            sitemap_to_date="2025-03-01",
        )
        pages = parser.pages()

        assert len(pages) == 1
        assert pages[0].url == "https://example.com/page2"


def test_sitemaps_parser_pages_override_dates(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ):
        parser = SitemapsParser(["https://example.com/sitemap.xml"])
        pages = parser.pages(sitemap_from_date="2025-02-15")

        assert len(pages) == 2
        page_urls = {page.url for page in pages}
        assert page_urls == {"https://example.com/page2", "https://example.com/page3"}


def test_sitemaps_parser_write_urls(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ), patch("smart_open.open", mock_open()) as mock_file:
        parser = SitemapsParser(["https://example.com/sitemap.xml"])
        parser.write_urls("/tmp/urls.txt")

        mock_file.assert_called_once_with("/tmp/urls.txt", "w")
        handle = mock_file()
        assert handle.write.call_count == 3
        handle.write.assert_any_call("https://example.com/page1\n")
        handle.write.assert_any_call("https://example.com/page2\n")
        handle.write.assert_any_call("https://example.com/page3\n")


def test_sitemaps_parser_write_urls_with_filter(mock_sitemap_tree):
    with patch(
        "harvester.sitemaps.sitemap_tree_for_homepage", return_value=mock_sitemap_tree
    ), patch("smart_open.open", mock_open()) as mock_file:
        parser = SitemapsParser(
            ["https://example.com/sitemap.xml"],
            sitemap_from_date="2025-02-15",
        )
        parser.write_urls("/tmp/urls.txt")

        handle = mock_file()
        assert handle.write.call_count == 2
        handle.write.assert_any_call("https://example.com/page2\n")
        handle.write.assert_any_call("https://example.com/page3\n")
