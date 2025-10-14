"""harvester.sitemaps"""

import logging
from collections import defaultdict
from datetime import UTC
from pathlib import Path
from urllib.parse import urlparse

import smart_open
from dateutil.parser import parse as dateutil_parse
from usp.objects.page import SitemapPage
from usp.tree import sitemap_tree_for_homepage

logger = logging.getLogger(__name__)


class SitemapsParser:
    """Class to encapsulate manual sitemap parsing pre-crawl."""

    def __init__(
        self,
        sitemaps: list[str] | tuple[str, ...],
        sitemap_from_date: str | None = None,
        sitemap_to_date: str | None = None,
    ):
        """Init.

        Args:
            sitemaps: iterable of full sitemaps paths
            sitemap_from_date: optional date filter used when returning parsed pages
            sitemap_to_date: optional date filter used when returning parsed pages
        """
        self.sitemaps = sitemaps
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
        """Parse sitemaps list of provided sitemaps."""
        logger.info(f"Parsing {len(self.sitemaps)} sitemaps")

        # create dictionary of domain:path for all sitemaps
        root_to_paths = defaultdict(set)
        for sitemap in self.sitemaps:
            root, path = self._parse_sitemap_components(sitemap)
            root_to_paths[root].add(path)

        _pages = []
        for root, paths in root_to_paths.items():
            tree = sitemap_tree_for_homepage(
                root,
                extra_known_paths=paths,
            )
            sitemap_pages = list(tree.all_pages())
            logger.info(
                f"Discovered {len(sitemap_pages)} URLs from sitemap root: {root}, "
                f"paths: {paths}"
            )
            _pages.extend(sitemap_pages)

        self._pages = list(set(_pages))
        logger.info(f"{len(self._pages)} total URLs discovered")

    def _parse_sitemap_components(self, sitemap: str) -> tuple[str, str]:
        """Parse a URL into (root, path) tuple.

        Args:
            sitemap: Full URL string

        Returns:
            tuple: (root_url, path) where root_url is scheme://netloc
        """
        parsed = urlparse(sitemap)
        root = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path
        return root, path

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
