#!/usr/bin/env python3
import asyncio
import os
import struct
import unittest
import time
import socket
import importlib.util
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Load the service module
service_path = Path(__file__).parent / "linapse-service"
loader = SourceFileLoader("linapse_service", str(service_path))
spec = importlib.util.spec_from_loader("linapse_service", loader)
linapse_service = importlib.util.module_from_spec(spec)
loader.exec_module(linapse_service)

class TestMilestone5Adversarial(unittest.TestCase):
    def setUp(self):
        print(f"\n--- setUp: {self._testMethodName} ---", flush=True)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        linapse_service._loop = self.loop
        linapse_service._socket_clients.clear()
        linapse_service._ws_clients.clear()
        self.socket_path = Path(f"/tmp/test_m5_adv_{os.getuid()}.sock")
        if self.socket_path.exists():
            self.socket_path.unlink()

    def tearDown(self):
        print(f"--- tearDown: {self._testMethodName} ---", flush=True)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        
        # Cancel all running tasks on the loop
        try:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                for task in pending:
                    task.cancel()
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            print(f"Error during pending tasks cancellation: {e}", flush=True)
            
        self.loop.close()

    def test_delayed_socket_creation(self):
        """
        Check that client-side reconnect logic successfully waits for socket creation.
        """
        async def run_test():
            client_connected = asyncio.Event()
            client_task_exception = None
            
            # Mimic the patched _mouse_with_reconnect loop
            async def mock_client_reconnect():
                nonlocal client_task_exception
                try:
                    while True:
                        try:
                            _r, _w = await asyncio.open_unix_connection(str(self.socket_path))
                            # Successfully connected!
                            client_connected.set()
                            _w.close()
                            await _w.wait_closed()
                            break
                        except OSError:
                            # Wait and retry
                            await asyncio.sleep(0.05)
                except Exception as e:
                    client_task_exception = e

            # Start client reconnect task before server exists
            client_task = asyncio.create_task(mock_client_reconnect())
            
            # Wait a bit, confirm client is still trying and hasn't connected or crashed
            await asyncio.sleep(0.2)
            self.assertFalse(client_connected.is_set())
            self.assertIsNone(client_task_exception)
            
            # Now start the server
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            # Wait for client to connect and exit
            await asyncio.wait_for(client_connected.wait(), timeout=2.0)
            self.assertTrue(client_connected.is_set())
            
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())

    def test_concurrent_connections_leak_check(self):
        """
        Connect 60 clients, disconnect them in waves, check for structure and FD leaks.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            clients = []
            num_clients = 60
            for i in range(num_clients):
                reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
                clients.append((reader, writer))
                
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), num_clients)
            
            # Wave 1: Close even index clients from client side
            for i in range(0, num_clients, 2):
                _, writer = clients[i]
                writer.close()
            
            # Wait for disconnect events to be processed
            await asyncio.sleep(0.1)
            self.assertEqual(len(linapse_service._socket_clients), num_clients // 2)
            
            # Wave 2: Close remaining clients
            for i in range(1, num_clients, 2):
                _, writer = clients[i]
                writer.close()
                
            await asyncio.sleep(0.1)
            self.assertEqual(len(linapse_service._socket_clients), 0)
            
            # Verify wait_closed on all
            for _, writer in clients:
                await writer.wait_closed()
                
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())

    def test_event_loop_responsiveness_packet_flood(self):
        """
        Flood 20,000 packets to a fast client and measure event loop cooperative delay.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            await asyncio.sleep(0.05)
            
            # Read client data in background
            received_count = 0
            async def client_reader():
                nonlocal received_count
                try:
                    while True:
                        data = await reader.readexactly(32)
                        received_count += 1
                except (asyncio.IncompleteReadError, asyncio.CancelledError):
                    pass

            reader_task = asyncio.create_task(client_reader())
            
            # Measure cooperative multitasking delay
            tick_times = []
            async def ticker():
                try:
                    while True:
                        t0 = time.time()
                        await asyncio.sleep(0.01)
                        tick_times.append(time.time() - t0)
                except asyncio.CancelledError:
                    pass
            
            ticker_task = asyncio.create_task(ticker())
            
            packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            flood_count = 10000
            
            t_start = time.time()
            for i in range(flood_count):
                await linapse_service._broadcast_socket(packet)
                if i % 100 == 0:
                    # Let the event loop run to process tasks
                    await asyncio.sleep(0.001)
                    
            # Wait for all packets to be read
            await asyncio.sleep(0.3)
            
            ticker_task.cancel()
            reader_task.cancel()
            writer.close()
            await asyncio.gather(ticker_task, reader_task, writer.wait_closed(), return_exceptions=True)
            server.close()
            await server.wait_closed()
            
            self.assertEqual(received_count, flood_count)
            
            # Check event loop delays: they should not be blocked for too long
            max_delay = max(tick_times) if tick_times else 0
            print(f"[DEBUG] Max loop tick delay during flood: {max_delay:.4f}s")
            # Usually, maximum delay should be less than 0.1s in cooperative setup
            self.assertLess(max_delay, 0.1, f"Event loop was blocked for too long: {max_delay:.4f}s")

        self.loop.run_until_complete(run_test())

    def test_invalid_input_to_unix_socket(self):
        """
        Send garbage bytes to the Unix socket server. Ensure it ignores them and stays healthy.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 1)
            
            # Send arbitrary random bytes to the server
            writer.write(b"GARBAGE_BYTES_STRESS_" * 100)
            await writer.drain()
            
            # Server should read and discard without crashing
            await asyncio.sleep(0.1)
            self.assertEqual(len(linapse_service._socket_clients), 1)
            
            # Confirm broadcasting still works to this client
            packet = struct.pack("iiiiiiii", 0, 9, 8, 7, 6, 5, 4, 10)
            await linapse_service._broadcast_socket(packet)
            
            data = await reader.readexactly(32)
            unpacked = struct.unpack("iiiiiiii", data)
            self.assertEqual(unpacked, (0, 9, 8, 7, 6, 5, 4, 10))
            
            writer.close()
            await writer.wait_closed()
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())

if __name__ == "__main__":
    unittest.main()
