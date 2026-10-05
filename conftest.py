"""Slow tests run in CI (the CI variable is set by GitHub Actions) or with --runslow.

Full tests (Medium seeds 10 to 99, about 3 s each) run only with --runslow.
"""

import os

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--runslow", action="store_true", help="also run tests marked slow")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--runslow"):
        return
    skip_full = pytest.mark.skip(reason="full: runs with --runslow only")
    skip_slow = pytest.mark.skip(reason="slow: runs in CI or with --runslow")
    for item in items:
        if "full" in item.keywords:
            item.add_marker(skip_full)
        elif "slow" in item.keywords and not os.environ.get("CI"):
            item.add_marker(skip_slow)
