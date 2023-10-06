"""harvester.wacz"""

import gzip
import io
import json
import logging
import zipfile
from contextlib import contextmanager
from types import TracebackType
from typing import IO

import pandas as pd
import smart_open  # type: ignore[import]
from warcio import ArchiveIterator  # type: ignore[import]
from warcio.recordloader import ArcWarcRecord  # type: ignore[import]

from harvester.exceptions import ContextManagerRequiredError, WaczFileDoesNotExist

logger = logging.getLogger(__name__)


class WACZClient:
    """Client of utilities to interact with a WACZ archive from a completed web crawl.

    WACZ file spec: https://replayweb.page/docs/wacz-format.

    WACZ files are a zipped archive of all assets from a web crawl.  This includes ALL
    HTTP requests made while crawling the pages.  The fully rendered form of the pages
    are stored in binary WARC files, with "index" files that help correlate a particular
    URL with the location in those WARC files.  This client supports reading files from
    a WACZ archive, and some utilities to actually extract the rendered page HTML from
    the WARC files.

    NOTE: This class is designed to be used via a context manager, e.g.:
        with WACZClient(<path_to_wacz_file>) as wacz_client:
            html_content = wacz_client.get_website_content_by_url("http://example.com")

    This guarantees that any open ZipFile file objects will be closed upon context manager
    exiting.
    """

    PAGES_FILEPATHS = ("pages/pages.jsonl", "pages/extraPages.jsonl")
    CDX_INDEX_FILEPATH = "indexes/index.cdx.gz"
    WARC_DIR = "archive"

    def __init__(self, wacz_filepath: str):
        self.wacz_filepath = wacz_filepath
        self._via_context_manager = False
        self._wacz_archive: zipfile.ZipFile | None = None
        self._html_websites_df: pd.DataFrame | None = None

    def __enter__(self) -> "WACZClient":
        """Enter method for use when class instantiated via a context manager.

        This sets the private attribute self._via_context_manager to True, allowing any
        methods to know if operating with a context manager.
        """
        self._via_context_manager = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Exit method for use when class instantiated via a context manager.

        When the context manager closes, this method closes any open file objects from the
        WACZ ZipFile.
        """
        self.close()

    def close(self) -> None:
        """Close open WACZ ZipFile."""
        if self._wacz_archive:
            logger.debug("Closing WACZ ZipFile file handle.")
            self._wacz_archive.close()
            self._wacz_archive = None

    @property
    def wacz_archive(self) -> zipfile.ZipFile:
        """Property that provides an open ZipFile file object of the target WACZ file.

        NOTE: when accessed, this property will throw a ContextManagerRequiredError
        exception if not operating in a context manager context.
        """
        if not self._via_context_manager:
            msg = (
                "Please use this class via a context manager for operations that read "
                "the WACZ file"
            )
            raise ContextManagerRequiredError(msg)
        if self._wacz_archive is None:
            with smart_open.open(self.wacz_filepath, "rb") as file_obj:
                _wacz_archive = zipfile.ZipFile(io.BytesIO(file_obj.read()))
                self._wacz_archive = _wacz_archive
        return self._wacz_archive

    def _get_archive_file_obj(self, archive_filepath: str) -> IO[bytes]:
        """Return a file-like object for a filepath in the WACZ ZipFile."""
        try:
            return self.wacz_archive.open(archive_filepath)
        except KeyError as exc:
            raise WaczFileDoesNotExist from exc

    def _get_pages_df(self) -> pd.DataFrame:
        """Generate dataframe of data from WACZ '/pages' files.

        The pages files come from the directory '/pages' in the WACZ file where a
        'pages.json' file ALWAYS exists, and 'extraPages.jsonl' file MAY exist.

        For the purpose of this WACZ client, this data defines the canonical list of URLs
        present in the web crawl, and a bonus of full-text from those pages with the
        HTML tags already stripped.
        """
        all_pages_dfs = []
        for pages_file in self.PAGES_FILEPATHS:
            try:
                with self._get_archive_file_obj(pages_file) as file_obj:
                    file_obj.readline()  # skip first line
                    pages_df = pd.read_json(file_obj, lines=True)

                    # filter out sitemap related pages
                    pages_df = pages_df[~pages_df.url.str.endswith("sitemap.html")]
                    pages_df = pages_df[~pages_df.url.str.endswith("sitemap.xml")]

                    # append to list of dataframes
                    all_pages_dfs.append(pages_df)

            except WaczFileDoesNotExist:
                msg = f"A pages file was not found in WACZ file: {pages_file}."
                logger.debug(msg)

        if not all_pages_dfs:
            msg = "Both pages.jsonl and extraPages.jsonl appear missing from WACZ file"
            raise WaczFileDoesNotExist(msg)

        return pd.concat(all_pages_dfs)

    def _get_cdx_df(self) -> pd.DataFrame:
        """Create DataFrame from CDX index data.

        Data returned includes more low level information about the HTTP request itself
        like status codes, mimetypes, and specific length and offsets where request
        response can be found in the '/archive' WARC files.
        """
        with self._get_archive_file_obj(
            self.CDX_INDEX_FILEPATH
        ) as file_obj, gzip.GzipFile(fileobj=file_obj) as decompressed_file:
            lines = decompressed_file.readlines()

        # extract JSON object from each line
        parsed_data = []
        for bytes_line in lines:
            cdx_line_data = self._parse_cdx_line(bytes_line)
            if cdx_line_data:
                parsed_data.append(cdx_line_data)

        # convert to dataframe and filter to text/html mimetypes
        cdx_df = pd.DataFrame(parsed_data)
        cdx_df = cdx_df[cdx_df.mime == "text/html"]

        # ruff: noqa: RET504
        return cdx_df

    @staticmethod
    def _parse_cdx_line(bytes_line: bytes) -> dict | None:
        """Parse JSON object from CDX line.

        Each line in a CDX file provides information about the HTTP request to that URL.
        Each line is comprised of a string of data and then a JSON object.  This method
        uses only the JSON object embedded in the line, which contains all the information
        needed.
        """
        str_line = bytes_line.decode("utf-8").strip()
        try:
            json_str = str_line.split(" ", 2)[2]
            return json.loads(json_str)
        except (IndexError, json.JSONDecodeError):
            logger.exception("Error parsing CDX line")
            return None

    @property
    def html_websites_df(self) -> pd.DataFrame:
        """Return a DataFrame of websites present in the crawl.

        This dataframe combines data from WACZ pages files and CDX index data.  It is
        then filtered to only HTML pages with CDX data present.  The end result is a
        dataframe of all websites from the crawl, with a enough high level and low level
        information about those pages to support other operations (like full HTML
        extraction if needed).
        """
        if self._html_websites_df is None:
            # load extra pages and CDX as dataframes
            extra_pages_df = self._get_pages_df()
            cdx_df = self._get_cdx_df()

            # merge dataframes
            merged_df = extra_pages_df.merge(cdx_df, how="left", on="url")

            # drop any without CDX WARC file pointers
            merged_df = merged_df[~merged_df.filename.isna()]

            # reset index
            merged_df = merged_df.reset_index()

            # replace NaN values with None
            merged_df = merged_df.where(pd.notna(merged_df), None)

            # cache result
            self._html_websites_df = merged_df

        return self._html_websites_df

    @contextmanager
    def _get_warc_record(
        self,
        warc_filepath: str,
        offset: int,
    ) -> ArcWarcRecord:
        """Get a single website (record) from a WARC archive file.

        Use of warcio.ArchiveIterator is extremely helpful here.  Data stored in WARC
        files may or may not be compressed, binary or string, and are defined by offsets
        and lengths.  The CDX index parsed to a DataFrame in self._get_cdx_df() provides
        the WARC file and the offset (where the binary website recording begins), but this
        library takes it from there, understanding where in the WARC file the record ends,
        and providing a handy reader of the actual data.
        """
        with self._get_archive_file_obj(warc_filepath) as file_obj:
            file_obj.seek(offset)
            record = next(ArchiveIterator(file_obj))
            yield record

    def get_website_content(
        self,
        warc_filename: str,
        offset: str | int,
        decode: bool = True,
    ) -> str:
        """Extract HTML content from a WARC record given WARC filename and offset.

        Given a WARC file and an offset, retrieve the WARC record as a readable object,
        then return the (optionally) decoded content.
        """
        warc_filepath = f"{self.WARC_DIR}/{warc_filename}"
        with self._get_warc_record(warc_filepath, int(offset)) as record:
            content = record.content_stream().read()
            if decode:
                content = content.decode("utf-8")
            return content

    # ruff: noqa: FBT001, FBT002
    def get_website_content_by_url(
        self,
        url: str,
        decode: bool = True,
    ) -> str:
        """Extract HTML content from a WARC record given a URL only.

        NOTE: this is slower than using self.get_website_content() if the warc filename
        and offset are known, as this needs to first perform a search via the URL to get
        the WARC filename and offset.
        """
        # get warc file the URL belongs to
        rows = self.html_websites_df[self.html_websites_df.url == url]
        if len(rows) == 1:
            row = rows.iloc[0]
        else:
            exc_msg = f"Could not find url in CDX index: {url}"
            raise FileNotFoundError(exc_msg)
        return self.get_website_content(row.filename, row.offset, decode=decode)
