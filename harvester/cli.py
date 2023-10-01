"""harvester.cli"""
# ruff: noqa: FBT001, ARG001

import logging
import os
from time import perf_counter

import click

from harvester.config import configure_logger, configure_sentry

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
