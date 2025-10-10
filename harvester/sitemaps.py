"""harvester.sitemaps"""

import logging
from collections.abc import Iterable
from datetime import UTC
from pathlib import Path

import smart_open
from dateutil.parser import parse as dateutil_parse
from usp.objects.page import SitemapPage
from usp.tree import sitemap_tree_for_homepage

logger = logging.getLogger(__name__)


class SitemapsParser:
    """Class to encapsulate manual sitemap parsing pre-crawl."""

    def __init__(
        self,
        sitemap_root: str,
        sitemap_paths: Iterable[str] | None = None,
        sitemap_from_date: str | None = None,
        sitemap_to_date: str | None = None,
    ):
        """Init.

        Args:
            sitemap_root: root location for of sitemaps, e.g. https://libraries.mit.edu/
            sitemap_paths: relative path of sitemaps from sitemap_root,
                e.g. /foo/sitemap.xml
            sitemap_from_date: optional date filter used when returning parsed pages
            sitemap_to_date: optional date filter used when returning parsed pages
        """
        self.sitemap_root = sitemap_root
        self.sitemap_paths = sitemap_paths
        self.sitemap_from_date = sitemap_from_date
        self.sitemap_to_date = sitemap_to_date
        self._pages: list[SitemapPage] | None = None

    def pages(
        self,
        sitemap_from_date: str | None = None,
        sitemap_to_date: str | None = None,
    ) -> list[SitemapPage]:
        """Return a list of SitemapPages from parsed sitemap tree, optionally filtered.

        Args:
            sitemap_from_date: optional date filter used when returning parsed pages
                - will override self.sitemap_from_date if set
            sitemap_to_date: optional date filter used when returning parsed pages
                - will override self.sitemap_to_date if set
        """
        if self._pages is None:
            self.parse()

        sitemap_from_date = sitemap_from_date or self.sitemap_from_date
        sitemap_to_date = sitemap_to_date or self.sitemap_to_date

        if sitemap_from_date:
            sitemap_from_date = dateutil_parse(sitemap_from_date).replace(tzinfo=UTC)
        if sitemap_to_date:
            sitemap_to_date = dateutil_parse(sitemap_to_date).replace(tzinfo=UTC)

        if self._pages is None:
            return []

        _pages = []
        for page in self._pages:
            if sitemap_from_date and page.last_modified < sitemap_from_date:
                continue
            if sitemap_to_date and page.last_modified >= sitemap_to_date:
                continue
            _pages.append(page)

        logger.info(f"Found {len(_pages)} URLs after filtering.")
        return _pages

    def parse(self) -> None:
        """Parse sitemaps from root + extra paths."""
        logger.info("Parsing sitemaps")
        tree = sitemap_tree_for_homepage(
            self.sitemap_root,
            extra_known_paths=set(self.sitemap_paths or []),
        )
        self._pages = list(tree.all_pages())
        logger.info(f"{len(self._pages)} URLs discovered from sitemap(s)")

    def write_urls(
        self,
        filepath: str | Path,
        sitemap_from_date: str | None = None,
        sitemap_to_date: str | None = None,
    ) -> None:
        """Write discovered URLs to file.

        Args:
            filepath: output filepath for writing, e.g. `urls.txt`
            sitemap_from_date: optional date filter used when returning parsed pages
                - will override self.sitemap_from_date if set
            sitemap_to_date: optional date filter used when returning parsed pages
                - will override self.sitemap_to_date if set
        """
        logger.info(f"Writing text file of URL seeds to '{filepath}'")
        with smart_open.open(filepath, "w") as f:
            for page in self.pages(
                sitemap_from_date=sitemap_from_date,
                sitemap_to_date=sitemap_to_date,
            ):
                f.write(f"{page.url}\n")
