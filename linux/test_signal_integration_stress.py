#!/usr/bin/env python3
import asyncio
import os
import sys
import struct
import json
import time
import socket
import select
import queue
import threading
import glob
import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

try:
    import websockets
except ImportError:
    pytest.skip("websockets is not installed", allow_module_level=True)

# Import the original test suite to reuse its classes, functions, and linapse_service module
import test_signal_integration as tsi
linapse_service = tsi.linapse_service

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def count_open_fds():
    try:
        return len(os.listdir("/proc/self/fd"))
    except Exception:
        return 0

def get_active_daemon_threads():
    return [t for t in threading.enumerate() if t.is_alive() and t != threading.main_thread()]

def setup_service(tmp_path):
    tsi.teardown_initiated = False
    tsi.started_threads.clear()
    tsi.ydotool_calls.clear()
    
    temp_socket_path = tmp_path / "spnav.sock"
    temp_actions_path = tmp_path / "actions.json"
    
    # Write initial configuration
    initial_actions = {
        "button_override": False,
        "buttons": {
            "0": {"action": "scroll_down"},
            "1": {"action": "scroll_up"},
            "chord": {"action": "key", "value": "shift+7"}
        },
        "taps": {
            "top:1": {"action": "key", "value": "ctrl+alt+t"}
        },
        "sensitivity": {},
        "inversion": {}
    }
    with open(temp_actions_path, "w") as f:
        json.dump(initial_actions, f)
        
    # Override service config paths and port
    linapse_service.ACTIONS_PATH = tsi.MockPathObj(temp_actions_path)
    free_port = get_free_port()
    linapse_service.WS_PORT = free_port
    
    # Setup pipe for HID mock
    read_fd, write_fd = os.pipe()
    mock_serial = tsi.MockSerial()
    
    # Setup loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    linapse_service._loop = loop
    
    # Reset internal variables
    linapse_service._socket_clients.clear()
    linapse_service._ws_clients.clear()
    linapse_service._held.clear()
    linapse_service._chord_fired = False
    linapse_service._timers.clear()
    linapse_service._scroll_threads.clear()
    
    patchers = [
        patch("linapse_service.Path", tsi.mock_path_factory(temp_socket_path)),
        patch("linapse_service.serial.Serial", return_value=mock_serial),
        patch("linapse_service.glob.glob", tsi.custom_glob),
        patch("linapse_service.open", tsi.mock_open_factory(read_fd)),
        patch("linapse_service.subprocess.Popen", tsi.mock_popen),
        patch("time.sleep", tsi.custom_sleep),
    ]
    
    for p in patchers:
        p.start()
        
    threading.Thread.__init__ = tsi.custom_init
    threading.excepthook = tsi.custom_excepthook
    
    # Start service main
    service_task = loop.create_task(linapse_service.main())
    
    # Let event loop spin to startup servers
    loop.run_until_complete(asyncio.sleep(0.1))
    
    return {
        "loop": loop,
        "ws_port": free_port,
        "socket_path": temp_socket_path,
        "actions_path": temp_actions_path,
        "mock_serial": mock_serial,
        "write_fd": write_fd,
        "read_fd": read_fd,
        "patchers": patchers,
        "service_task": service_task
    }

def teardown_service(svc):
    loop = svc["loop"]
    patchers = svc["patchers"]
    service_task = svc["service_task"]
    write_fd = svc["write_fd"]
    read_fd = svc["read_fd"]
    
    # Teardown sequence
    tsi.teardown_initiated = True
    
    # Cancel the main service task
    service_task.cancel()
    try:
        loop.run_until_complete(service_task)
    except asyncio.CancelledError:
        pass
        
    # Close pipes
    try:
        os.close(write_fd)
    except OSError:
        pass
    try:
        os.close(read_fd)
    except OSError:
        pass
        
    # Trigger thread exit across all threads by waking them up
    for t in list(tsi.started_threads):
        t.join(timeout=0.2)
        
    # Stop all patchers
    for p in reversed(patchers):
        p.stop()
        
    # Restore excepthook
    threading.Thread.__init__ = tsi.original_init
    threading.excepthook = tsi.original_excepthook
    
    # Clean up event loop and close lingering sockets
    linapse_service._loop = None
    
    # Close any lingering socket clients
    for writer in list(linapse_service._socket_clients):
        try:
            writer.close()
            loop.run_until_complete(writer.wait_closed())
        except Exception:
            pass
    linapse_service._socket_clients.clear()
    
    # Close any lingering ws clients
    for ws in list(linapse_service._ws_clients):
        try:
            loop.run_until_complete(ws.close())
        except Exception:
            pass
    linapse_service._ws_clients.clear()
    
    # Cancel all remaining tasks on loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        
    loop.close()

def test_fixture_rapid_restarts(tmp_path):
    """Verify that rapid setup/teardown of running_service fixture does not leak threads or sockets."""
    print(f"\n--- Starting rapid fixture restart stress test ---", flush=True)
    
    initial_threads = get_active_daemon_threads()
    initial_fds = count_open_fds()
    
    for i in range(20):
        svc = setup_service(tmp_path)
        try:
            loop = svc["loop"]
            ws_port = svc["ws_port"]
            sock_path = svc["socket_path"]
            
            async def quick_ping():
                reader, writer = await asyncio.open_unix_connection(str(sock_path))
                writer.close()
                await writer.wait_closed()
                
            loop.run_until_complete(quick_ping())
        finally:
            teardown_service(svc)
                
        # Give a very brief moment for OS to release resources/threads
        time.sleep(0.02)
        
    final_threads = get_active_daemon_threads()
    final_fds = count_open_fds()
    
    print(f"Initial threads: {len(initial_threads)}, Final threads: {len(final_threads)}")
    print(f"Initial FDs: {initial_fds}, Final FDs: {final_fds}")
    
    # Assert no thread leaks
    thread_diff = len(final_threads) - len(initial_threads)
    assert thread_diff <= 0, f"Thread leak detected! Leaked {thread_diff} threads: {final_threads}"
    
    # Assert no FD leaks
    fd_diff = final_fds - initial_fds
    assert fd_diff <= 2, f"FD/Socket leak detected! Leaked {fd_diff} FDs"

def test_high_frequency_packet_load(tmp_path):
    """Verify service behavior and event loop responsiveness under high-frequency simulated loads."""
    svc = setup_service(tmp_path)
    loop = svc["loop"]
    ws_port = svc["ws_port"]
    mock_serial = svc["mock_serial"]
    socket_path = svc["socket_path"]
    
    async def run_load():
        # Connect one WS client and one Unix socket client
        uri = f"ws://localhost:{ws_port}"
        ws = await websockets.connect(uri)
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        
        ws_received = []
        sock_received = []
        
        async def ws_reader():
            try:
                while True:
                    msg = await ws.recv()
                    ws_received.append(msg)
            except Exception:
                pass
                
        async def sock_reader():
            try:
                while True:
                    data = await reader.readexactly(32)
                    sock_received.append(data)
            except Exception:
                pass
                
        ws_task = asyncio.create_task(ws_reader())
        sock_task = asyncio.create_task(sock_reader())
        
        # Flood the serial queue with motion packets
        num_packets = 1000
        t0 = time.time()
        for i in range(num_packets):
            mock_serial.input_queue.put(b">MOTION:1.0,2.0,3.0,4.0,5.0,6.0\n")
            
        # Wait for all packets to be broadcast and received by both clients
        # Use a timeout of 5 seconds to prevent hanging
        timeout = 5.0
        while (len(ws_received) < num_packets or len(sock_received) < num_packets) and (time.time() - t0 < timeout):
            await asyncio.sleep(0.01)
            
        duration = time.time() - t0
        print(f"Processed {len(ws_received)} WS packets and {len(sock_received)} socket packets in {duration:.3f}s")
        
        # Clean up tasks
        ws_task.cancel()
        sock_task.cancel()
        await ws.close()
        writer.close()
        await writer.wait_closed()
        
        assert len(ws_received) == num_packets, f"WS received only {len(ws_received)}/{num_packets}"
        assert len(sock_received) == num_packets, f"Socket received only {len(sock_received)}/{num_packets}"
        
    try:
        loop.run_until_complete(run_load())
    finally:
        teardown_service(svc)

def test_timer_race_leak_on_teardown(tmp_path):
    """Verify if a pending Timer thread or scroll thread started just before teardown is correctly cleaned up."""
    svc = setup_service(tmp_path)
    
    # We will trigger a button press to start a Timer thread
    # The Timer thread will be active during teardown
    actions = {
        "button_override": False,
        "buttons": {
            "0": {"action": "scroll_down"}
        }
    }
    
    # Press button 0 (starts the Timer)
    linapse_service._on_press(0, actions)
    
    # Verify timer is running
    assert len(linapse_service._timers) == 1
    
    # Immediately trigger teardown of the service
    teardown_service(svc)
        
    # Give a brief moment for cleanup threads to stop
    time.sleep(0.15)
    
    # Check if any timers or scroll threads are still running
    # If the timer fired during teardown, it might have spawned a scroll thread
    # which could leak if not handled
    active_scroll_threads = len(linapse_service._scroll_threads)
    active_timers = len(linapse_service._timers)
    
    print(f"After teardown: active scroll threads = {active_scroll_threads}, active timers = {active_timers}")
    
    # Assert no scroll threads or timers remain active
    assert active_scroll_threads == 0, "Scroll thread leaked on teardown!"
    assert active_timers == 0, "Timer leaked on teardown!"
