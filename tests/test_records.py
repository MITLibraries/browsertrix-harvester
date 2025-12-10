"""tests.test_records"""

# ruff: noqa: SLF001

from unittest.mock import mock_open, patch

import pandas as pd
import pytest

from harvester.records import CrawlRecords, smart_open


def test_records_parser_wacz_filepath(mocked_parser):
    assert mocked_parser.wacz_filepath == "tests/fixtures/homepage.wacz"


def test_records_parser_generate_records(mocked_parser):
    assert mocked_parser._websites_records is None
    crawl_records = mocked_parser.generate_records()
    assert isinstance(crawl_records, CrawlRecords)
    assert isinstance(crawl_records.records_df, pd.DataFrame)
    assert mocked_parser._websites_records
    _ = mocked_parser.generate_records()


def test_records_parser_serialize_records(mocked_parser):
    crawl_records = mocked_parser.generate_records()

    # test XML write
    with patch.object(smart_open, "open", mock_open()) as m:
        crawl_records.write("test.xml")
        m.assert_called_with("test.xml", "wb")

    # test TSV write
    with patch.object(smart_open, "open", mock_open()) as m, patch.object(
        pd.DataFrame, "to_csv", return_value=None
    ):
        crawl_records.write("test.tsv")
        m.assert_called_with("test.tsv", "wb")

    # test CSV write
    with patch.object(smart_open, "open", mock_open()) as m, patch.object(
        pd.DataFrame, "to_csv", return_value=None
    ):
        crawl_records.write("test.csv")
        m.assert_called_with("test.csv", "wb")

    with pytest.raises(NotImplementedError):
        crawl_records.write("test.badformat")


def test_records_parser_remove_duplicate_urls(mocked_parser):
    df = pd.DataFrame(
        {
            "url": ["https://example.com", "https://example.com", "https://other.com"],
            "cdx_offset": [100, 200, 150],
        }
    )
    result = mocked_parser._remove_duplicate_urls(df)
    assert len(result) == 2
    assert (
        result[result["url"] == "https://example.com"]["cdx_offset"].to_numpy()[0] == 200
    )


def test_records_parser_generate_records_for_deleted_urls(mocked_parser, tmp_path):
    current_urls_file = tmp_path / "current_urls.txt"
    previous_urls_file = tmp_path / "previous_urls.txt"

    current_urls_file.write_text("https://example.com/page1\nhttps://example.com/page2\n")
    previous_urls_file.write_text(
        "https://example.com/page1\nhttps://example.com/page2\n"
        "https://example.com/deleted\n"
    )

    deleted_records = mocked_parser._generate_delete_records(
        str(current_urls_file), str(previous_urls_file)
    )

    assert len(deleted_records) == 1
    assert deleted_records[0] == {
        "url": "https://example.com/deleted",
        "status": "deleted",
    }


def test_records_parser_generate_records_for_deleted_urls_file_not_found(
    mocked_parser, tmp_path, caplog
):
    current_urls_file = tmp_path / "current_urls.txt"
    current_urls_file.write_text("https://example.com/page1\n")

    deleted_records = mocked_parser._generate_delete_records(
        str(current_urls_file), "nonexistent_file.txt"
    )

    assert len(deleted_records) == 0
    assert "Unable to retrieve previous list of URLs" in caplog.text


def test_records_parser_generate_records_invokes_deleted_urls(
    mocked_parser, mocked_wacz_client, tmp_path
):
    current_urls_file = tmp_path / "current_urls.txt"
    previous_urls_file = tmp_path / "previous_urls.txt"

    current_urls_file.write_text("https://libraries.mit.edu/\n")
    previous_urls_file.write_text(
        "https://libraries.mit.edu/\nhttps://example.com/deleted\n"
    )

    with patch("harvester.records.WACZClient", return_value=mocked_wacz_client):
        crawl_records = mocked_parser.generate_records(
            urls_file=str(current_urls_file),
            previous_sitemap_urls_file=str(previous_urls_file),
        )

    df = crawl_records.records_df
    deleted_rows = df[df["status"] == "deleted"]
    active_rows = df[df["status"] == "active"]

    assert len(deleted_rows) == 1
    assert deleted_rows.iloc[0]["url"] == "https://example.com/deleted"
    assert len(active_rows) >= 1


def test_records_parser_base64_encode_fulltext_success():
    pass


def test_records_parser_base64_encode_fulltext_error():
    pass
