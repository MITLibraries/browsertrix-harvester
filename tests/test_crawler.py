import os

import pytest

from browsertrix_harvester.exceptions import (
    ConfigYamlError,
    RequiresContainerContextError,
)


def test_crawler_config_yaml_copy_success(
    create_mocked_crawler, mock_smart_open, fake_config_yaml_content
):
    mocked_crawler = create_mocked_crawler()
    mocked_crawler.copy_config_yaml_local()

    # assert input file was opened for read and output file was opened for write
    mock_smart_open.assert_any_call(mocked_crawler.config_yaml_filepath, "rb")
    mock_smart_open.assert_any_call(
        mocked_crawler.DOCKER_CONTAINER_CONFIG_YAML_FILEPATH, "wb"
    )

    # assert data written is expected data from config YAML
    handle = mock_smart_open()
    handle.write.assert_called_once_with(fake_config_yaml_content)


@pytest.mark.raise_smart_open_exception
def test_crawler_config_yaml_copy_fail(create_mocked_crawler):
    mock_crawler = create_mocked_crawler()
    # assert ConfigYamlError thrown
    with pytest.raises(ConfigYamlError):
        mock_crawler.copy_config_yaml_local()


def test_crawler_properties(create_mocked_crawler):
    mocked_crawler = create_mocked_crawler()
    assert (
        mocked_crawler.crawl_output_dir
        == f"/crawls/collections/{mocked_crawler.crawl_name}"
    )
    assert (
        mocked_crawler.wacz_filepath
        == f"{mocked_crawler.crawl_output_dir}/{mocked_crawler.crawl_name}.wacz"
    )


def test_crawler_env_var_manipulation(create_mocked_crawler):
    assert os.getenv("VIRTUAL_ENV", None) is not None
    mocked_crawler = create_mocked_crawler()
    # ruff: noqa: SLF001
    env_vars = mocked_crawler._get_subprocess_env_vars()
    assert "VIRTUAL_ENV" not in env_vars


def test_crawl_docker_context_decorator(create_mocked_crawler):
    with pytest.raises(RequiresContainerContextError):
        create_mocked_crawler().crawl()
