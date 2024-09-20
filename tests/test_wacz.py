"""tests.test_wacz"""

# ruff: noqa: SLF001, PD901

import logging
from zipfile import ZipFile

import pandas as pd
import pytest

from harvester.exceptions import ContextManagerRequiredError, WaczFileDoesNotExist
from harvester.wacz import WACZClient


def test_wacz_client_wacz_filepath(mocked_wacz_client):
    assert mocked_wacz_client.wacz_filepath == "tests/fixtures/homepage.wacz"


def test_wacz_client_no_context_manager_raises_error():
    wacz_client = WACZClient("tests/fixtures/homepage.wacz")
    with pytest.raises(ContextManagerRequiredError):
        assert isinstance(wacz_client.wacz_archive, ZipFile)


def test_wacz_client_archive_property_caches_success():
    with WACZClient("tests/fixtures/homepage.wacz") as wacz_client:
        assert not wacz_client._wacz_archive
        _ = wacz_client.wacz_archive
        assert wacz_client._wacz_archive
        assert isinstance(wacz_client.wacz_archive, ZipFile)


def test_wacz_client_build_websites_dataframe_success(mocked_wacz_client):
    df = mocked_wacz_client.html_websites_df
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 13


@pytest.mark.usefixtures("_mock_missing_all_wacz_archive_files")
def test_wacz_client_build_websites_dataframe_fails(mocked_wacz_client, caplog):
    caplog.set_level(logging.DEBUG)
    with pytest.raises(WaczFileDoesNotExist):
        _df = mocked_wacz_client.html_websites_df
    assert "pages file was not found in WACZ file: pages/pages.jsonl." in caplog.text
    assert "pages file was not found in WACZ file: pages/extraPages.jsonl." in caplog.text


def test_wacz_client_lazy_loads_html_websites_df(mocked_wacz_client):
    assert mocked_wacz_client._html_websites_df is None
    _ = mocked_wacz_client.html_websites_df
    assert mocked_wacz_client._html_websites_df is not None
    assert isinstance(mocked_wacz_client.html_websites_df, pd.DataFrame)


def test_wacz_client_raise_exception_on_missing_wacz_file(mocked_wacz_client):
    with pytest.raises(WaczFileDoesNotExist):
        mocked_wacz_client._get_archive_file_object("does_not_exist")


def test_wacz_client_parse_cdx_lines(mocked_wacz_client, caplog):
    good_line = b"""edu,mit,libraries)/ 20230925175224 {"url":
    "https://libraries.mit.edu/", "mime": "text/html", "status": "200", "digest":
    "sha1:NCYTSW3H3FZCD2IXCKPCEKWDBSDYBRHR", "length": "43952", "offset": "3485",
    "filename": "rec-20230925175225009669-4ae3daf80a34.warc.gz", "recordDigest":
    "sha256:f41041ff559fbcb32622044cd2048514beb54dee0a4bde287c9c7f5dcd130887"}"""
    parsed_data = mocked_wacz_client._parse_cdx_line(good_line)
    assert isinstance(parsed_data, dict)
    assert parsed_data["url"] == "https://libraries.mit.edu/"

    bad_lines = [
        b"""{"url": "https://libraries.mit.edu/"}""",
        b"""edu,mit,libraries)/ 20230925175224""",
    ]
    for bad_line in bad_lines:
        parsed_data = mocked_wacz_client._parse_cdx_line(bad_line)
        assert "Error parsing CDX line" in caplog.text
        assert parsed_data is None

    str_line = """edu,mit,libraries)/ 20230925175224 {"url":
    "https://libraries.mit.edu/", "mime": "text/html", "status": "200", "digest":
    "sha1:NCYTSW3H3FZCD2IXCKPCEKWDBSDYBRHR", "length": "43952", "offset": "3485",
    "filename": "rec-20230925175225009669-4ae3daf80a34.warc.gz", "recordDigest":
    "sha256:f41041ff559fbcb32622044cd2048514beb54dee0a4bde287c9c7f5dcd130887"}"""
    with pytest.raises(AttributeError):
        _ = mocked_wacz_client._parse_cdx_line(str_line)


def test_wacz_client_get_content_by_url(mocked_wacz_client):
    url = "https://libraries.mit.edu/"
    content = mocked_wacz_client.get_website_content_by_url(url)
    assert len(content) == 126407
    assert "<!DOCTYPE html>" in content

    with pytest.raises(FileNotFoundError):
        _ = mocked_wacz_client.get_website_content_by_url("http://not.present.in.crawl")
