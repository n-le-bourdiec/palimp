"""Slow tests run in CI (the CI variable is set by GitHub Actions) or with --runslow."""

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--runslow", action="store_true", help="also run tests marked slow")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--runslow") or os.environ.get("CI"):
        return
    skip = pytest.mark.skip(reason="slow: runs in CI or with --runslow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
