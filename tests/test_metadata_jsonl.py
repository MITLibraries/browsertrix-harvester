"""tests.test_metadata_jsonl"""

# ruff: noqa: PERF401

from unittest.mock import mock_open, patch

import jsonlines
import pandas as pd

from harvester.metadata import CrawlMetadataRecords, smart_open


def test_metadata_records_to_jsonl_bytes():
    df = pd.DataFrame(
        [
            {"a": 1, "b": None},
            {"a": 2, "b": "x"},
        ]
    )
    records = CrawlMetadataRecords(df)
    data = records.to_jsonl()
    assert isinstance(data, (bytes, bytearray))
    text = data.decode("utf-8")
    lines = text.strip().split("\n")

    # parse back with jsonlines to ensure valid JSON
    parsed = []
    for line in lines:
        parsed.append(jsonlines.Reader(iter([line])).read())
    assert parsed == [{"a": 1, "b": None}, {"a": 2, "b": "x"}]


def test_metadata_write_jsonl_calls_open(tmp_path):
    df = pd.DataFrame([{"a": 1}])
    records = CrawlMetadataRecords(df)
    with patch.object(smart_open, "open", mock_open()) as m:
        records.write("out.jsonl")
        m.assert_called_with("out.jsonl", "wb")
