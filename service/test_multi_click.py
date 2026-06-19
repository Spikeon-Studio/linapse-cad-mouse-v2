#!/usr/bin/env python3
import asyncio
import os
import sys
import json
import time
import pytest
from pathlib import Path
from importlib.machinery import SourceFileLoader
import importlib.util
from unittest.mock import MagicMock

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
    monkeypatch.setattr("sys.platform", "linux")
    # Mock loop and broadcast
    monkeypatch.setattr(linapse_service, "_loop", asyncio.new_event_loop())
    monkeypatch.setattr(linapse_service, "_broadcast_from_thread", MagicMock())

def test_multi_click_detection():
    # Setup action configuration with double click on btn 0, and single/double actions
    actions = {
        "button_override": False,
        "current_mode": "Default",
        "modes": {
            "Default": {
                "buttons": {
                    "0:1": {"action": "key", "value": "ctrl+c"},
                    "0:2": {"action": "key", "value": "ctrl+v"},
                    "1:1": {"action": "key", "value": "shift+a"}
                },
                "taps": {}
            }
        }
    }
    
    linapse_service._actions_ref = [actions]
    
    # 1. Test single click with double click configured (delayed trigger)
    linapse_service._on_press(0, actions)
    time.sleep(0.05)
    assert len(ydotool_calls) == 0 # Delayed
    
    linapse_service._on_release(0, actions)
    
    # Poll up to 5s for the single-click action to fire
    start_time = time.time()
    while len(ydotool_calls) < 1 and time.time() - start_time < 5.0:
        time.sleep(0.05)
        
    # Should trigger single click action
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"]
    
    # 2. Test double click
    ydotool_calls.clear()
    linapse_service._on_press(0, actions)
    time.sleep(0.05)
    linapse_service._on_release(0, actions)
    
    # Immediately press again for second click
    linapse_service._on_press(0, actions)
    time.sleep(0.05)
    linapse_service._on_release(0, actions)
    
    # Poll up to 5s for the double-click action to fire
    start_time = time.time()
    while len(ydotool_calls) < 1 and time.time() - start_time < 5.0:
        time.sleep(0.05)
        
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]

def test_legacy_button_fallback():
    # Setup actions with legacy buttons (no :1 / :2 keys)
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
    
    linapse_service._actions_ref = [actions]
    
    # Since no double-click is configured, it should trigger immediately
    linapse_service._on_press(0, actions)
    
    # Poll up to 5s for the action to fire
    start_time = time.time()
    while len(ydotool_calls) < 1 and time.time() - start_time < 5.0:
        time.sleep(0.05)
        
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "29:1", "44:1", "44:0", "29:0"]
    
    linapse_service._on_release(0, actions)
    time.sleep(0.5)
    # Ensure no extra multi-click action is triggered
    assert len(ydotool_calls) == 1

def test_media_action_dispatch():
    # Verify that media actions trigger the correct keycodes
    actions = {
        "button_override": False,
        "current_mode": "Default",
        "modes": {
            "Default": {
                "buttons": {
                    "0": {"action": "media", "command": "play"},
                    "1": {"action": "media", "command": "mute"}
                },
                "taps": {}
            }
        }
    }
    
    linapse_service._actions_ref = [actions]
    
    # Test play command -> playpause (164) or play (207)
    linapse_service._on_press(0, actions)
    
    # Poll up to 5s for the action to fire
    start_time = time.time()
    while len(ydotool_calls) < 1 and time.time() - start_time < 5.0:
        time.sleep(0.05)
        
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "207:1", "207:0"]
    
    linapse_service._on_release(0, actions)
    
    # Test mute command -> mute (113)
    ydotool_calls.clear()
    linapse_service._on_press(1, actions)
    
    # Poll up to 5s for the action to fire
    start_time = time.time()
    while len(ydotool_calls) < 1 and time.time() - start_time < 5.0:
        time.sleep(0.05)
        
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "113:1", "113:0"]
    
    linapse_service._on_release(1, actions)
