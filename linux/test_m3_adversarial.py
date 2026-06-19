#!/usr/bin/env python3
import asyncio
import os
import sys
import struct
import json
import time
import socket
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the original test suite to reuse its fixtures and modules
import test_signal_integration as tsi
from test_signal_integration import running_service

def test_m3_browser_media_suppression(running_service):
    """
    1. Verify 'Browser' and 'Media' modes suppress 6DoF reports correctly.
    WebSocket and UNIX socket must NOT receive motion coordinates.
    """
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    socket_path = running_service["socket_path"]
    
    import websockets
    
    # --- BROWSER MODE ---
    linapse_service = tsi.linapse_service
    linapse_service.switch_mode("Browser")
    assert linapse_service._actions_ref[0]["current_mode"] == "Browser"
    
    async def run_browser_test():
        # Establish WS and UNIX Socket connections
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                # Send motion telemetry
                mock_serial.input_queue.put(b">MOTION:10.0,20.0,30.0,40.0,50.0,60.0\n")
                
                # Send a tap gesture to act as a marker (non-suppressed event)
                mock_serial.input_queue.put(b"TAP:NegZ:1\n")
                
                # Read first WebSocket message
                # It must be TAP, indicating the preceding MOTION was suppressed
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert first_msg == "TAP:top:1"
                
                # UNIX socket should receive nothing (suppressed)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readexactly(32), timeout=0.1)
                    
            finally:
                writer.close()
                await writer.wait_closed()

    loop.run_until_complete(run_browser_test())

    # --- MEDIA MODE ---
    linapse_service.switch_mode("Media")
    assert linapse_service._actions_ref[0]["current_mode"] == "Media"
    
    async def run_media_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                # Send motion telemetry
                mock_serial.input_queue.put(b">MOTION:5.0,-15.0,25.0,35.0,-45.0,55.0\n")
                
                # Send a tap gesture to act as a marker
                mock_serial.input_queue.put(b"TAP:PosX:1\n")
                
                # Read first WebSocket message - must be TAP
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert first_msg == "TAP:right:1"
                
                # UNIX socket should receive nothing (suppressed)
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readexactly(32), timeout=0.1)
                    
            finally:
                writer.close()
                await writer.wait_closed()

    loop.run_until_complete(run_media_test())

    # --- DEFAULT MODE (SHOULD NOT BE SUPPRESSED) ---
    linapse_service.switch_mode("Default")
    assert linapse_service._actions_ref[0]["current_mode"] == "Default"
    
    async def run_default_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            await asyncio.sleep(0.05)
            try:
                # Send motion telemetry
                mock_serial.input_queue.put(b">MOTION:1.0,2.0,3.0,4.0,5.0,6.0\n")
                
                # WS should receive MOTION broadcast
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                assert first_msg == "MOTION:1.0,2.0,3.0,4.0,5.0,6.0"
                
                # UNIX socket should receive 32-byte packet
                packet = await asyncio.wait_for(reader.readexactly(32), timeout=1.0)
                assert len(packet) == 32
                
            finally:
                writer.close()
                await writer.wait_closed()

    loop.run_until_complete(run_default_test())

def test_m3_button_mapping(running_service):
    """
    3. Verify button mapping (ctrl+pageup/pagedown, prev/next) is triggered.
    """
    loop = running_service["loop"]
    linapse_service = tsi.linapse_service
    
    # --- BROWSER MODE ---
    linapse_service.switch_mode("Browser")
    assert linapse_service._actions_ref[0]["current_mode"] == "Browser"
    
    tsi.ydotool_calls.clear()
    
    # Press button 0
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    # Sleep synchronously to let CHORD_WINDOW expire
    time.sleep(0.08)
    linapse_service._on_release(0)
    time.sleep(0.02)
    
    # Should trigger ctrl+pageup combo (keycodes: ctrl=29, pageup=104)
    # ydotool_calls should have a "key" action with ["ydotool", "key", "29:1", "104:1", "104:0", "29:0"]
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "29:1", "104:1", "104:0", "29:0"] for call in tsi.ydotool_calls)
    
    tsi.ydotool_calls.clear()
    
    # Press button 1
    linapse_service._on_press(1, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(1)
    time.sleep(0.02)
    
    # Should trigger ctrl+pagedown combo (keycodes: ctrl=29, pagedown=109)
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "29:1", "109:1", "109:0", "29:0"] for call in tsi.ydotool_calls)

    # --- MEDIA MODE ---
    linapse_service.switch_mode("Media")
    assert linapse_service._actions_ref[0]["current_mode"] == "Media"
    
    tsi.ydotool_calls.clear()
    
    # Press button 0
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(0)
    time.sleep(0.02)
    
    # Should trigger prev combo (keycode: prev=165)
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "165:1", "165:0"] for call in tsi.ydotool_calls)
    
    tsi.ydotool_calls.clear()
    
    # Press button 1
    linapse_service._on_press(1, linapse_service._actions_ref[0])
    time.sleep(0.08)
    linapse_service._on_release(1)
    time.sleep(0.02)
    
    # Should trigger next combo (keycode: next=163)
    assert len(tsi.ydotool_calls) > 0
    assert any(call == ["ydotool", "key", "163:1", "163:0"] for call in tsi.ydotool_calls)

def test_m3_accumulator_stress_boundaries(running_service):
    """
    2. Stress test accumulator scroll/volume/scrub logic.
    Test boundary coordinates (inf, nan, large values) and rapid oscillations.
    Verify stability (does not crash or hang).
    """
    mock_serial = running_service["mock_serial"]
    linapse_service = tsi.linapse_service
    
    # --- BROWSER MODE STRESS ---
    linapse_service.switch_mode("Browser")
    
    # Reset accumulators
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    
    # Test normal scroll
    mock_serial.input_queue.put(b">MOTION:0,0,0,160.0,0,0\n")
    time.sleep(0.02)
    # verify scroll down triggered (ydotool mousemove -w -- 0 1)
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "1"] for call in tsi.ydotool_calls)
    
    # A. Send NaN coordinate
    # nan is sanitized to 0.0, so it decays accumulator
    linapse_service._rx_scroll_accumulator = 10.0
    mock_serial.input_queue.put(b">MOTION:0,0,0,nan,0,0\n")
    time.sleep(0.02)
    # Should decay by 0.8: 10.0 * 0.8 = 8.0
    assert abs(linapse_service._rx_scroll_accumulator - 8.0) < 0.01

    # B. Send inf coordinate
    # inf is sanitized to 0.0, so it decays accumulator
    tsi.ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,inf,0,0\n")
    time.sleep(0.02)
    # Should decay by 0.8: 8.0 * 0.8 = 6.4
    assert abs(linapse_service._rx_scroll_accumulator - 6.4) < 0.01
    
    # C. Send further finite motion: should update accumulator normally and trigger a scroll
    mock_serial.input_queue.put(b">MOTION:0,0,0,160.0,0,0\n")
    time.sleep(0.02)
    # 6.4 + 160.0 = 166.4
    # 166.4 // 150.0 = 1 scroll
    # 166.4 - 150 = 16.4 remaining
    assert abs(linapse_service._rx_scroll_accumulator - 16.4) < 0.01
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "1"] for call in tsi.ydotool_calls)
    
    # D. Large values: 1.5e5
    # Let's reset the accumulator first
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,1.5e5,0,0\n")
    time.sleep(0.02)
    # scrolls = 150000 // 150.0 = 1000
    # should dispatch scrolls of 1000
    assert any(call == ["ydotool", "mousemove", "-w", "--", "0", "1000"] for call in tsi.ydotool_calls)
    
    # E. Rapid oscillations
    linapse_service._rx_scroll_accumulator = 0.0
    tsi.ydotool_calls.clear()
    for _ in range(10):
        mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
        mock_serial.input_queue.put(b">MOTION:0,0,0,-100.0,0,0\n")
    time.sleep(0.05)
    # Accumulator should oscillate around 0, never triggering scroll actions
    assert abs(linapse_service._rx_scroll_accumulator) < 0.01
    assert not any(call[1] == "mousemove" and "-w" in call for call in tsi.ydotool_calls)

    # --- MEDIA MODE STRESS ---
    linapse_service.switch_mode("Media")
    linapse_service._rz_scrub_accumulator = 0.0
    linapse_service._rx_volume_accumulator = 0.0
    tsi.ydotool_calls.clear()
    
    # A. Send inf to RZ (scrub)
    # RZ scrub: inf is sanitized to 0.0, should decay accumulator
    linapse_service._rz_scrub_accumulator = 10.0
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,inf\n")
    time.sleep(0.02)
    assert abs(linapse_service._rz_scrub_accumulator - 8.0) < 0.01
    
    # Reset RZ scrub accumulator
    linapse_service._rz_scrub_accumulator = 0.0
    
    # B. Send inf to RX (volume)
    # RX volume: inf is sanitized to 0.0, should decay accumulator
    linapse_service._rx_volume_accumulator = 10.0
    mock_serial.input_queue.put(b">MOTION:0,0,0,inf,0,0\n")
    time.sleep(0.02)
    assert abs(linapse_service._rx_volume_accumulator - 8.0) < 0.01
