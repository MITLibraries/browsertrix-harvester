"""tests.test_crawler"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from harvester.exceptions import (
    ConfigYamlError,
    RequiresContainerContextError,
    WaczFileDoesNotExist,
)


def test_crawler_config_yaml_copy_success(
    create_mocked_crawler, mock_config_yaml_open, fake_config_yaml_content
):
    crawler = create_mocked_crawler()
    crawler._copy_config_yaml_local()

    # assert input file was opened for read and output file was opened for write
    mock_config_yaml_open.assert_any_call(crawler.config_yaml_filepath, "rb")
    mock_config_yaml_open.assert_any_call(
        crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH, "wb"
    )

    # assert data written is expected data from config YAML
    handle = mock_config_yaml_open()
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
    assert os.getenv("VIRTUAL_ENV", None)
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

    base_args = {
        "crawl",
        "--collection",
        crawler.crawl_name,
        "--config",
        crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH,
        "--useSitemap",
        "--logging",
        "stats",
        "--workers",
        str(crawler.num_workers),
    }

    # assert without sitemap_from_date
    crawler.sitemap_from_date = None
    command = crawler._build_subprocess_command()
    assert set(command) == base_args

    # assert when sitemap_from_date is included
    from_date = "1979-01-01"
    crawler.sitemap_from_date = from_date
    command = crawler._build_subprocess_command()
    assert set(command) == base_args.union({"--sitemapFromDate", from_date})

    # assert inclusion of misc btrix args JSON
    crawler = create_mocked_crawler()
    crawler.btrix_args_json = json.dumps({"--miscArg1": "value1", "--miscArg2": "value2"})
    command = crawler._build_subprocess_command()
    assert set(command) == base_args.union(
        {"--miscArg1", "value1", "--miscArg2", "value2"}
    )


@pytest.mark.usefixtures("_mock_inside_container", "_mock_wacz_file_exists")
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


@pytest.mark.usefixtures("_mock_inside_container")
def test_crawl_fails_to_create_wacz_raises_error(create_mocked_crawler):
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

    with pytest.raises(WaczFileDoesNotExist), patch(
        "subprocess.Popen", return_value=mock_process
    ):
        crawler.crawl()
