"""tests.test_parser"""
# ruff: noqa: S108

from unittest.mock import call, mock_open, patch

import pytest
import smart_open

from harvester.cli import main


def test_cli_no_command_options(caplog, runner):
    result = runner.invoke(main)
    assert result.exit_code == 0

    result = runner.invoke(main, ["--verbose"])
    assert result.exit_code == 2
    assert "Error: Missing command." in result.output


def test_cli_docker_shell(caplog, runner):
    with patch("os.system") as mock_system:
        result = runner.invoke(main, ["--verbose", "shell"])
        mock_system.assert_called_with("bash")
        assert result.exit_code == 0


def test_cli_harvest_missing_options_raises_error(caplog, runner):
    result = runner.invoke(
        main,
        [
            "--verbose",
            "harvest",
            "--crawl-name",
            "homepage",
            "--metadata-output-file",
            "/tmp/test.xml",
        ],
    )
    assert "Error: Missing option '--config-yaml-file'" in result.output

    _result = runner.invoke(
        main,
        [
            "--verbose",
            "harvest",
            "--config-yaml-file",
            "/tmp/config.yaml",
        ],
    )
    assert (
        "One or both of arguments --wacz-output-file and --metadata-output-file"
        in caplog.text
    )


@pytest.mark.usefixtures("_mock_inside_container")
def test_cli_harvest_required_options_bad_yaml_raises_error(caplog, runner):
    runner.invoke(
        main,
        [
            "--verbose",
            "harvest",
            "--crawl-name",
            "homepage",
            "--config-yaml-file",
            "/files/does/not/exist.yaml",
            "--metadata-output-file",
            "/tmp/test.xml",
        ],
    )
    assert "Preparing for harvest name: 'homepage'" in caplog.text
    assert (
        "Could not open file locally or from S3: /files/does/not/exist.yaml"
        in caplog.text
    )


@pytest.mark.usefixtures("_mock_inside_container")
def test_cli_harvest_required_options_good_yaml(caplog, runner):
    with patch("harvester.crawl.Crawler.crawl"), patch.object(
        smart_open, "open", mock_open()
    ):
        runner.invoke(
            main,
            [
                "--verbose",
                "harvest",
                "--crawl-name",
                "homepage",
                "--config-yaml-file",
                "tests/fixtures/lib-website-homepage.yaml",
                "--wacz-output-file",
                "/tmp/homepage.wacz",
            ],
        )

        assert (
            "Crawl complete, WACZ archive located at: "
            "/crawls/collections/homepage/homepage.wacz" in caplog.text
        )


@pytest.mark.usefixtures("_mock_inside_container")
def test_cli_harvest_write_wacz(caplog, runner):
    with patch("harvester.crawl.Crawler.crawl"), patch.object(
        smart_open, "open", mock_open()
    ):
        runner.invoke(
            main,
            [
                "--verbose",
                "harvest",
                "--crawl-name",
                "homepage",
                "--config-yaml-file",
                "tests/fixtures/lib-website-homepage.yaml",
                "--wacz-output-file",
                "/tmp/homepage.wacz",
            ],
        )
        assert "Writing WACZ archive to: /tmp/homepage.wacz" in caplog.text
        assert call("/tmp/homepage.wacz", "wb")
        assert call("/crawls/collections/homepage/homepage.wacz", "rb")


@pytest.mark.usefixtures("_mock_inside_container")
def test_cli_harvest_write_metadata(caplog, runner):
    with patch(
        "harvester.crawl.Crawler.crawl",
    ), patch(
        "harvester.parse.CrawlParser.generate_metadata",
    ) as mock_generate_metadata:
        runner.invoke(
            main,
            [
                "--verbose",
                "harvest",
                "--crawl-name",
                "homepage",
                "--config-yaml-file",
                "tests/fixtures/lib-website-homepage.yaml",
                "--metadata-output-file",
                "/tmp/homepage-metadata.xml",
            ],
        )
        assert "Parsing WACZ archive file" in caplog.text
        assert mock_generate_metadata.called
        assert "Metadata records successfully written" in caplog.text
