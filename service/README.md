# CAD Mouse MK2 — Linux Setup

This directory contains everything needed to get the CAD Mouse MK2 working on Linux, including full 6DoF motion in browser-based CAD and native applications.

## How it works

Linux has no official 3Dconnexion driver. The solution is a chain of open-source tools:

```
CAD Mouse MK2
    │  USB HID & Serial (Seeed XIAO RP2040)
    ▼
linapse-service    — bridges serial/HID inputs, translates buttons/taps via ydotool,
    │               and creates /run/user/<uid>/spnav.sock
    │
    ├─► Native Linux Apps (Blender, FreeCAD, etc.) — read spnav.sock via libspnav
    │
    └─► linapse-service — WebSocket bridge to browser apps (wss://127.51.68.120:8181)
            ▲
        Linapse Browser Connector (official extension)
            ▲
        Browser Apps (OnShape, SketchUp Web)
```

## Prerequisites

| Package | Notes |
|---------|-------|
| `ydotool` | Arch: `sudo pacman -S ydotool` |
| `python3` + pip | Browser bridge deps installed by `install.sh` (`fastapi`, `uvicorn`, `numpy`, `scipy`, `websockets`) |
| Browser | Install the [Linapse Browser Connector](../docs/BROWSER_EXTENSION.md) (Chrome, Edge, Firefox, Safari) |

## Firmware

Before running the installer, flash the firmware. You can do this easily from the **Firmware** tab in the **Linapse Configurator** UI (which compiles and flashes automatically), or manually:
1. Hold **B**, tap **R** on the XIAO RP2040 to enter BOOTSEL mode (or hold B while plugging in)
2. Build and copy the firmware: `pio run && sudo mount /dev/sdX1 /mnt && sudo cp .pio/build/seeed_xiao_rp2040/firmware.uf2 /mnt/ && sudo umount /mnt`

## Installation

```bash
cd service
chmod +x install.sh
./install.sh
```

The installer:
- Adds your user to the `input` group (needed for hidraw button access)
- Installs `linapse-service` to `~/.local/bin/`
- Installs and enables two systemd user services: `ydotoold`, `linapse-service` (includes the browser CAD bridge on port 8181)
- Configures `~/.config/environment.d/99-spnav.conf` so native apps find the user socket path automatically
- Installs udev rules so services restart automatically on plug/unplug
- On Ubuntu 24.04+ installs an AppArmor profile (`/etc/apparmor.d/linapse-electron`) so the Electron configurator's Chromium sandbox can create user namespaces (skipped on distros without the restriction)
- Vendors the OnShape/SketchUp WebSocket protocol stack in `service/spacenav_ws/` (no external `spacenav-ws` PyPI package)
- Enables the local dev-sync git hook (see below) so future `git pull`s keep this deployment current

### Local dev hooks

`install.sh` copies `service/` into `~/.local/bin/` and bakes this checkout's absolute path into the installed systemd unit and desktop launcher. None of that re-runs on `git pull` — only `install.sh` does it — so a dev checkout can silently drift from what's actually installed and running. This has caused real bugs on dev machines: a home-directory rename left stale absolute paths in the installed systemd unit and desktop launcher (configurator served 404s, launcher icon didn't resolve), and separately `~/.local/bin/linapse-service` sat months behind the repo, still running code with an already-fixed phantom-gamepad bug (the CAD Mouse kept registering/deregistering as a game controller, e.g. in Steam, outside Controller mode) because nobody had re-run `install.sh` since.

`install.sh` now runs `git config core.hooksPath .githooks`, which points git at the hooks in [`.githooks/`](../.githooks) (`post-merge`, `post-checkout`). Those call [`scripts/dev-resync.sh`](../scripts/dev-resync.sh), which:
- Re-copies `service/linapse-service`, `service/linapse/`, `service/spacenav_ws/`, `service/linapse-ws-proxy` into `~/.local/bin/` if they differ, and restarts `linapse-service` if anything changed
- Re-renders the configurator's systemd unit and desktop launcher from their templates (picks up a changed repo path or template edits) and restarts/reloads as needed

It's idempotent and only touches what's actually out of date, so it's safe to run any time: `scripts/dev-resync.sh`. If you didn't run `install.sh` on this checkout (or cloned it elsewhere), enable the hook manually with `git config core.hooksPath .githooks`, or just re-run `scripts/dev-resync.sh` after pulling.

After the installer finishes, install the Linapse Browser Connector browser extension:

1. Install the Linapse Browser Connector from your browser's extension store (links printed at the end of install).
2. Open OnShape or SketchUp Web and open any document — motion should work immediately.

See **[docs/BROWSER_EXTENSION.md](../docs/BROWSER_EXTENSION.md)** for store links, enterprise policy install, and Safari build instructions.

For detailed setup, configuration, and verification guides for all 14 supported/experimental applications (including Blender, FreeCAD, Unreal Engine, Unity, etc.), see **[docs/INTEGRATIONS.md](../docs/INTEGRATIONS.md)**.

> **Note:** If you were just added to the `input` group, log out and back in (or reboot) before the buttons will work.

## Button mapping & Motion tuning

To change button maps, tap gestures, lighting, or motion tuning, use the **Linapse Configurator** (see `docs/USAGE.md` for details). 

Manual configuration is loaded from:
`~/.config/cad-mouse/actions.json`

If you modify configuration files manually, restart the service to apply changes:
```bash
systemctl --user restart linapse-service
```

## Troubleshooting

**Motion not working in Browser (OnShape / SketchUp)**
- Check the Linapse Browser Connector extension is enabled
- Check `linapse-service` is running: `systemctl --user status linapse-service`
- The browser bridge runs inside `linapse-service` at `wss://127.51.68.120:8181`

**Buttons not working**
- Ensure you're in the `input` group: `groups | grep input` (reboot if you just added yourself)
- Check the linapse-service logs: `journalctl --user -u linapse-service -f`
- Verify the hidraw device exists: `ls /dev/input/by-id/ | grep -i CAD_Mouse`

**Device not recognised after plugging in**
```bash
# Manually restart services
systemctl --user restart linapse-service
```

**Services hitting start-limit**
```bash
systemctl --user reset-failed linapse-service
systemctl --user restart linapse-service
```

