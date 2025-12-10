"""harvester.parse"""

import base64
import io
import logging
import time
import xml.etree.ElementTree as ET

import jsonlines  # type: ignore[import]
import pandas as pd
import smart_open  # type: ignore[import]

from harvester.wacz import WACZClient

logger = logging.getLogger(__name__)


class CrawlRecordsParser:
    """Class to facilitate parsing records from completed crawls.

    This parser is designed to parse a WACZ file, a compressed archive of a web crawl, and
    generate records for each website crawled.
    """

    def __init__(self, wacz_filepath: str):
        self.wacz_filepath = wacz_filepath
        self._websites_records: CrawlRecords | None = None

    def generate_records(
        self,
        *,
        urls_file: str | None = None,
        previous_sitemap_urls_file: str | None = None,
    ) -> "CrawlRecords":
        """Generate dataframe of records from websites crawled in WACZ file.

        This combines data from the crawl (e.g. URL, WARC file), and the full,
        rendered HTML from the website itself.

        Args:
            urls_file: Text file with URLs found in this crawl
                - used for generating action="delete" records
            previous_sitemap_urls_file: Text file with URLs found in last crawl
                - used for generating action="delete" records
        """
        logger.info("Generating records from crawl")

        # if records already generated, re-use
        if self._websites_records:
            return self._websites_records

        all_records = []

        # add records from the crawl (new or modified sites)
        with WACZClient(self.wacz_filepath) as wacz_client:
            t0 = time.time()
            row_count = len(wacz_client.html_websites_df)

            # loop through HTML pages captured in crawl
            for i, row in enumerate(wacz_client.html_websites_df.itertuples(), 1):
                if i % 100 == 0:  # pragma: no cover
                    logger.debug(
                        "%d/%d records parsed, %.2fs", *(i, row_count, time.time() - t0)
                    )
                    t0 = time.time()

                # init record dictionary with data already known from WACZ files
                record = {
                    "url": row.url,
                    "status": "active",
                    "cdx_warc_filename": row.filename,
                    "cdx_title": row.title,
                    "cdx_offset": row.offset,
                    "cdx_length": row.length,
                }

                # add base64 encoded full HTML
                html_content = wacz_client.get_website_content(
                    str(row.filename),
                    str(row.offset),
                    decode=False,
                )
                record["html_base64"] = base64.b64encode(html_content).decode()  # type: ignore[arg-type]

                # add response headers
                record["response_headers"] = wacz_client.get_response_headers(  # type: ignore[assignment]
                    str(row.filename), str(row.offset)
                )

                all_records.append(record)

        # add status=deleted records if current and previous URL lists are passed
        if urls_file and previous_sitemap_urls_file:
            all_records.extend(
                self._generate_delete_records(urls_file, previous_sitemap_urls_file)
            )

        # create dataframe from all dictionaries
        websites_records_df = pd.DataFrame(all_records)

        # replace NaN with python None
        websites_records_df = websites_records_df.where(  # type: ignore[call-overload]
            pd.notna(websites_records_df), None
        )

        # remove duplicate URLs
        websites_records_df = self._remove_duplicate_urls(websites_records_df)

        logger.info(f"{len(websites_records_df)} records generated.")

        # init instance of CrawlRecords and cache
        self._websites_records = CrawlRecords(websites_records_df)

        return self._websites_records

    def _generate_delete_records(
        self, current_urls_filepath: str, previous_urls_filepath: str
    ) -> list[dict]:
        """Generate records for URLs that have been removed since last crawl.

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
        logger.info(f"Creating {len(deleted_urls)} status=deleted records.")

        return [
            {
                "url": url,
                "status": "deleted",
            }
            for url in deleted_urls
            if url and url != ""
        ]

    def _remove_duplicate_urls(self, websites_records_df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate URLs.

        The instance with the last CDX offset is used, which is a somewhat arbitrary
        attempt to used the last instance crawled, but it likely makes no difference given
        the short timeframe of the crawl.
        """
        return (
            websites_records_df.sort_values("cdx_offset")
            .drop_duplicates(subset="url", keep="last")
            .reset_index(drop=True)
        )


class CrawlRecords:
    """Class to represent and serialize structured records extracted from crawl."""

    def __init__(self, records_df: pd.DataFrame) -> None:
        self.records_df = records_df

    # ruff: noqa: D105
    def __repr__(self) -> str:
        return f"<CrawlRecords: {len(self.records_df)} records>"  # pragma: no cover

    def to_xml(self) -> bytes:
        """Create an XML byte string of crawl record.

        This returns an XML byte string in the format:
        <records>
            <record>...</record>, ...
        </records>
        """
        root = ET.Element("records")
        for _, row in self.records_df.iterrows():
            item = ET.Element("record")
            root.append(item)
            for col in self.records_df.columns:
                cell = ET.Element(col)
                cell.text = str(row[col])
                item.append(cell)
        return ET.tostring(root, encoding="utf-8", method="xml")

    def to_jsonl(self) -> bytes:
        """Create JSONLines buffer from crawl record."""
        buffer = io.StringIO()
        with jsonlines.Writer(buffer) as writer:
            for _, row in self.records_df.iterrows():
                writer.write(row.to_dict())
        return buffer.getvalue().encode("utf-8")

    def write(self, filepath: str) -> None:
        """Serialize records in various file formats.

        The file format is determined by the filepath file extension.
        """
        logger.info("Writing records to: %s", filepath)

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
                self.records_df.to_csv(filepath, sep="\t", index=False)
        elif file_format == "csv":
            with smart_open.open(filepath, "wb") as f:
                self.records_df.to_csv(filepath, sep=",", index=False)
        else:
            message = f"File format '{file_format}' not recognized"
            raise NotImplementedError(message)
