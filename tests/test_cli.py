"""tests.test_parser"""
# ruff: noqa: S108

from unittest.mock import patch

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
