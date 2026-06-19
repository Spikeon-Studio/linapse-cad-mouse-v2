import os
import sys
import time
import socket
import asyncio
import threading
import http.server
import socketserver
import websockets
import pytest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Skip if playwright is not installed
pytestmark = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")

# Helper to find free ports
def get_free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

# Threaded HTTP Server to serve configurator/
class ThreadedHTTPServer:
    def __init__(self, port, directory):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
            def log_message(self, format, *args):
                pass  # Suppress HTTP server output in test logs

        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(("localhost", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

# Mock WebSocket Server
class MockWSServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.server = None
        self.clients = set()
        self.loop = None
        self.thread = None

    def start(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._start_server())
        self.loop.run_forever()

    async def _start_server(self):
        self.server = await websockets.serve(self._handler, self.host, self.port)

    async def _handler(self, ws):
        self.clients.add(ws)
        try:
            async for msg in ws:
                pass
        except Exception:
            pass
        finally:
            self.clients.discard(ws)

    def broadcast(self, message):
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)

    async def _broadcast(self, message):
        if self.clients:
            await asyncio.gather(*(c.send(message) for c in list(self.clients)), return_exceptions=True)

    def stop(self):
        if self.loop:
            if self.server:
                self.server.close()
            self.loop.call_soon_threadsafe(self.loop.stop)

def test_benchy_viewport_motion():
    # Setup directories
    linux_dir = Path(__file__).parent
    configurator_dir = linux_dir.parent / "configurator"
    assert configurator_dir.exists(), f"Configurator directory not found at {configurator_dir}"

    # Allocate ports
    http_port = get_free_port()
    ws_port = get_free_port()

    # Start HTTP and WS servers
    http_server = ThreadedHTTPServer(http_port, str(configurator_dir))
    http_server.start()

    ws_server = MockWSServer("localhost", ws_port)
    ws_server.start()

    # Wait for servers to spin up
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Intercept and redirect WebSocket connection to our test port
            redirect_js = f"""
            const OriginalWebSocket = window.WebSocket;
            window.WebSocket = class extends OriginalWebSocket {{
                constructor(url, protocols) {{
                    const newUrl = url.replace(':13000', ':{ws_port}');
                    super(newUrl, protocols);
                }}
            }};
            """
            page.add_init_script(redirect_js)

            # Load page
            page.goto(f"http://localhost:{http_port}/index.html")

            # Click the "Sensitivity" tab to load the Benchy viewport
            page.click("text=Sensitivity")

            # Poll until benchyScene is initialized
            start_time = time.time()
            initialized = False
            while time.time() - start_time < 5.0:
                is_ready = page.evaluate("() => typeof benchyScene !== 'undefined' && benchyScene !== null && benchyScene.benchy !== undefined")
                if is_ready:
                    initialized = True
                    break
                time.sleep(0.1)

            assert initialized, "benchyScene failed to initialize within 5 seconds"

            # Get initial position and rotation
            initial = page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")

            # Helper to get current coordinates
            def get_current():
                return page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")

            # Test X Translation (Left/Right)
            ws_server.broadcast("MOTION:100,0,0,0,0,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['x'] > initial['x'], f"X translation (right) failed: expected > {initial['x']}, got {curr['x']}"

            ws_server.broadcast("MOTION:-200,0,0,0,0,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['x'] < initial['x'], f"X translation (left) failed: expected < {initial['x']}, got {curr['x']}"

            # Reset position for next tests
            page.evaluate("() => { const b = benchyScene.benchy; b.position.set(0, 0, 0); b.rotation.set(0, 0, 0); }")
            initial = get_current()

            # Test Z Translation (Pull Up / Push Down on Z axis, maps to Y on screen)
            # Pull Up (negative Z value in motion, e.g. v[2] < 0) -> Benchy moves UP (y increases)
            ws_server.broadcast("MOTION:0,0,-100,0,0,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['y'] > initial['y'], f"Z translation (Pull Up) failed: expected y > {initial['y']}, got {curr['y']}"

            # Push Down (positive Z value in motion, e.g. v[2] > 0) -> Benchy moves DOWN (y decreases)
            ws_server.broadcast("MOTION:0,0,200,0,0,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['y'] < initial['y'], f"Z translation (Push Down) failed: expected y < {initial['y']}, got {curr['y']}"

            # Reset
            page.evaluate("() => { const b = benchyScene.benchy; b.position.set(0, 0, 0); b.rotation.set(0, 0, 0); }")
            initial = get_current()

            # Test Pitch (RX Axis rotation)
            ws_server.broadcast("MOTION:0,0,0,100,0,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['rx'] > initial['rx'], f"RX Pitch failed: expected rx > {initial['rx']}, got {curr['rx']}"

            # Test Yaw (RY Axis rotation)
            ws_server.broadcast("MOTION:0,0,0,0,100,0")
            time.sleep(0.2)
            curr = get_current()
            assert curr['ry'] > initial['ry'], f"RY Yaw failed: expected ry > {initial['ry']}, got {curr['ry']}"

            # Test Roll (RZ Axis rotation)
            # v[5] > 0 -> rotation.z decreases
            ws_server.broadcast("MOTION:0,0,0,0,0,100")
            time.sleep(0.2)
            curr = get_current()
            assert curr['rz'] < initial['rz'], f"RZ Roll failed: expected rz < {initial['rz']}, got {curr['rz']}"

            browser.close()
    finally:
        ws_server.stop()
        http_server.stop()
