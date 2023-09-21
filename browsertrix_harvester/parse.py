"""browsertrix_harvester.parse"""
# ruff: noqa: N813

import gzip
import io
import json
import logging
import time
import xml.etree.ElementTree as etree
import zipfile
from contextlib import contextmanager
from types import TracebackType
from typing import IO

import pandas as pd
import smart_open  # type: ignore[import]
from bs4 import BeautifulSoup
from warcio import ArchiveIterator  # type: ignore[import]
from warcio.recordloader import ArcWarcRecord  # type: ignore[import]
from yake import KeywordExtractor  # type: ignore[import]

from browsertrix_harvester.exceptions import WaczFileDoesNotExist

logger = logging.getLogger(__name__)


class CrawlParser:
    """Class to facilitate parsing structured data from completed crawls.

    This parser is designed to parse a WACZ file, https://replayweb.page/docs/wacz-format,
    which is a compressed archive of a web crawl.  By utilizing this archive file, a full
    crawl can be easily written anywhere, and this parser can parse data from that crawl
    without juggling multiple files.

    Pulling data from a compressed archive, and the random seek nature of the approach
    below is not optimally performant, but sufficient for use cases at this time.  If new
    use cases arise with considerably larger WACZ files -- that might stress both memory
    and time -- this will need to be reworked.
    """

    # WACZ archive filepaths
    EXTRA_PAGES_FILEPATH = "pages/extraPages.jsonl"
    CDX_INDEX_FILEPATH = "indexes/index.cdx.gz"
    WARC_DIR = "archive"

    # list of metadata tags that are extracted from HTML
    HTML_CONTENT_METADATA_TAGS = (
        "title",
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

    FULLTEXT_KEYWORD_STOPWORDS = (
        "Skip to Main",
        "Main Content",
        "MIT",
        "Main",
        "Content",
        "Skip",
        "Libraries",
        "Open",
    )

    def __init__(self, wacz_filepath: str):
        self.wacz_filepath = wacz_filepath
        self._archive: zipfile.ZipFile | None = None
        self._websites_df: pd.DataFrame | None = None
        self._websites_metadata: CrawlMetadataRecords | None = None

        #
        self._kw_extractor: KeywordExtractor | None = None

    def __enter__(self) -> "CrawlParser":
        """Allows CrawlParser to get used in a context manager context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """On teardown of self, closes Zipfile handle."""
        self.close()

    @property
    def archive(self) -> zipfile.ZipFile:
        if self._archive is None:
            with smart_open.open(self.wacz_filepath, "rb") as file_obj:
                self._archive = zipfile.ZipFile(io.BytesIO(file_obj.read()))
        return self._archive

    @property
    def websites_df(self) -> pd.DataFrame:
        """Property that provides a DataFrame of websites present in the crawl.

        This dataframe combines data from pages/extraPages.json and CDX index data.  It is
        filtered to only HTML pages, and those with CDX data present.
        """
        if self._websites_df is None:
            try:
                extra_pages_df = self._get_extra_pages_df()
            except WaczFileDoesNotExist:
                logger.exception("could not find extraPages.jsonlin WACZ archive")
                raise
            try:
                cdx_df = self._get_cdx_df()
            except WaczFileDoesNotExist:
                logger.exception("could not find index.cdx in WACZ archive")
                raise

            # merge dataframes
            merged_df = extra_pages_df.merge(cdx_df, how="left", on="url")

            # drop any without CDX WARC file pointers
            merged_df = merged_df[~merged_df.filename.isna()]

            # reset index
            merged_df = merged_df.reset_index()

            # replace NaN values with None
            merged_df = merged_df.where(pd.notna(merged_df), None)

            # cache result
            self._websites_df = merged_df

        return self._websites_df

    @property
    def kw_extractor(self) -> KeywordExtractor:
        if self._kw_extractor is None:
            # init keyword extractor
            self._kw_extractor = KeywordExtractor()

            # update stopwords
            self._kw_extractor.stopword_set.update(
                [word.lower().strip() for word in self.FULLTEXT_KEYWORD_STOPWORDS]
            )
        return self._kw_extractor

    def close(self) -> None:
        if self._archive:
            self._archive.close()
            self._archive = None

    def _get_archive_file_obj(self, archive_filepath: str) -> IO[bytes]:
        try:
            return self.archive.open(archive_filepath)
        except KeyError as exc:
            raise WaczFileDoesNotExist from exc

    def _get_extra_pages_df(self) -> pd.DataFrame:
        with self._get_archive_file_obj(self.EXTRA_PAGES_FILEPATH) as file_obj:
            file_obj.readline()  # skip first line
            extra_pages_df = pd.read_json(file_obj, lines=True)

            # filter out sitemap.html sites
            extra_pages_df = extra_pages_df[
                ~extra_pages_df.url.str.endswith("sitemap.html")
            ]

            # ruff: noqa: RET504
            return extra_pages_df

    def _get_cdx_df(self) -> pd.DataFrame:
        """Create DataFrame from CDX index data."""
        with self._get_archive_file_obj(
            self.CDX_INDEX_FILEPATH
        ) as file_obj, gzip.GzipFile(fileobj=file_obj) as decompressed_file:
            lines = decompressed_file.readlines()

        # attempt to extract JSON objects from each line
        parsed_data = []
        for bytes_line in lines:
            str_line = bytes_line.decode("utf-8").strip()
            try:
                json_str = str_line.split(" ", 2)[2]
                parsed_data.append(json.loads(json_str))
            except (IndexError, json.JSONDecodeError):
                continue

        # convert to dataframe and filter to text/html mimetypes
        cdx_df = pd.DataFrame(parsed_data)
        cdx_df = cdx_df[cdx_df.mime == "text/html"]

        return cdx_df

    @contextmanager
    def _get_warc_record(self, warc_filepath: str, offset: int) -> ArcWarcRecord:
        """Get a single website (record) from a WARC archive file.

        Use of warcio.ArchiveIterator is extremely helpful here.  Data stored in WARC
        files may or may not be compressed, binary or string, and are defined by offsets
        and lengths.  The CDX index parsed to a DataFrame in self._get_cdx_df() provides
        the WARC file and the offset (where the binary website recording begins), but this
        library takes it from there, understanding where in the WARC file the record ends,
        and providing a handy reader of the actual data.

        In the event we ever want to explore extracting other file types (e.g. media,
        JSON, etc.) this approach will also prove useful.
        """
        with self._get_archive_file_obj(warc_filepath) as file_obj:
            file_obj.seek(offset)
            record = next(ArchiveIterator(file_obj))
            yield record

    # ruff: noqa: FBT001, FBT002
    def get_website_content_by_url(self, url: str, decode: bool = True) -> str:
        """Get HTML content via a URL.

        This is slower than using self.get_website_content() if the warc filename and
        offset are known, as this needs to search the dataframe for the URL to get the
        WARC filename.
        """
        # get warc file the URL belongs to
        rows = self.websites_df[self.websites_df.url == url]
        if len(rows) == 1:
            row = rows.iloc[0]
        else:
            exc_msg = f"could not find url in CDX index: {url}"
            raise FileNotFoundError(exc_msg)
        return self.get_website_content(row.filename, row.offset, decode=decode)

    def get_website_content(
        self, warc_filename: str, offset: str | int, decode: bool = True
    ) -> str:
        """Extract HTML content from a WARC record."""
        warc_filepath = f"{self.WARC_DIR}/{warc_filename}"
        with self._get_warc_record(warc_filepath, int(offset)) as record:
            content = record.content_stream().read()
            if decode:
                content = content.decode("utf-8")
            return content

    @classmethod
    def get_html_content_metadata(cls, html_content: str | bytes) -> dict:
        """Extract structured metadata from the website HTML."""
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

    def _parse_fulltext(self, fulltext: str) -> str:
        """Cleanup fulltext as provided by Browsertrix crawl."""
        fulltext = fulltext.replace("\n", " ")
        fulltext = fulltext.replace("\r", " ")
        fulltext = fulltext.replace("\t", " ")
        return fulltext

    def _parse_fulltext_50_words(self, fulltext: str) -> str:
        """Extract the first 50 words from the fulltext."""
        first_50_words = fulltext.split(" ")[:50]
        if len(first_50_words) == 50:
            first_50_words.append("[...]")
        return " ".join(first_50_words)

    def _parse_fulltext_keywords(self, fulltext: str) -> str:
        """Parse keywords from fulltext, using YAKE keyword extractor."""
        keywords = self.kw_extractor.extract_keywords(fulltext)
        return ",".join([keyword for keyword, _score in keywords])

    def parse_fulltext_fields(
        self, raw_fulltext: str | None, include_fulltext: bool = False
    ) -> dict:
        """Parse fulltext fields for output metadata.

        While both first 50 words and keywords are always calculated, we don't always
        include the FULL fulltext.  And, if not text is provided, we return None for all
        fulltext fields.
        """
        if raw_fulltext is None:
            return {
                "fulltext": None,
                "fulltext_50_words": None,
                "fulltext_keywords": None,
            }

        fulltext = self._parse_fulltext(raw_fulltext)
        return {
            "fulltext": fulltext if include_fulltext else None,
            "fulltext_50_words": self._parse_fulltext_50_words(fulltext),
            "fulltext_keywords": self._parse_fulltext_keywords(fulltext),
        }

    def generate_metadata(self, include_fulltext: bool = False) -> "CrawlMetadataRecords":
        """Generate dataframe of metadata records for websites.

        This combines metadata from the crawl (e.g. URL, extracted fulltext), and
        metadata extracted from the HTML content itself.

        If more or different metadata is needed, this would be the method to extend.
        """
        logger.info("generating metadata records for crawl")

        if self._websites_metadata is not None:
            return self._websites_metadata

        all_metadata = []

        t0 = time.time()
        row_count = len(self.websites_df)
        for i, row in enumerate(self.websites_df.itertuples(), 1):
            if i % 100 == 0:
                logger.debug(
                    "%d/%d records parsed, %.2fs", *(i, row_count, time.time() - t0)
                )
                t0 = time.time()

            # init with metadata from crawl
            metadata = {
                "url": row.url,
                "cdx_warc_filename": row.filename,
                "cdx_title": row.title,
                "cdx_offset": row.offset,
                "cdx_length": row.length,
            }

            # augment with metadata from actual HTML content
            html_content = self.get_website_content(row.filename, row.offset, decode=True)
            html_metadata = self.get_html_content_metadata(html_content)
            metadata.update(html_metadata)

            # augment with fulltext
            metadata.update(
                self.parse_fulltext_fields(row.text, include_fulltext=include_fulltext)
            )

            # append to list
            all_metadata.append(metadata)

        # create dataframe
        websites_metadata_df = pd.DataFrame(all_metadata)

        # replace NaN with python None
        websites_metadata_df = websites_metadata_df.where(
            pd.notna(websites_metadata_df), None
        )

        # init instance of CrawlMetadataRecords and cache
        self._websites_metadata = CrawlMetadataRecords(websites_metadata_df)

        return self._websites_metadata


class CrawlMetadataRecords:
    """Class to represent and serialize structured metadata extracted from crawl."""

    def __init__(self, metadata_df: pd.DataFrame) -> None:
        self.df = metadata_df

    # ruff: noqa: D105
    def __repr__(self) -> str:
        return f"<CrawlMetadataRecords: {len(self.df)} records>"

    def to_xml(self) -> bytes:
        """Create an XML byte string of crawl metadata.

        This returns an XML string in the format:
        <records>
            <record>...</record>, ...
        </records>
        """
        root = etree.Element("records")
        for _, row in self.df.iterrows():
            item = etree.Element("record")
            root.append(item)
            for col in self.df.columns:
                cell = etree.Element(col)
                cell.text = str(row[col])
                item.append(cell)
        xml_bytes = etree.tostring(root, encoding="utf-8", method="xml")
        return xml_bytes

    def write(self, filepath: str) -> None:
        """Write metadata records in various formats.

        The file format is determined by the filepath file extension.
        """
        logger.info("writing metadata to: %s", filepath)

        # determine file format
        file_format = filepath.split(".")[-1].strip().lower()

        # write file
        if file_format == "xml":
            with smart_open.open(filepath, "wb") as f:
                f.write(self.to_xml())
        elif file_format == "tsv":
            with smart_open.open(filepath, "wb") as f:
                self.df.to_csv(filepath, sep="\t", index=False)
        elif file_format == "csv":
            with smart_open.open(filepath, "wb") as f:
                self.df.to_csv(filepath, sep=",", index=False)
        else:
            msg = f"file format '{file_format}' not recognized"
            raise NotImplementedError(msg)
