from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Generator
from urllib.request import urlopen

import pytest
from playwright.sync_api import Page, expect


APP_PORT = 8507
APP_URL = f"http://127.0.0.1:{APP_PORT}"


def _wait_for_app(url: str, timeout_seconds: int = 90) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urlopen(url) as response:  # noqa: S310
                if response.status == 200:
                    return
        except Exception:
            time.sleep(1)
    raise TimeoutError(f"Timed out waiting for Streamlit app at {url}")


@pytest.fixture(scope="session")
def streamlit_server(initialized_test_database: str) -> Generator[str, None, None]:
    env = os.environ.copy()
    env["TEST_DATABASE_URL"] = initialized_test_database
    env["AUTO_LOAD_DB_ON_START"] = "1"

    process = subprocess.Popen(
        [
            "poetry",
            "run",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            str(APP_PORT),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_app(APP_URL)
        yield APP_URL
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.mark.e2e
def test_streamlit_app_loads_and_displays_reconciled_lot(
    page: Page, streamlit_server: str
) -> None:
    page.goto(streamlit_server, wait_until="networkidle")

    expect(page.get_by_text("Operational Signal Dashboard").first).to_be_visible(
        timeout=30000
    )
    expect(page.get_by_text("Production Line Rankings").first).to_be_visible(
        timeout=30000
    )
    expect(page.get_by_text("Shipping Risk Alerts").first).to_be_visible(
        timeout=30000
    )
    expect(page.get_by_text("Defect Trend Signals").first).to_be_visible(
        timeout=30000
    )
    expect(page.get_by_text("Line 1").first).to_be_visible(timeout=30000)
    expect(page.get_by_text("20260112001").first).to_be_visible(
        timeout=30000
    )
