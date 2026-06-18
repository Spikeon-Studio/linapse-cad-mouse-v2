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
    └─► spacenav-ws — WebSocket bridge to browser apps (port 8181)
            ▲
        Tampermonkey browser userscript (platform spoofing)
            ▲
        Browser Apps (OnShape, SketchUp Web)
```

## Prerequisites

| Package | Notes |
|---------|-------|
| `ydotool` | Arch: `sudo pacman -S ydotool` |
| `uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `python3` | Usually pre-installed |
| Tampermonkey | Browser extension (Chrome/Firefox) |

## Firmware

Before running the installer, flash the firmware. Build and copy the firmware:
1. Hold **B**, tap **R** on the XIAO RP2040 to enter BOOTSEL mode (or hold B while plugging in)
2. Build and copy the firmware: `pio run && sudo mount /dev/sdX1 /mnt && sudo cp .pio/build/seeed_xiao_rp2040/firmware.uf2 /mnt/ && sudo umount /mnt`

## Installation

```bash
cd linux
chmod +x install.sh
./install.sh
```

The installer:
- Adds your user to the `input` group (needed for hidraw button access)
- Installs `linapse-service` to `~/.local/bin/`
- Installs and enables three systemd user services: `ydotoold`, `spacenav-ws`, `linapse-service`
- Configures `~/.config/environment.d/99-spnav.conf` so native apps find the user socket path automatically
- Installs udev rules so services restart automatically on plug/unplug
- Patches `spacenav-ws` to disable its built-in button-snap behaviour

After the installer finishes, install the Tampermonkey userscript:

1. Install [Tampermonkey](https://www.tampermonkey.net/) in your browser
2. Drag `linux/linapse-browser-connector.user.js` onto the Tampermonkey dashboard
3. Open OnShape or SketchUp Web and open any document — motion should work immediately

For detailed setup, configuration, and verification guides for all 14 supported/experimental applications (including Blender, FreeCAD, Unreal Engine, Unity, etc.), see **[docs/INTEGRATIONS.md](../docs/INTEGRATIONS.md)**.

> **Note:** If you were just added to the `input` group, log out and back in (or reboot) before the buttons will work.

## Button mapping & Sensitivity tuning

To change button maps, tap gestures, lighting, or motion sensitivity, use the **Linapse Configurator** (see `docs/USAGE.md` for details). 

Manual configuration is loaded from:
`~/.config/cad-mouse/actions.json`

If you modify configuration files manually, restart the service to apply changes:
```bash
systemctl --user restart linapse-service
```

## Troubleshooting

**Motion not working in Browser (OnShape / SketchUp)**
- Check the Tampermonkey userscript is active on the page
- Refresh the browser tab after any service restart
- Check spacenav-ws is running: `systemctl --user status spacenav-ws`
- Check linapse-service is running: `systemctl --user status linapse-service`

**Buttons not working**
- Ensure you're in the `input` group: `groups | grep input` (reboot if you just added yourself)
- Check the linapse-service logs: `journalctl --user -u linapse-service -f`
- Verify the hidraw device exists: `ls /dev/input/by-id/ | grep -i CAD_Mouse`

**Device not recognised after plugging in**
```bash
# Manually restart services
systemctl --user restart spacenav-ws linapse-service
```

**Services hitting start-limit**
```bash
systemctl --user reset-failed spacenav-ws linapse-service
systemctl --user restart spacenav-ws linapse-service
```

