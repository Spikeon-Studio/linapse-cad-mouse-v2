# Project: Linapse CAD Mouse MK2 Option A (Spacenavd Replacement)

## Architecture
- `linapse-service` owns serial connection (`/dev/ttyACM*`), button HIDraw, and broadcasts:
  1. Configurator WebSocket events on `ws://localhost:13000`.
  2. Unix socket events on `/run/user/<UID>/spnav.sock` (replacing system-wide `spacenavd`).
- `spacenav-ws` connects to `/run/user/<UID>/spnav.sock`, reads packed binary structures, and streams events to clients (e.g. OnShape).
- Python script `patch-spacenav-ws.py` updates connection strings inside `spacenav_ws` package.
- `setup.sh` and `linux/install.sh` handle packaging cleanups and user-space setup.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|---|---|---|---|
| 1 | Explore & Setup | Analyze spacenav event format, locate spacenav-ws cache | None | DONE |
| 2 | R1: Socket Server | Implement UNIX socket server in `linapse-service` and packet broadcasting | M1 | DONE |
| 3 | R2: Socket Path Patch | Update `patch-spacenav-ws.py` to patch `spacenav_ws` and reconnect wrapper | M2 | DONE |
| 4 | R3: Host Installer & Clean-up | Remove spacenavd package, remove udev rules copy, etc. in `setup.sh` and `install.sh` | M3 | DONE |
| 5 | E2E & Validation | Verify all tests, runtime functionality, and build cleanly | M4 | DONE |

## Interface Contracts
### `linapse-service` Unix Socket ↔ `spacenav-ws`
- Protocol: AF_UNIX SOCK_STREAM
- Socket path: `/run/user/<UID>/spnav.sock`
- Broadcast Event Format: 32-byte binary struct matching spacenav protocol event.
- Packet format details: `[0, x, z, y, rx, ry, rz, period]` (y/z swapped, integer type).

## Code Layout
- `linux/linapse-service`: Main service executable (Python).
- `linux/patch-spacenav-ws.py`: Script to patch spacenav-ws in Python env cache.
- `linux/install.sh`: Installer script.
- `setup.sh`: Global setup script.
- `linux/flash.sh`: Firmware flash utility.
- `platformio.ini`: PlatformIO firmware build settings.
