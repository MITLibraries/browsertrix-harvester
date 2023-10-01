import pytest
from click.testing import CliRunner


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("SENTRY_DSN", "None")
    monkeypatch.setenv("WORKSPACE", "test")
    monkeypatch.setenv("VIRTUAL_ENV", "/fake/path/to/virtual/env")


@pytest.fixture
def runner():
    return CliRunner()
