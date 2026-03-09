"""Shared pytest fixtures."""

from __future__ import annotations

import os
from typing import cast

import pytest

from ops_summary.config import load_environment
from ops_summary.test_data import initialize_test_database


@pytest.fixture(scope="session", autouse=True)
def _load_env_files() -> None:
    load_environment(test=True, override=True)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    return cast(str, url)


@pytest.fixture(scope="session")
def initialized_test_database(test_database_url: str) -> str:
    initialize_test_database(test_database_url)
    return test_database_url
