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
from harvester.utils import require_container
from harvester.wacz import WACZClient

logger = logging.getLogger(__name__)


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
    required=False,
    help="Filepath to write metadata records to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.xml.  Supported file type extensions: [xml,tsv,csv].",
)
@click.option(
    "--include-fulltext",
    is_flag=True,
    help="Set to include parsed fulltext from website in generated structured metadata.",
)
@click.pass_context
def generate_metadata_records(
    ctx: click.Context,
    wacz_input_file: str,
    metadata_output_file: str,
    include_fulltext: bool,
) -> None:
    """Generate metadata records from a WACZ file.

    This is a convenience CLI command.  Most commonly, the command 'harvest' will be used
    that performs a web crawl and generates metadata records from that crawl as under the
    umbrella of a single command.  This CLI command would be useful if a crawl is already
    completed (a WACZ file exists) and only the generation of metadata records is needed.
    """
    logger.info("Parsing WACZ archive file")
    parser = CrawlMetadataParser(wacz_input_file)
    parser.generate_metadata(include_fulltext=include_fulltext).write(
        metadata_output_file
    )
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
    "--sitemap-from-date",
    required=False,
    default=None,
    type=str,
    help="YYYY-MM-DD string to filter websites modified after this date in sitemaps",
)
@click.option(
    "--wacz-output-file",
    required=False,
    help="Filepath to write WACZ archive file to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.xml.",
)
@click.option(
    "--metadata-output-file",
    required=False,
    help="Filepath to write metadata records to. Can be a local filepath or an S3 URI, "
    "e.g. s3://bucketname/filename.xml.  Supported file type extensions: [xml,tsv,csv].",
)
@click.option(
    "--include-fulltext",
    is_flag=True,
    help="Set to include parsed fulltext from website in generated structured metadata.",
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
    sitemap_from_date: str,
    wacz_output_file: str,
    metadata_output_file: str,
    include_fulltext: bool,
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

    logger.info("Preparing for harvest name: '%s'", crawl_name)
    crawler = Crawler(
        crawl_name,
        config_yaml_file,
        sitemap_from_date=sitemap_from_date,
        num_workers=num_workers,
        btrix_args_json=btrix_args_json,
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
        parser.generate_metadata(include_fulltext=include_fulltext).write(
            metadata_output_file
        )
        logger.info("Metadata records successfully written")

    logger.info(
        "Total elapsed: %s",
        str(
            timedelta(seconds=perf_counter() - ctx.obj["START_TIME"]),
        ),
    )
