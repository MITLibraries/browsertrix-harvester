"""harvester.parse"""

import io
import logging
import time
import xml.etree.ElementTree as ET

import jsonlines  # type: ignore[import]
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

    def generate_metadata(
        self,
        *,
        include_fulltext: bool = False,
        extract_fulltext_keywords: bool = False,
        urls_file: str | None = None,
        previous_sitemap_urls_file: str | None = None,
    ) -> "CrawlMetadataRecords":
        """Generate dataframe of metadata records from websites crawled in WACZ file.

        This combines metadata from the crawl (e.g. URL, extracted fulltext), and
        metadata extracted from the HTML content itself.

        Args:
            include_fulltext: #TODO: complete
            extract_fulltext_keywords: #TODO: complete
            urls_file: #TODO: complete
            previous_sitemap_urls_file: #TODO: complete
        """
        logger.info("Generating metadata records from crawl")

        # if metadata records already generated, re-use
        if self._websites_metadata:
            return self._websites_metadata

        all_metadata = []

        # add metadata records from the crawl (new or modified sites)
        with WACZClient(self.wacz_filepath) as wacz_client:
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
                    "status": "active",
                    "cdx_warc_filename": row.filename,
                    "cdx_title": row.title,
                    "cdx_offset": row.offset,
                    "cdx_length": row.length,
                }

                # augment with metadata parsed from the website's HTML content
                html_content = wacz_client.get_website_content(
                    str(row.filename), str(row.offset), decode=True
                )
                html_metadata = self.get_html_content_metadata(html_content)
                metadata.update(html_metadata)

                # augment again with data parsed from, and including, HTML fulltext
                metadata.update(
                    self.parse_fulltext_fields(
                        row.text,  # type:ignore[arg-type]
                        include_fulltext=include_fulltext,
                        extract_fulltext_keywords=extract_fulltext_keywords,
                    )
                )

                all_metadata.append(metadata)

        # add status=deleted metadata records if current and previous URL lists are passed
        if urls_file and previous_sitemap_urls_file:
            all_metadata.extend(
                self._generate_metadata_for_deleted_urls(
                    urls_file, previous_sitemap_urls_file
                )
            )

        # create dataframe from all dictionaries
        websites_metadata_df = pd.DataFrame(all_metadata)

        # replace NaN with python None
        websites_metadata_df = websites_metadata_df.where(  # type: ignore[call-overload]
            pd.notna(websites_metadata_df), None
        )

        # remove duplicate URLs
        websites_metadata_df = self._remove_duplicate_urls(websites_metadata_df)

        logger.info(f"{len(websites_metadata_df)} metadata records generated.")

        # init instance of CrawlMetadataRecords and cache
        self._websites_metadata = CrawlMetadataRecords(websites_metadata_df)

        return self._websites_metadata

    def _generate_metadata_for_deleted_urls(
        self, current_urls_filepath: str, previous_urls_filepath: str
    ) -> list[dict]:
        """Generate metadata records for URLs that have been removed since last crawl.

        If the previous list of URLs is not retrievable for any reason, this method
        defaults to yielding zero deleted records.
        """
        logger.info(
            "Analyzing previous and current sitemap discovered URLs for deletions."
        )

        # open local list of URLs from this crawl's sitemap parsing
        with open(current_urls_filepath) as f:
            current_urls = [line.strip() for line in f]

        # open local/remote list of URLs from a previous crawl's sitemap parsing
        try:
            with smart_open.open(previous_urls_filepath) as f:
                previous_urls = [line.strip() for line in f]
        except (FileNotFoundError, OSError) as exc:
            logger.error(  # noqa: TRY400
                "Unable to retrieve previous list of URLs at: "
                f"'{previous_urls_filepath}', error: '{exc}'"
            )
            return []

        deleted_urls = list(set(previous_urls).difference(set(current_urls)))
        logger.info(f"Creating {len(deleted_urls)} status=deleted metadata records.")

        return [
            {
                "url": url,
                "status": "deleted",
            }
            for url in deleted_urls
            if url and url != ""
        ]

    @classmethod
    def get_html_content_metadata(cls, html_content: str | bytes) -> dict:
        """Extract structured metadata from the website HTML.

        This method extracts values for HTML tags defined in HTML_CONTENT_METADATA_TAGS,
        which are mostly aligned with expected Open Graph Protocol (OGP) HTML elements.
        """
        html_soup = BeautifulSoup(html_content, "html.parser")

        tags = {}
        tags.update(cls._parse_open_graph_meta_elements(html_soup))
        tags.update(cls._parse_dublin_core_meta_elements(html_soup))

        return tags

    @classmethod
    def _parse_open_graph_meta_elements(cls, html_soup: BeautifulSoup) -> dict:
        """Parse OpenGraph <meta> tag values.

        https://ogp.me/

        Example:
            <meta property="og:title" content="MIT Libraries"/>
            <meta property="og:description" content="Library home page." />
        """
        og_tag_properties = (
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

        fields = {}
        for og_tag_property in og_tag_properties:
            og_tag = html_soup.find("meta", attrs={"property": og_tag_property})
            if og_tag is None:
                continue
            if content := og_tag.get("content"):  # type: ignore[union-attr]
                content_stripped = content.strip()  # type: ignore[union-attr]
                if content_stripped != "":
                    og_tag_name_friendly = og_tag_property.replace(":", "_")
                    fields[og_tag_name_friendly] = content_stripped
        return fields

    @classmethod
    def _parse_dublin_core_meta_elements(cls, html_soup: BeautifulSoup) -> dict:
        """Parse Dublin Core <meta> tag values.

        Example:
            <meta name="DC.Title" content="LibGuides: Biology: Home"/>
            <meta name="DC.Description" content="A guide about biology."/>
        """
        dc_tag_names = (
            "DC.Title",
            "DC.Creator",
            "DC.Subject",
            "DC.Description",
            "DC.Publishers",
            "DC.Rights",
            "DC.Language",
            "DC.Identifier",
            "DC.Date.Created",
            "DC.Date.Modified",
        )
        fields = {}
        for dc_tag_name in dc_tag_names:
            dc_tag = html_soup.find("meta", attrs={"name": dc_tag_name})
            if dc_tag is None:
                continue
            if content := dc_tag.get("content"):  # type: ignore[union-attr]
                content_stripped = content.strip()  # type: ignore[union-attr]
                if content_stripped != "":
                    dc_tag_name_friendly = dc_tag_name.replace(":", "_")
                    fields[dc_tag_name_friendly] = content_stripped
        return fields

    def _remove_fulltext_whitespace(self, fulltext: str) -> str:
        """Remove whitespace from provided fulltext."""
        return fulltext.replace("\n", " ").replace("\r", " ").replace("\t", " ")

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
        *,
        include_fulltext: bool = True,
        extract_fulltext_keywords: bool = False,
    ) -> dict:
        """Parse fulltext fields for output metadata."""
        fields: dict[str, str | None] = {
            "fulltext": None,
            "fulltext_keywords": None,
        }

        # return early if no fulltext fields requested
        if not (include_fulltext or extract_fulltext_keywords) or raw_fulltext is None:
            return fields

        fulltext = self._remove_fulltext_whitespace(raw_fulltext)

        if include_fulltext:
            fields["fulltext"] = fulltext

        if extract_fulltext_keywords:
            fields["fulltext_keywords"] = self._generate_fulltext_keywords(fulltext)

        return fields

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

    def _remove_duplicate_urls(self, websites_metadata_df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate URLs.

        The instance with the last CDX offset is used, which is a somewhat arbitrary
        attempt to used the last instance crawled, but it likely makes no difference given
        the short timeframe of the crawl.
        """
        return (
            websites_metadata_df.sort_values("cdx_offset")
            .drop_duplicates(subset="url", keep="last")
            .reset_index(drop=True)
        )


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
        root = ET.Element("records")
        for _, row in self.metadata_df.iterrows():
            item = ET.Element("record")
            root.append(item)
            for col in self.metadata_df.columns:
                cell = ET.Element(col)
                cell.text = str(row[col])
                item.append(cell)
        return ET.tostring(root, encoding="utf-8", method="xml")

    def to_jsonl(self) -> bytes:
        """Create JSONLines buffer from crawl metadata."""
        buffer = io.StringIO()
        with jsonlines.Writer(buffer) as writer:
            for _, row in self.metadata_df.iterrows():
                writer.write(row.to_dict())
        return buffer.getvalue().encode("utf-8")

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
        elif file_format == "jsonl":
            with smart_open.open(filepath, "wb") as f:
                f.write(self.to_jsonl())
        elif file_format == "tsv":
            with smart_open.open(filepath, "wb") as f:
                self.metadata_df.to_csv(filepath, sep="\t", index=False)
        elif file_format == "csv":
            with smart_open.open(filepath, "wb") as f:
                self.metadata_df.to_csv(filepath, sep=",", index=False)
        else:
            message = f"File format '{file_format}' not recognized"
            raise NotImplementedError(message)
