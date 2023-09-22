"""tests.test_crawler"""

import os
from unittest.mock import MagicMock, patch

import pytest

from browsertrix_harvester.exceptions import (
    ConfigYamlError,
    RequiresContainerContextError,
)


def test_crawler_config_yaml_copy_success(
    create_mocked_crawler, mock_smart_open, fake_config_yaml_content
):
    crawler = create_mocked_crawler()
    crawler._copy_config_yaml_local()

    # assert input file was opened for read and output file was opened for write
    mock_smart_open.assert_any_call(crawler.config_yaml_filepath, "rb")
    mock_smart_open.assert_any_call(crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH, "wb")

    # assert data written is expected data from config YAML
    handle = mock_smart_open()
    handle.write.assert_called_once_with(fake_config_yaml_content)


@pytest.mark.raise_smart_open_exception
def test_crawler_config_yaml_copy_fail(create_mocked_crawler):
    mock_crawler = create_mocked_crawler()
    # assert ConfigYamlError thrown
    with pytest.raises(ConfigYamlError):
        mock_crawler._copy_config_yaml_local()


def test_crawler_properties(create_mocked_crawler):
    crawler = create_mocked_crawler()
    assert (
        crawler.wacz_filepath == f"{crawler.crawl_output_dir}/{crawler.crawl_name}.wacz"
    )


def test_crawler_env_var_manipulation(create_mocked_crawler):
    assert os.getenv("VIRTUAL_ENV", None) is not None
    crawler = create_mocked_crawler()
    # ruff: noqa: SLF001
    env_vars = crawler._get_subprocess_env_vars()
    assert "VIRTUAL_ENV" not in env_vars


def test_crawl_docker_context_decorator(create_mocked_crawler):
    with pytest.raises(RequiresContainerContextError):
        create_mocked_crawler().crawl()


def test_crawl_remove_previous_crawl(create_mocked_crawler):
    crawler = create_mocked_crawler()

    # assert removal
    with patch("os.path.exists", return_value=True), patch(
        "shutil.rmtree"
    ) as mock_rmtree:
        crawler._remove_previous_crawl()
        mock_rmtree.assert_called_once_with(crawler.crawl_output_dir)

    # assert skips removal
    with patch("os.path.exists", return_value=False), patch(
        "shutil.rmtree"
    ) as mock_rmtree:
        crawler._remove_previous_crawl()
        mock_rmtree.assert_not_called()


def test_crawler_build_command(create_mocked_crawler):
    crawler = create_mocked_crawler()

    # assert without sitemap_from_date
    crawler.sitemap_from_date = None
    command = crawler._build_subprocess_command()
    assert command == [
        # fmt: off
        "crawl",
        "--collection", crawler.crawl_name,
        "--config", crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH,
        "--workers", str(crawler.num_workers),
        "--useSitemap",
        "--logging", "stats",
        # fmt: on
    ]

    # assert when sitemap_from_date is included
    from_date = "1979-01-01"
    crawler.sitemap_from_date = from_date
    command = crawler._build_subprocess_command()
    assert command == [
        # fmt: off
        "crawl",
        "--collection", crawler.crawl_name,
        "--config", crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH,
        "--workers", str(crawler.num_workers),
        "--useSitemap",
        "--logging", "stats",
        "--sitemapFromDate", from_date
        # fmt: on
    ]


@pytest.mark.usefixtures("_mock_inside_container")
def test_crawl_success(create_mocked_crawler):
    crawler = create_mocked_crawler()

    stdouts = ["stdout1", "", "stdout2"]
    stderrs = ["stderr1", "stderr2", ""]

    # create a mock subprocess process with
    mock_process = MagicMock()
    mock_process.__enter__.return_value = mock_process
    mock_process.__exit__.return_value = None
    mock_process.stdout = iter(stdouts)
    mock_process.stderr = iter(stderrs)
    mock_process.wait.return_value = 0

    with patch("subprocess.Popen", return_value=mock_process):
        return_code, stdout, stderr = crawler.crawl()
        assert return_code == 0
        assert stdout == [_ for _ in stdouts if _ != ""]  # empty strings are skipped
        assert stderr == [_ for _ in stderrs if _ != ""]  # empty strings are skipped
