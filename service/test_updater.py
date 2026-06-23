import unittest
from unittest.mock import MagicMock, patch
import io
import json
import sys
from linapse import state
from linapse import updater

class TestUpdater(unittest.TestCase):
    def setUp(self):
        state.service_version = "2.19.1"
        state.latest_software_version = None
        state.software_update_status = "idle"
        state.software_update_url = None

    def test_compare_versions(self):
        self.assertEqual(updater.compare_versions("2.19.1", "2.19.1"), 0)
        self.assertEqual(updater.compare_versions("v2.19.1", "2.19.1"), 0)
        self.assertEqual(updater.compare_versions("v2.20.0", "v2.19.1"), 1)
        self.assertEqual(updater.compare_versions("2.19.0", "v2.19.1"), -1)
        self.assertEqual(updater.compare_versions("2.19.2", "2.19.10"), -1)
        self.assertEqual(updater.compare_versions("2.19", "2.19.1"), -1)

    @patch("urllib.request.urlopen")
    @patch("linapse.state.broadcast_from_thread")
    def test_check_for_updates_available(self, mock_broadcast, mock_urlopen):
        # Mock GitHub releases response
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.20.0",
            "assets": [
                {"name": "LinapseServiceSetup.exe", "browser_download_url": "http://example.com/setup.exe"},
                {"name": "linapse-service.pkg", "browser_download_url": "http://example.com/setup.pkg"}
            ],
            "zipball_url": "http://example.com/zipball.zip",
            "html_url": "http://example.com/release"
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Force platform mock if needed, or check it generic
        updater.check_for_updates(quiet=True)
        
        self.assertEqual(state.latest_software_version, "2.20.0")
        self.assertEqual(state.software_update_status, "available")
        self.assertIsNotNone(state.software_update_url)

    @patch("urllib.request.urlopen")
    @patch("linapse.state.broadcast_from_thread")
    def test_check_for_updates_up_to_date(self, mock_broadcast, mock_urlopen):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({
            "tag_name": "v2.19.1",
            "assets": []
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        updater.check_for_updates(quiet=True)
        
        self.assertEqual(state.software_update_status, "idle")
        self.assertIsNone(state.latest_software_version)

    @patch("urllib.request.urlopen")
    @patch("linapse.state.broadcast_from_thread")
    def test_check_for_updates_rate_limit_fallback(self, mock_broadcast, mock_urlopen):
        mock_response_fallback = MagicMock()
        mock_response_fallback.read.return_value = b"2.20.0\n"

        def mock_urlopen_side_effect(req, *args, **kwargs):
            # req can be Request object
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "api.github.com" in url:
                raise Exception("HTTP Error 403: rate limit exceeded")
            elif "raw.githubusercontent.com" in url:
                mock_enter = MagicMock()
                mock_enter.__enter__.return_value = mock_response_fallback
                return mock_enter
            raise ValueError(f"Unexpected url {url}")

        mock_urlopen.side_effect = mock_urlopen_side_effect

        updater.check_for_updates(quiet=True)

        self.assertEqual(state.latest_software_version, "2.20.0")
        self.assertEqual(state.software_update_status, "available")
        self.assertEqual(state.software_update_url, "https://github.com/spikeon/linapse-cad-mouse-v2/releases/tag/v2.20.0")

    @patch("linapse.state.broadcast_from_thread")
    @patch("subprocess.Popen")
    @patch("shutil.which")
    def test_run_downloaded_installer(self, mock_which, mock_popen, mock_broadcast):
        state.downloaded_installer_path = "/tmp/fake/setup.sh"
        mock_which.side_effect = lambda x: x == "gnome-terminal"
        
        updater.run_downloaded_installer()
        
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("gnome-terminal", args)
        self.assertIn("./setup.sh", args[4])
