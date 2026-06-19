#!/usr/bin/env python3
"""
Challenger Verification Test Suite for Milestone 3 (Specialized Browser/Media Modes)
Specifically tests:
1. 6DoF report suppression on WS and Unix Socket for Browser & Media modes.
2. Accumulator boundary coordinates (inf, nan, large values) & rapid oscillations stability.
3. Button mapping combos (ctrl+pageup/pagedown, prev/next) triggering.
"""

import asyncio
import os
import sys
import struct
import json
import time
import pytest
import math
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the original test suite to reuse its fixtures and modules
import test_signal_integration as tsi
from test_signal_integration import running_service

def test_challenger_6dof_suppression(running_service):
    """
    Verify Browser and Media modes suppress 6DoF reports correctly on both
    WebSocket and Unix socket.
    """
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    socket_path = running_service["socket_path"]
    
    import websockets
    linapse_service = tsi.linapse_service
    
    # 1. Test Browser Mode Suppression
    linapse_service.switch_mode("Browser")
    assert linapse_service._actions_ref[0]["current_mode"] == "Browser"
    
    async def run_browser_suppression_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                # Clear ws queue if any
                # Send motion telemetry in Browser mode (should be suppressed)
                mock_serial.input_queue.put(b">MOTION:1.0,2.0,3.0,4.0,5.0,6.0\n")
                
                # Send TAP event to act as a marker
                mock_serial.input_queue.put(b"TAP:NegZ:1\n")
                
                # WS should receive TAP, but NOT the preceding MOTION
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert "TAP" in first_msg
                assert "MOTION" not in first_msg
                
                # Unix socket should receive nothing (Timeout)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readexactly(32), timeout=0.1)
            finally:
                writer.close()
                await writer.wait_closed()
                
    loop.run_until_complete(run_browser_suppression_test())

    # 2. Test Media Mode Suppression
    linapse_service.switch_mode("Media")
    assert linapse_service._actions_ref[0]["current_mode"] == "Media"
    
    async def run_media_suppression_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                # Send motion telemetry in Media mode (should be suppressed)
                mock_serial.input_queue.put(b">MOTION:10.0,-20.0,30.0,-40.0,50.0,-60.0\n")
                
                # Send TAP event to act as a marker
                mock_serial.input_queue.put(b"TAP:NegZ:1\n")
                
                # WS should receive TAP, but NOT the preceding MOTION
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert "TAP" in first_msg
                assert "MOTION" not in first_msg
                
                # Unix socket should receive nothing (Timeout)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readexactly(32), timeout=0.1)
            finally:
                writer.close()
                await writer.wait_closed()
                
    loop.run_until_complete(run_media_suppression_test())

    # 3. Test Default Mode (should NOT be suppressed)
    linapse_service.switch_mode("Default")
    assert linapse_service._actions_ref[0]["current_mode"] == "Default"
    
    async def run_default_motion_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                mock_serial.input_queue.put(b">MOTION:1.0,2.0,3.0,4.0,5.0,6.0\n")
                
                # WS should receive MOTION
                ws_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert ws_msg == "MOTION:1.0,2.0,3.0,4.0,5.0,6.0"
                
                # Unix socket should receive 32 bytes
                socket_data = await asyncio.wait_for(reader.readexactly(32), timeout=1.0)
                assert len(socket_data) == 32
            finally:
                writer.close()
                await writer.wait_closed()
                
    loop.run_until_complete(run_default_motion_test())


def test_challenger_accumulator_boundary_stress(running_service):
    """
    Stress test accumulator scroll/volume/scrub logic.
    Ensure accumulator is not poisoned by NaN or Inf and decays/resumes normally.
    Test large values and rapid oscillations.
    """
    mock_serial = running_service["mock_serial"]
    linapse_service = tsi.linapse_service
    
    # Switch to Browser mode (uses rx scroll accumulator)
    linapse_service.switch_mode("Browser")
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    
    # 1. Poisoning test with NaN
    # Normal input first to increase accumulator
    mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
    time.sleep(0.02)
    assert abs(linapse_service._rx_scroll_accumulator - 100.0) < 0.01
    
    # Send NaN (should be converted to 0, causing decay: 100 * 0.8 = 80.0)
    mock_serial.input_queue.put(b">MOTION:0,0,0,nan,0,0\n")
    time.sleep(0.02)
    assert abs(linapse_service._rx_scroll_accumulator - 80.0) < 0.01
    assert not math.isnan(linapse_service._rx_scroll_accumulator)
    
    # Send normal value after NaN to verify recovery
    mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
    time.sleep(0.02)
    # 80.0 + 100.0 = 180.0
    # 180.0 // 150.0 = 1 scroll down (triggers ydotool)
    # Remaining accumulator: 180.0 - 150.0 = 30.0
    assert abs(linapse_service._rx_scroll_accumulator - 30.0) < 0.01
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "1"] for call in tsi.ydotool_calls)
    
    # 2. Poisoning test with Inf
    linapse_service._rx_scroll_accumulator = 100.0
    tsi.ydotool_calls.clear()
    # Send inf (should be converted to 0, causing decay: 100 * 0.8 = 80.0)
    mock_serial.input_queue.put(b">MOTION:0,0,0,inf,0,0\n")
    time.sleep(0.02)
    assert abs(linapse_service._rx_scroll_accumulator - 80.0) < 0.01
    assert not math.isinf(linapse_service._rx_scroll_accumulator)
    
    # Send normal value after Inf
    mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
    time.sleep(0.02)
    assert abs(linapse_service._rx_scroll_accumulator - 30.0) < 0.01
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "1"] for call in tsi.ydotool_calls)

    # 3. Large coordinate stability (e.g. overflow protection)
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,1.5e6,0,0\n")
    time.sleep(0.02)
    # scrolls = 1.5e6 // 150.0 = 10000 scrolls
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "10000"] for call in tsi.ydotool_calls)
    assert linapse_service._rx_scroll_accumulator == 0.0

    # 4. Rapid oscillations stability
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    for _ in range(50):
        mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
        mock_serial.input_queue.put(b">MOTION:0,0,0,-100.0,0,0\n")
    time.sleep(0.1)
    # The accumulator should end up near 0 and no scroll commands should be dispatched (since absolute accumulates never cross threshold)
    assert abs(linapse_service._rx_scroll_accumulator) < 0.01
    assert not any(call[1] == "mousemove" and "-w" in call for call in tsi.ydotool_calls)

    # 5. Media mode accumulators testing (rz scrub and rx volume)
    linapse_service.switch_mode("Media")
    linapse_service._rz_scrub_accumulator = 0.0
    linapse_service._rx_volume_accumulator = 0.0
    tsi.ydotool_calls.clear()
    
    # RZ scrub: nan & inf tests
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,nan\n")
    time.sleep(0.02)
    assert linapse_service._rz_scrub_accumulator == 0.0
    
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,inf\n")
    time.sleep(0.02)
    assert linapse_service._rz_scrub_accumulator == 0.0

    # RX volume: nan & inf tests
    mock_serial.input_queue.put(b">MOTION:0,0,0,nan,0,0\n")
    time.sleep(0.02)
    assert linapse_service._rx_volume_accumulator == 0.0
    
    mock_serial.input_queue.put(b">MOTION:0,0,0,inf,0,0\n")
    time.sleep(0.02)
    assert linapse_service._rx_volume_accumulator == 0.0


def test_challenger_button_mapping(running_service):
    """
    Verify Browser and Media button mapping configurations translate to correctly-timed
    ydotool key commands (ctrl+pageup/pagedown, prev/next).
    """
    loop = running_service["loop"]
    linapse_service = tsi.linapse_service
    
    # 1. Browser Mode Button Mapping
    linapse_service.switch_mode("Browser")
    assert linapse_service._actions_ref[0]["current_mode"] == "Browser"
    
    tsi.ydotool_calls.clear()
    
    # Press button 0 (should map to ctrl+pageup)
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(0)
    time.sleep(0.02)
    
    # ctrl = 29, pageup = 104
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "29:1", "104:1", "104:0", "29:0"] for call in tsi.ydotool_calls)
    
    tsi.ydotool_calls.clear()
    
    # Press button 1 (should map to ctrl+pagedown)
    linapse_service._on_press(1, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(1)
    time.sleep(0.02)
    
    # ctrl = 29, pagedown = 109
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "29:1", "109:1", "109:0", "29:0"] for call in tsi.ydotool_calls)

    # 2. Media Mode Button Mapping
    linapse_service.switch_mode("Media")
    assert linapse_service._actions_ref[0]["current_mode"] == "Media"
    
    tsi.ydotool_calls.clear()
    
    # Press button 0 (should map to prev)
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(0)
    time.sleep(0.02)
    
    # prev = 165
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "165:1", "165:0"] for call in tsi.ydotool_calls)
    
    tsi.ydotool_calls.clear()
    
    # Press button 1 (should map to next)
    linapse_service._on_press(1, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(1)
    time.sleep(0.02)
    
    # next = 163
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "163:1", "163:0"] for call in tsi.ydotool_calls)
