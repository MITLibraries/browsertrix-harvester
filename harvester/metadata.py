"""harvester.parse"""
# ruff: noqa: N813

import logging
import time
import xml.etree.ElementTree as etree

import pandas as pd
import smart_open  # type: ignore[import]
from bs4 import BeautifulSoup
from yake import KeywordExtractor  # type: ignore[import]

from harvester.wacz import WACZClient

logger = logging.getLogger(__name__)


class CrawlMetadataParser:
    """Class to facilitate parsing metadata records from completed crawls.

    This parser is designed to parse a WACZ file, a compressed archive of a web crawl, and
    generate metadata records for each website crawled.
    """

    # list of metadata tags that are extracted from HTML
    HTML_CONTENT_METADATA_TAGS = (
        "og:site_name",
        "og:title",
        "og:locale",
        "og:type",
        "og:image",
        "og:url",
        "og:image:url",
        "og:image:secure_url",
        "og:image:type",
        "og:image:width",
        "og:image:height",
        "og:image:alt",
        "og:description",
    )

    # list of stopwords to ignore when generating keywords from fulltext
    FULLTEXT_KEYWORD_STOPWORDS = (
        "Skip to Main",
        "Main Content",
        "MIT",
        "Main",
        "Content",
        "Skip",
        "Libraries",
        "Open",
        "Library",
        "View Menu Home",
        "View Menu",
        "events Subscribe",
        "Subscribe",
        "Access Collection",
        "Event date",
        "access",
        "access downloads",
        "access policies",
        "Toggle navigation View",
        "navigation View Menu",
        "articles by MIT-affiliated",
        "authors made",
        "Menu Home",
        "Toggle navigation",
        "navigation View",
        "Menu Home Services",
        "Documentation Center Toggle",
        "Center Toggle navigation",
        "Documentation Center Toggle",
        "Stacks Toggle navigation",
        "titles Chronological list",
        "Stacks Toggle",
    )

    def __init__(self, wacz_filepath: str):
        self.wacz_filepath = wacz_filepath
        self._websites_metadata: CrawlMetadataRecords | None = None
        self._keyword_extractor: KeywordExtractor | None = None

    def generate_metadata(self, include_fulltext: bool = False) -> "CrawlMetadataRecords":
        """Generate dataframe of metadata records from websites crawled in WACZ file.

        This combines metadata from the crawl (e.g. URL, extracted fulltext), and
        metadata extracted from the HTML content itself.
        """
        logger.info("Generating metadata records from crawl")

        # if metadata records already generated, re-use
        if self._websites_metadata:
            return self._websites_metadata

        with WACZClient(self.wacz_filepath) as wacz_client:
            # bookkeeping
            all_metadata = []
            t0 = time.time()
            row_count = len(wacz_client.html_websites_df)

            # loop through websites dataframe and enrich with data from HTML content
            # NOTE: naive loop through dataframe is not ideal performance-wise, but works
            for i, row in enumerate(wacz_client.html_websites_df.itertuples(), 1):
                if i % 100 == 0:  # pragma: no cover
                    logger.debug(
                        "%d/%d records parsed, %.2fs", *(i, row_count, time.time() - t0)
                    )
                    t0 = time.time()

                # init website metadata dictionary with data already known from WACZ files
                metadata = {
                    "url": row.url,
                    "cdx_warc_filename": row.filename,
                    "cdx_title": row.title,
                    "cdx_offset": row.offset,
                    "cdx_length": row.length,
                }

                # augment with metadata parsed from the website's HTML content
                html_content = wacz_client.get_website_content(
                    row.filename, row.offset, decode=True
                )
                html_metadata = self.get_html_content_metadata(html_content)
                metadata.update(html_metadata)

                # augment again with data parsed from, and including, HTML fulltext
                metadata.update(
                    self.parse_fulltext_fields(
                        row.text, include_fulltext=include_fulltext
                    )
                )

                all_metadata.append(metadata)

            # create dataframe from all dictionaries
            websites_metadata_df = pd.DataFrame(all_metadata)

            # replace NaN with python None
            websites_metadata_df = websites_metadata_df.where(
                pd.notna(websites_metadata_df), None
            )

            # init instance of CrawlMetadataRecords and cache
            self._websites_metadata = CrawlMetadataRecords(websites_metadata_df)

            return self._websites_metadata

    @classmethod
    def get_html_content_metadata(cls, html_content: str | bytes) -> dict:
        """Extract structured metadata from the website HTML.

        This method extracts values for HTML tags defined in HTML_CONTENT_METADATA_TAGS,
        which are mostly aligned with expected Open Graph Protocol (OGP) HTML elements.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        tags = {}
        for og_tag_name in cls.HTML_CONTENT_METADATA_TAGS:
            og_tag = soup.find("meta", property=og_tag_name)
            if og_tag is None:
                continue
            if content := og_tag.get("content"):  # type: ignore[union-attr]
                content_stripped = content.strip()  # type: ignore[union-attr]
                if content_stripped != "":
                    og_tag_name_friendly = og_tag_name.replace(":", "_")
                    tags[og_tag_name_friendly] = content_stripped
        return tags

    def _remove_fulltext_whitespace(self, fulltext: str) -> str:
        """Remove whitespace from provided fulltext."""
        fulltext = fulltext.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        # ruff: noqa: RET504
        return fulltext

    def _generate_fulltext_keywords(self, fulltext: str) -> str:
        """Parse keywords from fulltext, using YAKE keyword extractor.

        The yake method extract_keywords() returns a keyword and score of that keyword
        from the fulltext as a tuple.  The score is not currently used.
        """
        keywords = self.keyword_extractor.extract_keywords(fulltext)
        return ",".join([keyword for keyword, _score in keywords])

    def parse_fulltext_fields(
        self,
        raw_fulltext: str | None,
        # ruff: noqa: FBT001, FBT002
        include_fulltext: bool = False,
        include_fulltext_keywords: bool = True,
    ) -> dict:
        """Parse fulltext fields for output metadata."""
        if not raw_fulltext:
            return {
                "fulltext": None,
                "fulltext_50_words": None,
                "fulltext_keywords": None,
            }

        fulltext = self._remove_fulltext_whitespace(raw_fulltext)
        return {
            "fulltext": fulltext if include_fulltext else None,
            "fulltext_keywords": self._generate_fulltext_keywords(fulltext)
            if include_fulltext_keywords
            else None,
        }

    @property
    def keyword_extractor(self) -> KeywordExtractor:
        """Property to lazy load an instance of the yake KeywordExtract class.

        This is a somewhat experimental feature, to extract keywords from a website's
        full-text.  It may be determined that a more refined approach is needed, but for
        now this provides a serviceable (if somewhat naive) list of keywords for websites.
        """
        if self._keyword_extractor is None:
            # init keyword extractor
            self._keyword_extractor = KeywordExtractor()

            # update stopwords
            self._keyword_extractor.stopword_set.update(
                [word.lower().strip() for word in self.FULLTEXT_KEYWORD_STOPWORDS]
            )
        return self._keyword_extractor


class CrawlMetadataRecords:
    """Class to represent and serialize structured metadata extracted from crawl."""

    def __init__(self, metadata_df: pd.DataFrame) -> None:
        self.metadata_df = metadata_df

    # ruff: noqa: D105
    def __repr__(self) -> str:
        return (
            f"<CrawlMetadataRecords: {len(self.metadata_df)} records>"  # pragma: no cover
        )

    def to_xml(self) -> bytes:
        """Create an XML byte string of crawl metadata.

        This returns an XML byte string in the format:
        <records>
            <record>...</record>, ...
        </records>
        """
        root = etree.Element("records")
        for _, row in self.metadata_df.iterrows():
            item = etree.Element("record")
            root.append(item)
            for col in self.metadata_df.columns:
                cell = etree.Element(col)
                cell.text = str(row[col])
                item.append(cell)
        return etree.tostring(root, encoding="utf-8", method="xml")

    def write(self, filepath: str) -> None:
        """Serialize metadata records in various file formats.

        The file format is determined by the filepath file extension.
        """
        logger.info("Writing metadata to: %s", filepath)

        # determine file format
        file_format = filepath.split(".")[-1].strip().lower()

        # write file
        if file_format == "xml":
            with smart_open.open(filepath, "wb") as f:
                f.write(self.to_xml())
        elif file_format == "tsv":
            with smart_open.open(filepath, "wb") as f:
                self.metadata_df.to_csv(filepath, sep="\t", index=False)
        elif file_format == "csv":
            with smart_open.open(filepath, "wb") as f:
                self.metadata_df.to_csv(filepath, sep=",", index=False)
        else:
            message = f"File format '{file_format}' not recognized"
            raise NotImplementedError(message)
