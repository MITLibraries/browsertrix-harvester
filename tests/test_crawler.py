from unittest.mock import mock_open, patch

from browsertrix_harvester.crawl import Crawler


def test_copy_config_yaml():
    fake_input_file = "path/to/fake_config.yaml"

    # mock smart_open.open for both reading and writing
    mock_content = "fake file content"
    mock_smart_open = mock_open(read_data=mock_content)

    with patch("smart_open.open", mock_smart_open):
        Crawler(
            crawl_name="test",
            config_yaml_filepath=fake_input_file,
        )

    # assert input file was opened for read and output file was opened for write
    mock_smart_open.assert_any_call(fake_input_file, "rb")
    mock_smart_open.assert_any_call("/btrixharvest/crawl-config.yaml", "wb")

    # assert written data is from read file
    handle = mock_smart_open()
    handle.write.assert_called_once_with(mock_content)
