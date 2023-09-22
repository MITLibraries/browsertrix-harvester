"""browsertrix_harvester.crawl"""

import logging
import os
import shutil
import subprocess

import smart_open  # type: ignore[import]

from browsertrix_harvester.exceptions import ConfigYamlError
from browsertrix_harvester.utils import require_container

logger = logging.getLogger(__name__)


class Crawler:
    """Class that manages browsertrix crawls."""

    DOCKER_CONTAINER_CONFIG_YAML_FILEPATH = "/btrixharvest/crawl-config.yaml"

    # ruff: noqa: FBT001, FBT002
    def __init__(
        self,
        crawl_name: str,
        config_yaml_filepath: str,
        sitemap_from_date: str | None = None,
        num_workers: int = 4,
    ) -> None:
        self.crawl_name = crawl_name
        self.config_yaml_filepath = config_yaml_filepath
        self.sitemap_from_date = sitemap_from_date
        self.num_workers = num_workers

    @property
    def crawl_output_dir(self) -> str:
        return f"/crawls/collections/{self.crawl_name}"

    @property
    def wacz_filepath(self) -> str:
        """Location of WACZ archive after crawl is completed."""
        return f"{self.crawl_output_dir}/{self.crawl_name}.wacz"

    @require_container
    def crawl(self) -> tuple[int, list[str], list[str]]:
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

        stdout, stderr = [], []
        # ruff: noqa: S603
        with subprocess.Popen(
            cmd,
            cwd="/crawls",
            env=self._get_subprocess_env_vars(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ) as process:
            if process.stdout is not None:  # pragma: no cover
                for line in process.stdout:
                    # ruff: noqa: PLW2901
                    line = line.strip()
                    if line is not None and line != "":
                        logger.debug(line)
                        stdout.append(line)
            if process.stderr is not None:  # pragma: no cover
                for line in process.stderr:
                    # ruff: noqa: PLW2901
                    line = line.strip()
                    if line is not None and line != "":
                        logger.debug(line)
                        stderr.append(line)
            return_code = process.wait()
        return return_code, stdout, stderr

    def _copy_config_yaml_local(self) -> None:
        """Download and/or copy config YAML to expected location"""
        logger.info(
            "creating docker container copy of config YAML from: %s",
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
                "could not open file locally or from S3: %s", self.config_yaml_filepath
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
            logger.warning("removing pre-existing crawl at: %s", self.crawl_output_dir)
            shutil.rmtree(self.crawl_output_dir)

    def _build_subprocess_command(self) -> list:
        """Build subprocess command that will execute browsertrix-crawler."""
        cmd = [
            # fmt: off
            "crawl",
            "--collection", self.crawl_name,
            "--config", self.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH,
            "--workers", str(self.num_workers),
            "--useSitemap",
            "--logging", "stats",
            # fmt: on
        ]
        if self.sitemap_from_date is not None:
            cmd.extend(["--sitemapFromDate", self.sitemap_from_date])
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
