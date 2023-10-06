import os
from unittest.mock import Mock, mock_open, patch

import pytest
from click.testing import CliRunner

from harvester.crawl import Crawler
from harvester.exceptions import WaczFileDoesNotExist
from harvester.metadata import CrawlMetadataParser
from harvester.wacz import WACZClient


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/path/to/virtual/env")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def fake_config_yaml_content():
    return "fake config YAML data"


@pytest.fixture
def mock_config_yaml_open(fake_config_yaml_content, request):
    should_raise = request.node.get_closest_marker(name="raise_smart_open_exception")
    if should_raise:
        mock_s_open = Mock(side_effect=Exception("Mocked exception"))
    else:
        mock_s_open = mock_open(read_data=fake_config_yaml_content)
    with patch("smart_open.open", mock_s_open):
        yield mock_s_open


@pytest.fixture
def create_mocked_crawler(mock_config_yaml_open):
    def crawler_factory() -> Crawler:
        return Crawler(
            crawl_name="test",
            config_yaml_filepath="path/to/fake_config.yaml",
        )

    return crawler_factory


@pytest.fixture
def _mock_inside_container():
    def mock_exists(path):
        if path == "/.dockerenv":
            return True
        return original_exists(path)

    original_exists = os.path.exists
    with patch("os.path.exists", side_effect=mock_exists):
        yield


@pytest.fixture
def mocked_parser() -> CrawlMetadataParser:
    return CrawlMetadataParser("tests/fixtures/homepage.wacz")


@pytest.fixture
def mocked_wacz_client() -> WACZClient:
    with WACZClient("tests/fixtures/homepage.wacz") as wacz_client:
        yield wacz_client


@pytest.fixture
def _mock_wacz_file_exists(create_mocked_crawler):
    """Mock True for os.path.exists of the WACZ file from a successful crawl."""
    crawler = create_mocked_crawler()
    original_exists = os.path.exists

    def wacz_file_exists(path):
        if path == crawler.wacz_filepath:
            return True
        return original_exists(path)

    with patch("os.path.exists", side_effect=wacz_file_exists):
        yield


@pytest.fixture
def _mock_missing_all_wacz_archive_files():
    def always_raise_wacz_file_not_exists(_filepath):
        raise WaczFileDoesNotExist

    with patch(
        "harvester.wacz.WACZClient._get_archive_file_obj",
        side_effect=always_raise_wacz_file_not_exists,
    ):
        yield
