"""harvester.cli"""

# ruff: noqa: FBT001

import logging
import os
from datetime import UTC, datetime, timedelta
from time import perf_counter

import click
import smart_open  # type: ignore[import]

from harvester.config import configure_logger, configure_sentry
from harvester.crawl import Crawler
from harvester.metadata import CrawlMetadataParser
from harvester.sitemaps import SitemapsParser
from harvester.utils import require_container
from harvester.wacz import WACZClient

logger = logging.getLogger(__name__)

CRAWL_SITEMAP_URLS_FILEPATH = "/tmp/urls.txt"  # noqa: S108
ALL_SITEMAP_URLS_FILEPATH = "/tmp/urls-all.txt"  # noqa: S108


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "-v", "--verbose", is_flag=True, help="Pass to log at debug level instead of info"
)
@click.pass_context
def main(ctx: click.Context, verbose: bool) -> None:
    ctx.ensure_object(dict)
    ctx.obj["START_TIME"] = perf_counter()
    root_logger = logging.getLogger()
    logger.info(configure_logger(root_logger, verbose))
    logger.info(configure_sentry())
    logger.info("Running process")


@main.command()
def docker_shell() -> None:
    """Run a bash shell inside the docker container.

    The decorator utils.require_container is used to ensure a docker container context
    for running a bash shell.
    """

    @require_container
    def bash_shell_with_confirmed_container_context() -> None:
        # ruff: noqa: S605, S607
        os.system("bash")

    bash_shell_with_confirmed_container_context()


@main.command()
@click.option(
    "--wacz-input-file",
    required=True,
    type=str,
    help="Filepath to WACZ archive from crawl",
)
@click.option(
    "--url",
    required=True,
    type=str,
    help="Website URL to parse HTML content for",
)
def parse_url_content(wacz_input_file: str, url: str) -> None:
    """Get HTML for a single URL.

    This CLI command extracts the fully rendered content of a specific URL from a web
    crawl WACZ file. By printing/echoing the contents, this can be redirected via stdout
    in the calling context.
    """
    # set logging level to ERROR to keep stdout clear of logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.ERROR)

    # parse crawled content for URL
    with WACZClient(wacz_input_file) as wacz_client:
        html_content = wacz_client.get_website_content_by_url(url, decode=True)

    click.echo(html_content)


@main.command()
@click.option(
    "--wacz-input-file",
    required=True,
    type=str,
    help="Filepath to WACZ archive from crawl",
)
@click.option(
    "--metadata-output-file",
    required=True,
    help="Filepath to write metadata records to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.jsonl.  Supported file type extensions: "
    "[jsonl, xml,tsv,csv].",
)
@click.option(
    "--include-fulltext",
    is_flag=True,
    help="Set to include parsed fulltext from website in generated structured metadata.",
)
@click.option(
    "--extract-fulltext-keywords",
    is_flag=True,
    help="Set to use YAKE to extract keywords from fulltext.",
)
@click.pass_context
def generate_metadata_records(
    ctx: click.Context,
    wacz_input_file: str,
    metadata_output_file: str,
    include_fulltext: bool,
    extract_fulltext_keywords: bool,
) -> None:
    """Generate metadata records from a WACZ file.

    This is a convenience CLI command.  Most commonly, the command 'harvest' will be used
    that performs a web crawl and generates metadata records from that crawl as under the
    umbrella of a single command.  This CLI command would be useful if a crawl is already
    completed (a WACZ file exists) and only the generation of metadata records is needed.
    """
    logger.info("Parsing WACZ archive file")
    parser = CrawlMetadataParser(wacz_input_file)
    crawl_metadata_records = parser.generate_metadata(
        include_fulltext=include_fulltext,
        extract_fulltext_keywords=extract_fulltext_keywords,
    )
    crawl_metadata_records.write(metadata_output_file)
    logger.info("Metadata records successfully written")
    logger.info(
        "Total elapsed: %s",
        str(
            timedelta(seconds=perf_counter() - ctx.obj["START_TIME"]),
        ),
    )


@main.command()
@click.option(
    "--config-yaml-file",
    required=True,
    type=str,
    help="Filepath of browsertrix config YAML. Can be a local filepath or an S3 "
    "URI, e.g. s3://bucketname/crawl-config.yaml",
)
@click.option(
    "--crawl-name",
    required=False,
    type=str,
    default=f"crawl-{datetime.now(tz=UTC).strftime('%Y-%m-%d-%H%M%S')}",
    help="Optional override for crawl name. [Default 'crawl-<TIMESTAMP>']",
)
@click.option(
    "--parse-sitemaps-pre-crawl",
    is_flag=True,
    help="Set to parse passed sitemaps pre-crawl, generating a file of URLs that will be "
    "used to seed the crawl.  If set, --sitemap-root is required and --sitemap-path is "
    "optional.",
)
@click.option(
    "--sitemap-root",
    required=False,
    default=None,
    type=str,
    help="Root URL for sitemap parsing, e.g. 'https://libraries.mit.edu/'.",
)
@click.option(
    "--sitemap-path",
    required=False,
    multiple=True,
    type=str,
    help="Path(s) to sitemap files relative to --sitemap-root, can be specified multiple "
    "times, e.g. 'sitemap.xml', 'news/sitemap.xml', etc.",
)
@click.option(
    "--sitemap-from-date",
    required=False,
    default=None,
    type=str,
    help="YYYY-MM-DD string to filter websites modified on/after this date in sitemaps",
)
@click.option(
    "--sitemap-to-date",
    required=False,
    default=None,
    type=str,
    help="YYYY-MM-DD string to filter websites modified before this date in sitemaps",
)
@click.option(
    "--wacz-output-file",
    required=False,
    help="Filepath to write WACZ archive file to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.jsonl.",
)
@click.option(
    "--metadata-output-file",
    required=False,
    help="Filepath to write metadata records to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.jsonl.  Supported file type extensions: "
    "[jsonl,xml,tsv,csv].",
)
@click.option(
    "--sitemap-urls-output-file",
    required=False,
    help="If --parse-sitemaps-pre-crawl is set, optionally write a text file of "
    "discoveredURLs parsed from sitemap(s).",
)
@click.option(
    "--previous-sitemap-urls-file",
    required=False,
    help="If passed, a previous file with all URLs from sitemap parsing will be read and "
    "used to determine if URLs have since been removed and should be marked as "
    "'deleted' as an output metadata record.",
)
@click.option(
    "--include-fulltext",
    is_flag=True,
    help="Set to include parsed fulltext from website in generated structured metadata.",
)
@click.option(
    "--extract-fulltext-keywords",
    is_flag=True,
    help="Set to use YAKE to extract keywords from fulltext.",
)
@click.option(
    "--num-workers",
    default=2,
    required=False,
    type=int,
    help="Number of parallel thread workers for crawler. [Default 2]",
)
@click.option(
    "--btrix-args-json",
    default=None,
    required=False,
    type=str,
    help="JSON formatted string of additional args to pass to browsertrix-crawler, "
    "https://github.com/webrecorder/browsertrix-crawler#crawling-configuration"
    "-options",
)
@click.pass_context
def harvest(
    ctx: click.Context,
    crawl_name: str,
    config_yaml_file: str,
    parse_sitemaps_pre_crawl: bool,
    sitemap_root: str,
    sitemap_path: tuple[str, ...],
    sitemap_from_date: str,
    sitemap_to_date: str,
    wacz_output_file: str,
    metadata_output_file: str,
    sitemap_urls_output_file: str,
    previous_sitemap_urls_file: str,
    include_fulltext: bool,
    extract_fulltext_keywords: bool,
    num_workers: int,
    btrix_args_json: str,
) -> None:
    """Perform crawl and generate metadata records.

    Perform a web crawl and generate metadata records from the resulting WACZ file.
    """
    if not wacz_output_file and not metadata_output_file:
        msg = (
            "One or both of arguments --wacz-output-file and --metadata-output-file "
            "must be set.  Exiting without performing a crawl."
        )
        logger.error(msg)
        return

    # handle optional, pre-crawl sitemap parsing
    urls_file = None
    if parse_sitemaps_pre_crawl:
        sitemaps_parser = SitemapsParser(sitemap_root, sitemap_paths=sitemap_path)
        sitemaps_parser.parse()

        # create a local, temporary URLs file for crawl use, optionally limited by dates
        sitemaps_parser.write_urls(
            CRAWL_SITEMAP_URLS_FILEPATH,
            sitemap_from_date=sitemap_from_date,
            sitemap_to_date=sitemap_to_date,
        )
        urls_file = CRAWL_SITEMAP_URLS_FILEPATH

        # write all discovered sitemap URLs to a local, temporary file
        sitemaps_parser.write_urls(ALL_SITEMAP_URLS_FILEPATH)

    # instantiate crawler
    logger.info("Preparing for harvest name: '%s'", crawl_name)
    crawler = Crawler(
        crawl_name,
        config_yaml_file,
        sitemap_from_date=sitemap_from_date,
        sitemap_to_date=sitemap_to_date,
        num_workers=num_workers,
        btrix_args_json=btrix_args_json,
        urls_file=urls_file,
    )
    crawler.crawl()
    logger.info("Crawl complete, WACZ archive located at: %s", crawler.wacz_filepath)

    # upload WACZ if output file destination provided
    if wacz_output_file:
        logger.info("Writing WACZ archive to: %s", wacz_output_file)
        with smart_open.open(wacz_output_file, "wb") as wacz_out, smart_open.open(
            crawler.wacz_filepath, "rb"
        ) as wacz_in:
            wacz_out.write(wacz_in.read())

    # parse crawl and generate metadata records
    if metadata_output_file:
        logger.info("Parsing WACZ archive file")
        parser = CrawlMetadataParser(crawler.wacz_filepath)
        crawl_metadata_records = parser.generate_metadata(
            include_fulltext=include_fulltext,
            extract_fulltext_keywords=extract_fulltext_keywords,
            urls_file=ALL_SITEMAP_URLS_FILEPATH,
            previous_sitemap_urls_file=previous_sitemap_urls_file,
        )
        crawl_metadata_records.write(metadata_output_file)
        logger.info("Metadata records successfully written")

    # optionally, create a text file containing ALL URLs discovered
    # this supports future crawls analyzing this snapshot of sitemap URLs
    if sitemap_urls_output_file:
        if not os.path.exists(ALL_SITEMAP_URLS_FILEPATH):
            logger.error(
                "Cannot write sitemap URLs: /tmp/urls-all.txt not found. "
                "Ensure --parse-sitemaps-pre-crawl is set."
            )
        else:
            logger.info("Writing all sitemap URLs to: %s", sitemap_urls_output_file)
            with open(ALL_SITEMAP_URLS_FILEPATH) as urls_in, smart_open.open(
                sitemap_urls_output_file, "w"
            ) as urls_out:
                urls_out.write(urls_in.read())

    logger.info(
        "Total elapsed: %s",
        str(
            timedelta(seconds=perf_counter() - ctx.obj["START_TIME"]),
        ),
    )
