"""tests.test_parser"""
# ruff: noqa: SLF001, PD901

from unittest.mock import mock_open, patch
from zipfile import ZipFile

import pandas as pd
import pytest

from browsertrix_harvester.exceptions import WaczFileDoesNotExist
from browsertrix_harvester.parse import CrawlMetadataRecords, CrawlParser, smart_open


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
    assert len(df) == 13


def test_parser_lazy_loads(mocked_parser):
    assert mocked_parser._kw_extractor is None
    _ = mocked_parser.kw_extractor
    assert mocked_parser._kw_extractor is not None
    assert mocked_parser._websites_df is None
    _ = mocked_parser.websites_df
    assert mocked_parser._websites_df is not None
    assert isinstance(mocked_parser.websites_df, pd.DataFrame)


def test_parser_raise_exception_on_missing_wacz_file(mocked_parser):
    with pytest.raises(WaczFileDoesNotExist):
        mocked_parser._get_archive_file_obj("does_not_exist")


def test_parser_parse_cdx_lines(mocked_parser, caplog):
    good_line = b"""edu,mit,libraries)/ 20230925175224 {"url":
    "https://libraries.mit.edu/", "mime": "text/html", "status": "200", "digest":
    "sha1:NCYTSW3H3FZCD2IXCKPCEKWDBSDYBRHR", "length": "43952", "offset": "3485",
    "filename": "rec-20230925175225009669-4ae3daf80a34.warc.gz", "recordDigest":
    "sha256:f41041ff559fbcb32622044cd2048514beb54dee0a4bde287c9c7f5dcd130887"}"""
    parsed_data = mocked_parser._parse_cdx_line(good_line)
    assert isinstance(parsed_data, dict)
    assert parsed_data["url"] == "https://libraries.mit.edu/"

    bad_lines = [
        b"""{"url": "https://libraries.mit.edu/"}""",
        b"""edu,mit,libraries)/ 20230925175224""",
    ]
    for bad_line in bad_lines:
        parsed_data = mocked_parser._parse_cdx_line(bad_line)
        assert "error parsing CDX line" in caplog.text
        assert parsed_data is None

    str_line = """edu,mit,libraries)/ 20230925175224 {"url":
    "https://libraries.mit.edu/", "mime": "text/html", "status": "200", "digest":
    "sha1:NCYTSW3H3FZCD2IXCKPCEKWDBSDYBRHR", "length": "43952", "offset": "3485",
    "filename": "rec-20230925175225009669-4ae3daf80a34.warc.gz", "recordDigest":
    "sha256:f41041ff559fbcb32622044cd2048514beb54dee0a4bde287c9c7f5dcd130887"}"""
    with pytest.raises(AttributeError):
        _ = mocked_parser._parse_cdx_line(str_line)


def test_parser_generate_metadata(mocked_parser):
    assert mocked_parser._websites_metadata is None
    crawl_metadata_records = mocked_parser.generate_metadata()
    assert isinstance(crawl_metadata_records, CrawlMetadataRecords)
    assert isinstance(crawl_metadata_records.df, pd.DataFrame)
    assert mocked_parser._websites_metadata is not None
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


def test_parser_get_content_by_url(mocked_parser):
    url = "https://libraries.mit.edu/"
    content = mocked_parser.get_website_content_by_url(url)
    assert len(content) == 126407
    assert "<!DOCTYPE html>" in content

    with pytest.raises(FileNotFoundError):
        _ = mocked_parser.get_website_content_by_url("http://not.present.in.crawl")


def test_parser_handles_missing_fulltext(mocked_parser):
    url = "https://libraries.mit.edu/"

    # generate websites dataframe and remove text from a row
    websites_df = mocked_parser.websites_df
    # ruff: noqa: PD002
    websites_df.set_index("url", inplace=True)
    websites_df.loc[url, "text"] = None
    # ruff: noqa: PD002
    websites_df.reset_index(inplace=True)
    mocked_parser._websites_df = websites_df

    # generate metadata and assert all fulltext derived fields are None
    crawl_metadata_records = mocked_parser.generate_metadata()
    row = crawl_metadata_records.df.set_index("url").loc[url]
    assert row.fulltext is None
    assert row.fulltext_keywords is None
