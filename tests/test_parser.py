"""tests.test_parser"""
# ruff: noqa: SLF001, PD002, PD901

from unittest.mock import mock_open, patch

import pandas as pd
import pytest

from harvester.metadata import CrawlMetadataRecords, smart_open


def test_parser_wacz_filepath(mocked_parser):
    assert mocked_parser.wacz_filepath == "tests/fixtures/homepage.wacz"


def test_parser_generate_metadata(mocked_parser):
    assert mocked_parser._websites_metadata is None
    crawl_metadata_records = mocked_parser.generate_metadata()
    assert isinstance(crawl_metadata_records, CrawlMetadataRecords)
    assert isinstance(crawl_metadata_records.df, pd.DataFrame)
    assert mocked_parser._websites_metadata
    _ = mocked_parser.generate_metadata()


def test_parser_serialize_metadata(mocked_parser):
    crawl_metadata_records = mocked_parser.generate_metadata()

    # test XML write
    with patch.object(smart_open, "open", mock_open()) as m:
        crawl_metadata_records.write("test.xml")
        m.assert_called_with("test.xml", "wb")

    # test TSV write
    with patch.object(smart_open, "open", mock_open()) as m, patch.object(
        pd.DataFrame, "to_csv", return_value=None
    ):
        crawl_metadata_records.write("test.tsv")
        m.assert_called_with("test.tsv", "wb")

    # test CSV write
    with patch.object(smart_open, "open", mock_open()) as m, patch.object(
        pd.DataFrame, "to_csv", return_value=None
    ):
        crawl_metadata_records.write("test.csv")
        m.assert_called_with("test.csv", "wb")

    with pytest.raises(NotImplementedError):
        crawl_metadata_records.write("test.badformat")


def test_wacz_client_lazy_loads_keyword_extractor(mocked_parser):
    assert not mocked_parser._keyword_extractor
    _ = mocked_parser.keyword_extractor
    assert mocked_parser._keyword_extractor


def test_parser_handles_missing_fulltext_success(mocked_parser, mocked_wacz_client):
    url = "https://libraries.mit.edu/"

    # generate websites dataframe and remove text for a URL
    missing_fulltext_html_websites_df = mocked_wacz_client.html_websites_df
    missing_fulltext_html_websites_df.set_index("url", inplace=True)
    missing_fulltext_html_websites_df.loc[url, "text"] = None
    missing_fulltext_html_websites_df.reset_index(inplace=True)
    mocked_wacz_client._html_websites_df = missing_fulltext_html_websites_df

    # path the WACZClient that would get instantied and used by CrawlMetadataParser
    with patch("harvester.metadata.WACZClient", return_value=mocked_wacz_client):
        crawl_metadata_records = mocked_parser.generate_metadata()

    row = crawl_metadata_records.df.set_index("url").loc[url]
    assert row.fulltext is None
    assert row.fulltext_keywords is None
