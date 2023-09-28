import os
from unittest.mock import Mock, mock_open, patch

import pytest
from click.testing import CliRunner

from harvester.crawl import Crawler
from harvester.parse import CrawlParser


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
def mocked_parser():
    return CrawlParser("tests/fixtures/homepage.wacz")
