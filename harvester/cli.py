"""harvester.cli"""
# ruff: noqa: FBT001, ARG001

import logging
import os
from datetime import UTC, datetime, timedelta
from time import perf_counter

import click
import smart_open  # type: ignore[import]

from harvester.config import configure_logger, configure_sentry
from harvester.crawl import Crawler

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
@click.pass_context
def shell(ctx: click.Context) -> None:
    """Run a bash shell inside the docker container."""
    # ruff: noqa: S605, S607
    os.system("bash")


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
    num_workers: int,
    btrix_args_json: str,
) -> None:
    """Perform a web crawl and parse structured data."""
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
        logger.info("writing WACZ archive to: %s", wacz_output_file)
        with smart_open.open(wacz_output_file, "wb") as wacz_out, smart_open.open(
            crawler.wacz_filepath, "rb"
        ) as wacz_in:
            wacz_out.write(wacz_in.read())

    elapsed_time = perf_counter() - ctx.obj["START_TIME"]
    logger.info(
        "Total time to complete harvest: %s",
        str(
            timedelta(seconds=elapsed_time),
        ),
    )
