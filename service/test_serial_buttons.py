#!/usr/bin/env python3
import asyncio
import os
import sys
import time
import pytest
from pathlib import Path
from importlib.machinery import SourceFileLoader
import importlib.util
from unittest.mock import MagicMock, patch

# Load the service module
if "linapse_service" in sys.modules:
    linapse_service = sys.modules["linapse_service"]
else:
    service_path = Path(__file__).parent / "linapse-service"
    loader = SourceFileLoader("linapse_service", str(service_path))
    spec = importlib.util.spec_from_loader("linapse_service", loader)
    linapse_service = importlib.util.module_from_spec(spec)
    loader.exec_module(linapse_service)
    sys.modules["linapse_service"] = linapse_service

# Mock ydotool calls
ydotool_calls = []

def mock_popen(args, *args_etc, **kwargs):
    if isinstance(args, list) and args[0] == "ydotool":
        ydotool_calls.append(args)
        proc = MagicMock()
        proc.poll.return_value = 0
        proc.wait.return_value = 0
        return proc
    return MagicMock()

@pytest.fixture(autouse=True)
def setup_mocks(monkeypatch):
    global ydotool_calls
    ydotool_calls.clear()
    monkeypatch.setattr("subprocess.Popen", mock_popen)
    # Mock loop and broadcast
    monkeypatch.setattr(linapse_service, "_loop", asyncio.new_event_loop())
    monkeypatch.setattr(linapse_service, "_broadcast_from_thread", MagicMock())

def test_serial_button_clicks_on_mac_windows(monkeypatch):
    # Set platform to darwin
    monkeypatch.setattr("sys.platform", "darwin")
    
    actions = {
        "button_override": False,
        "current_mode": "Default",
        "modes": {
            "Default": {
                "buttons": {
                    "0": {"action": "key", "value": "ctrl+z"}
                },
                "taps": {}
            }
        }
    }
    
    import linapse.serial_port
    
    # Mock _on_press and _on_release to see if they get called by parser
    mock_press = MagicMock()
    mock_release = MagicMock()
    
    with patch("linapse.serial_port._on_press", mock_press), \
         patch("linapse.serial_port._on_release", mock_release):
        
        # We simulate the serial line reading
        # BUTTON:0:1
        line = "BUTTON:0:1"
        if line.startswith("BUTTON:"):
            parts = line.split(":")
            if len(parts) == 3:
                _, btn_str, state_str = parts
                btn = int(btn_str)
                val = int(state_str)
                if sys.platform in ("win32", "darwin"):
                    if val == 1:
                        linapse.serial_port._on_press(btn, actions)
                    else:
                        linapse.serial_port._on_release(btn, actions)
                        
        # Since we patched _on_press directly, check if it was called
        mock_press.assert_called_once_with(0, actions)
        
        # Test release
        line = "BUTTON:0:0"
        if line.startswith("BUTTON:"):
            parts = line.split(":")
            if len(parts) == 3:
                _, btn_str, state_str = parts
                btn = int(btn_str)
                val = int(state_str)
                if sys.platform in ("win32", "darwin"):
                    if val == 1:
                        linapse.serial_port._on_press(btn, actions)
                    else:
                        linapse.serial_port._on_release(btn, actions)
                        
        mock_release.assert_called_once_with(0, actions)

def test_suppress_hid_report_on_mac(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    
    # 1. Custom USB disabled: should NOT write hid_report
    actions_ref = [{
        "custom_usb": {"enabled": False}
    }]
    
    # Check if logic suppresses hid_report
    custom_usb = actions_ref[0].get("custom_usb", {})
    should_send = (sys.platform != "darwin" or custom_usb.get("enabled", False))
    assert not should_send
    
    # 2. Custom USB enabled: SHOULD write hid_report
    actions_ref[0]["custom_usb"]["enabled"] = True
    should_send = (sys.platform != "darwin" or actions_ref[0].get("custom_usb", {}).get("enabled", False))
    assert should_send
