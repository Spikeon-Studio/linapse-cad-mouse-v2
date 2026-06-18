# Original User Request

## Initial Request — 2026-06-18T06:04:49-04:00

Implement Option A (Spacenavd Replacement) for the Linapse CAD Mouse MK2 host software stack.

Working directory: /home/spikeon/Dev/linapse-cad-mouse-v2
Integrity mode: development

## Requirements

### R1. Socket Server in linapse-service
- Implement an AF_UNIX SOCK_STREAM server in [linapse-service](file:///home/spikeon/Dev/linapse-cad-mouse-v2/linux/linapse-service) listening at `/run/user/<UID>/spnav.sock` (resolved using `os.getuid()`).
- Parse incoming `>MOTION:x,y,z,rx,ry,rz` lines from the serial interface.
- Convert the 6 float values to integers and map/pack them into 32-byte binary structures matching the spacenav protocol format: `[0, x, z, y, rx, ry, rz, period]` (note y/z swapping).
- Broadcast the packed 32-byte events to all connected socket clients.

### R2. Relocated Socket Path Patch
- Modify [patch-spacenav-ws.py](file:///home/spikeon/Dev/linapse-cad-mouse-v2/linux/patch-spacenav-ws.py) to replace `/var/run/spnav.sock` connection strings with the custom user-space socket path `/run/user/<UID>/spnav.sock` inside the `spacenav_ws` Python package cache.

### R3. Host Integration Installer and Clean-up
- Modify [setup.sh](file:///home/spikeon/Dev/linapse-cad-mouse-v2/setup.sh) and [install.sh](file:///home/spikeon/Dev/linapse-cad-mouse-v2/linux/install.sh):
  - Fully uninstall the system-wide `spacenavd` package using the detected package manager (`pacman`, `apt-get`, or `dnf`).
  - Remove udev rules copy, `/etc/spnavrc` copy, and `spacenavd` daemon control logic.
  - Remove VID/PID prompting and checks from the installer and [flash.sh](file:///home/spikeon/Dev/linapse-cad-mouse-v2/linux/flash.sh).
  - Comment out or remove the SpaceMouse USB VID/PID override lines in [platformio.ini](file:///home/spikeon/Dev/linapse-cad-mouse-v2/platformio.ini).

## Acceptance Criteria

### Installation and Cleanup
- [ ] Running the installer uninstalls the `spacenavd` package.
- [ ] No `spacenavd` processes are active on the host machine.
- [ ] No files are written to `/etc/udev/rules.d/99-spacemouse.rules` or `/etc/spnavrc`.
- [ ] PlatformIO firmware builds and flashes successfully without prompting for USB VID/PID.

### Runtime Functionality
- [ ] Running `linapse-service` creates a UNIX socket at `/run/user/<UID>/spnav.sock`.
- [ ] Running `spacenav-ws` connects to `/run/user/<UID>/spnav.sock` and stays connected.
- [ ] Moving the CAD Mouse puck streams coordinates through the UNIX socket to `spacenav-ws`, translating to smooth viewport movements.
- [ ] Configurator live Benchy test continues to function.
