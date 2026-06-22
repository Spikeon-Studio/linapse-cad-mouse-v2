import os
import sys
import pytest

def pytest_configure(config):
    # Keep the browser bridge off during the whole pytest session (including subprocess stress tests).
    os.environ["LINAPSE_SKIP_BROWSER_BRIDGE"] = "1"

def pytest_runtest_setup(item):
    if sys.platform in ("win32", "darwin"):
        filename = item.fspath.basename
        cross_platform_files = {
            "test_cross_platform.py",
            "test_installer_config.py",
            "test_browser_extension.py",
            "test_browser_bridge.py",
            "test_playwright_benchy.py",
            "test_multi_click.py",
            "test_serial_buttons.py"
        }
        if filename not in cross_platform_files:
            pytest.skip(f"Linux-only test: skipped on {sys.platform}")
