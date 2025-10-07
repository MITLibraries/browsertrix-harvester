"""harvester.crawl"""

import json
import logging
import os
import shutil
import subprocess

import smart_open  # type: ignore[import]

from harvester.exceptions import ConfigYamlError, WaczFileDoesNotExist
from harvester.utils import require_container

logger = logging.getLogger(__name__)


class Crawler:
    """Class that manages browsertrix crawls."""

    DOCKER_CONTAINER_CONFIG_YAML_FILEPATH = "/browsertrix-harvester/crawl-config.yaml"

    def __init__(
        self,
        crawl_name: str,
        config_yaml_filepath: str,
        sitemap_from_date: str | None = None,
        num_workers: int = 4,
        btrix_args_json: str | None = None,
    ) -> None:
        self.crawl_name = crawl_name
        self.config_yaml_filepath = config_yaml_filepath
        self.sitemap_from_date = sitemap_from_date
        self.num_workers = num_workers
        self.btrix_args_json = btrix_args_json

        self._crawl_status_details: list[dict] = []

    @property
    def crawl_output_dir(self) -> str:
        return f"/crawls/collections/{self.crawl_name}"

    @property
    def wacz_filepath(self) -> str:
        """Location of WACZ archive after crawl is completed."""
        return f"{self.crawl_output_dir}/{self.crawl_name}.wacz"

    @require_container
    def crawl(self) -> int:
        """Perform a browsertrix crawl.

        This method is decorated with @required_container that will prevent it from
        running if not inside a Docker container with the alias executable "crawl" that
        is a symlink to the Browsertrix node application.

        The crawl itself is invoked via a subprocess OS command that runs and waits for
        the crawl to complete.
        """
        # copy config yaml to known, local file location
        self._copy_config_yaml_local()

        # remove pre-existing crawl
        self._remove_previous_crawl()

        # build subprocess command
        cmd = self._build_subprocess_command()

        # ruff: noqa: S603
        with subprocess.Popen(
            cmd,
            cwd="/crawls",
            env=self._get_subprocess_env_vars(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            self._handle_subprocess_logging(process)
            return_code = process.wait()
            for line in self._crawl_status_details[-3:]:
                logger.info(line)

        # raise exception if WACZ file not found from crawl
        if not os.path.exists(self.wacz_filepath):
            msg = f"WACZ file not found at expected path: {self.wacz_filepath}"
            raise WaczFileDoesNotExist(msg)

        return return_code

    def _handle_subprocess_logging(self, process: subprocess.Popen[str]) -> None:
        """Handle logging of subprocess stdout and stderr."""
        if process.stdout:  # pragma: no cover
            for line in process.stdout:
                line = line.strip()  # noqa: PLW2901
                if line and line != "":
                    if '"context":"crawlStatus"' in line:
                        self._log_crawl_count_status(line)
                    logger.debug(line)
        if process.stderr:  # pragma: no cover
            for line in process.stderr:
                line = line.strip()  # noqa: PLW2901
                if line and line != "":
                    logger.debug(line)

    def _log_crawl_count_status(self, log_line: str, buffer_size: int = 100) -> None:
        """Occasionally log crawl status counts.

        Parse browsertrix log lines with context=crawlStatus, logging the status only
        every buffer_size count.
        """
        try:
            line_data = json.loads(log_line)
        except json.JSONDecodeError:
            return

        details = {
            k: v
            for k, v in line_data.get("details", {}).items()
            if k in ["crawled", "total", "pending", "failed", "limit"]
        }

        self._crawl_status_details.append(details)

        if len(self._crawl_status_details) == buffer_size:
            logger.info(self._crawl_status_details[-1])
            self._crawl_status_details = []

    def _copy_config_yaml_local(self) -> None:
        """Download and/or copy config YAML to expected location"""
        logger.info(
            "Creating docker container copy of config YAML from: %s",
            self.config_yaml_filepath,
        )
        try:
            with smart_open.open(
                self.config_yaml_filepath, "rb"
            ) as f_in, smart_open.open(
                self.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH, "wb"
            ) as f_out:
                f_out.write(f_in.read())
        except Exception as e:
            logger.exception(
                "Could not open file locally or from S3: %s", self.config_yaml_filepath
            )
            raise ConfigYamlError from e

    def _remove_previous_crawl(self) -> None:
        """Remove previous crawl if exists.

        Browsertrix will APPEND to previous crawls -- WARC files, indexed data, etc. -- if
        the crawl directory already exists.  While the WACZ file will overwrite, this can
        still introduce some unneeded complexity for a container that really should only
        ever have one crawl per invocation.
        """
        if os.path.exists(self.crawl_output_dir):
            logger.warning("Removing pre-existing crawl at: %s", self.crawl_output_dir)
            shutil.rmtree(self.crawl_output_dir)

    def _build_subprocess_command(self) -> list:
        """Build subprocess command that will execute browsertrix-crawler with args.

        Build dictionary of key/value pairs from defaults defined here, common arguments
        broken out as explicit CLI arguments, and any additional arguments passed as a
        JSON string via CLI command that browsertrix accepts.  They are applied and
        overridden in that order, then serialized as a flat list for OS command.
        """
        # build base command
        cmd = [
            "crawl",
            "--useSitemap",
        ]

        # default args
        btrix_args = {
            "--collection": self.crawl_name,
            "--config": self.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH,
            "--logging": "stats",
        }

        # apply common arguments as standalone CLI arguments
        if self.num_workers:
            btrix_args["--workers"] = str(self.num_workers)
        if self.sitemap_from_date:
            btrix_args["--sitemapFromDate"] = self.sitemap_from_date

        # lastly, if JSON string of btrix args provided, parse and apply
        if self.btrix_args_json:
            btrix_additional_args = json.loads(self.btrix_args_json)
            for arg_name, arg_value in btrix_additional_args.items():
                btrix_args[arg_name] = str(arg_value)

        # flatten to list and extend base command
        btrix_args_list = [item for sublist in btrix_args.items() for item in sublist]
        cmd.extend(btrix_args_list)

        logger.info(cmd)

        return cmd

    @staticmethod
    def _get_subprocess_env_vars() -> dict:
        """Prepare env vars for subprocess that calls browsertrix-crawler

        Browsertrix is a node application that runs in this container, and relies on
        some global python libraries.  Because this CLI app, browsertrix-harvester, runs
        in a pipenv virtual environment, it's required to UNSET a couple of env vars when
        calling the os command to crawl.
        """
        env_vars = dict(os.environ)
        env_vars.pop("VIRTUAL_ENV", None)
        return env_vars
