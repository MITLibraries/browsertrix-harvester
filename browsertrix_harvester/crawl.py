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

    LOCAL_CONFIG_YAML_FILEPATH = "/btxharvest/crawl-config.yaml"

    # ruff: noqa: FBT001, FBT002
    def __init__(
        self,
        crawl_name: str,
        config_yaml_filepath: str,
        sitemap_from_date: str | None = None,
        num_workers: int = 4,
        overwrite: bool = True,
    ) -> None:
        self.crawl_name = crawl_name
        self.config_yaml_filepath = config_yaml_filepath
        self.sitemap_from_date = sitemap_from_date
        self.num_workers = num_workers
        self.overwrite = overwrite

        # establish local copy of config YAML in container
        self._copy_config_yaml()

    @property
    def wacz_filepath(self) -> str:
        """Location of WACZ archive after crawl is completed."""
        return f"{self.crawl_output_dir}/{self.crawl_name}.wacz"

    @property
    def crawl_output_dir(self) -> str:
        return f"/crawls/collections/{self.crawl_name}"

    def _copy_config_yaml(self) -> None:
        """Download and/or copy config YAML to expected location"""
        logger.info(
            "creating docker container copy of config YAML from: %s",
            self.config_yaml_filepath,
        )
        try:
            with smart_open.open(self.config_yaml_filepath, "rb") as f_in, open(
                self.LOCAL_CONFIG_YAML_FILEPATH, "wb"
            ) as f_out:
                f_out.write(f_in.read())
        except Exception as e:
            logger.exception(
                "could not open file locally or from S3: %s", self.config_yaml_filepath
            )
            raise ConfigYamlError from e

    @require_container
    def crawl(self) -> tuple[int, list[str], list[str]]:
        """Perform a browsertrix crawl.

        This method is decorated with @required_container that will prevent it from
        running if not inside a Docker container with the alias executable "crawl" that
        is a symlink to the Browsertrix node application.

        The crawl itself is invoked via a subprocess OS command that runs and waits for
        the crawl to complete.
        """
        cmd = [
            # fmt: off
            "crawl",
            "--collection", self.crawl_name,
            "--config", self.LOCAL_CONFIG_YAML_FILEPATH,
            "--workers", str(self.num_workers),
            "--useSitemap",
            "--logging", "stats",
            # fmt: on
        ]
        if self.sitemap_from_date is not None:
            cmd.extend(["--sitemapFromDate", self.sitemap_from_date])
        logger.info(cmd)

        # remove pre-existing crawl by crawl-name if overwrite=True
        if self.overwrite and os.path.exists(self.crawl_output_dir):
            logger.info("removing pre-existing crawl at: %s", self.crawl_output_dir)
            shutil.rmtree(self.crawl_output_dir)

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
            if process.stdout is not None:
                for line in process.stdout:
                    # ruff: noqa: PLW2901
                    line = line.strip()
                    if line is not None and line != "":
                        logger.debug(line)
                        stdout.append(line)
            if process.stderr is not None:
                for line in process.stderr:
                    # ruff: noqa: PLW2901
                    line = line.strip()
                    if line is not None and line != "":
                        logger.debug(line)
                        stderr.append(line)
            return_code = process.wait()
        return return_code, stdout, stderr

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
