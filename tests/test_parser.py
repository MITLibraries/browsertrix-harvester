"""tests.test_parser"""
# ruff: noqa: SLF001, PD901

from zipfile import ZipFile

import pandas as pd
import pytest

from browsertrix_harvester.exceptions import WaczFileDoesNotExist
from browsertrix_harvester.parse import CrawlParser


def test_parser_as_context_manager():
    with CrawlParser("tests/fixtures/homepage.wacz") as parser:
        _ = parser.archive
    assert parser._archive is None


def test_parser_wacz_filepath(mocked_parser):
    assert mocked_parser.wacz_filepath == "tests/fixtures/homepage.wacz"


def test_parser_loads_wacz_archive(mocked_parser):
    isinstance(mocked_parser.archive, ZipFile)


def test_parser_loads_wacz_archive_missing_files(mocked_parser):
    parser = CrawlParser("tests/fixtures/missing_files.wacz")
    with pytest.raises(WaczFileDoesNotExist):
        _ = parser.archive


def test_parser_build_websites_dataframe_success(mocked_parser):
    df = mocked_parser.websites_df
    assert isinstance(df, pd.DataFrame)
