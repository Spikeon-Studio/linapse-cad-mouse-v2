# Project: Linapse CAD Mouse Cross-Platform Support

## Architecture
- `linapse-service` running as the host service.
- Serial communication reads from serial port.
- Input simulation: `ydotool` (Linux), `pynput` (Windows, macOS).
- Socket communication: Unix domain socket on Linux only.
- CI/CD workflow: `multi-distro-test.yml` packaging executables using PyInstaller and creating installers.

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| 1 | Explore & Design | Analyze code, write design plan | none | DONE |
| 2 | Implementation | Cross-platform porting of linapse-service | M1 | DONE |
| 3 | Verification | Unit tests mocking platform & running existing tests | M2 | DONE |
| 4 | Packaging & CI/CD | PyInstaller packaging, Windows & macOS installers, GHA setup | M3 | DONE |
| 5 | Version Release | Increment version, update VERSION, userscript, and CHANGELOG | M4 | DONE |

## Interface Contracts
### Serial Interface
- Read lines starting with `TAP:`, `>MOTION:`, and responses.
- Write commands starting with `led `.
### Configurator WebSocket
- Read/write JSON configurations and events.
### Input Emulation Interface
- Map buttons/taps/motion deflection to keystrokes, scroll, volume, etc.

## Code Layout
- `linux/linapse-service`: The main host daemon
- `linux/test_signal_integration.py`: Main integration tests
- `VERSION`: Holds the project version
- `CHANGELOG.md`: Tracks project history
- `.github/workflows/multi-distro-test.yml`: GHA workflow
