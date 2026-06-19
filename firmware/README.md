# Linapse CAD Mouse Firmware

Firmware for the 6-DoF magnetic CAD space mouse, designed for the Raspberry Pi RP2040 controller (specifically the Seeed Studio XIAO RP2040). It interfaces with three TLV493D 3D magnetic sensors to compute knob translation and rotation, sending standardized USB HID multi-axis controller reports.

## System Architecture & File Layout

- **`include/Config.h`**: Device constants, pin definitions, default gain matrices, axis signs, tap detection thresholds, and animation speeds.
- **`include/LedConfig.h` / `src/LedConfig.cpp`**: Manages LED preferences (brightness, color, effect index) and EEPROM persistence.
- **`include/SensConfig.h` / `src/SensConfig.cpp`**: Manages sensitivity settings (deadzones, Kalman parameters, sensitivity exponent) and EEPROM persistence.
- **`src/controllers/MotionController.cpp`**: Applies baseline subtraction, scaling, 1D Kalman filtering, deadzone clamping, and sensitivity curves to generate 6-DoF output.
- **`src/controllers/TapDetector.cpp`**: Real-time translation velocity monitoring to detect mechanical taps on the knob, emitting serial events.
- **`src/controllers/EffectEngine.cpp`**: Animates the 8-pixel NeoPixel LED ring with multiple modes (e.g. solid, breathing, reactive, swirl, and volume).
- **`src/controllers/HIDController.cpp`**: Manages USB HID communication for multi-axis reports (Report ID 1) and physical buttons (Report ID 3).
- **`src/main.cpp`**: System initialization, 100Hz control loop, and USB Serial command handling.

---

## Building and Flashing

This project is built using **PlatformIO**. Target environment and build configurations are located in `platformio.ini`.

To flash the device:
1. Hold both physical buttons down while inserting the USB cable.
2. The device will reboot to bootloader (BOOTSEL) mode, mounting as a USB storage drive.
3. Drag and drop the compiled `.uf2` file, or flash directly using the Web Configurator build utility.
4. Alternatively, sending a reset command or opening a serial connection at 1200 baud resets the RP2040 to bootloader mode.

---

## Sensor Geometry & Motion Processing

### Sensor Layout
- **`mag1`**: Bottom sensor
- **`mag2`**: Top-left sensor
- **`mag3`**: Top-right sensor

### Geometric Decomposition
The raw magnetic coordinates (after subtracting the baseline rest calibration) are transformed into translation (Tx, Ty, Tz) and rotation (Rx, Ry, Rz) using the following geometric equations:

```
Tx = (mag1x + mag2x + mag3x) / 3
Ty = (mag1y + mag2y + mag3y) / 3
Tz = (mag1z + mag2z + mag3z) / 3

Rx = sqrt(3) * (mag2z + mag3z - 2 * mag1z) / 3
Ry = mag3z - mag2z
Rz = sum_i (posXi * magYi - posYi * magXi)
```

- **Tx, Ty, Tz**: Average deflection across all three sensors.
- **Ry**: Left-right Z difference across the top edge.
- **Rx**: Top pair versus bottom, scaled for equilateral triangle geometry.
- **Rz**: Twist estimate computed using the X/Y positions of the sensors.

---

## Linapse Fork Changes

The Linapse fork introduces several enhancements to improve device stability, responsiveness, configuration persistence, and system integration:

### 1. Kalman Filtering
A 1D Kalman filter runs independently on each of the six motion axes to filter out magnetic noise and sensor jitter.
- **Process Noise (`kalman_q`)** and **Measurement Noise (`kalman_r`)** are fully configurable at runtime.
- **Deactivity Decay**: When deflection falls below the deadzone threshold, the filter state is decayed toward zero (`kalmanX *= 0.8f`) while preserving covariance. This avoids jumpy boundary transitions.

### 2. Volume Visualizer Effect
A custom lighting effect (`volume`) visualizes the host system volume (0–100%) on the 8 LED ring:
- LEDs 1 to 8 light up sequentially to represent volume levels.
- Supports fractional intensity: the boundary LED interpolates its brightness smoothly based on the exact percentage.
- Synced dynamically via the background host service (`linapse-service`).

### 3. Multi-Click/Tap Integrations
Tapping the knob head acts as a macro input, generating secondary command dispatches without physical buttons:
- **Directional Detection**: Differentiates between taps in five directions: `PosX` (right), `NegX` (left), `PosY` (forward), `NegY` (back), and `NegZ` (upward/downward force). `PosZ` (upward pull from below) is physically impossible and suppressed.
- **Multi-Tap Window**: Detects single, double, triple, or quadruple clicks within a configurable timeframe (e.g. 300ms).
- **Motion Suppression**: Mouse cursor movement and telemetry are temporarily suppressed while tapping is in progress to prevent pointer drift.
- **Serial Alerts**: Outputs real-time events in the format `TAP:<DIR>:<COUNT>` (e.g., `TAP:NegX:2` for double left tap) for daemon handling.

### 4. Configuration Persistence Layout
Settings are persisted in the RP2040's simulated EEPROM. Separate magic bytes ensure validation across updates:
- **LED Config (Bytes 0-15)**: Magic `0xCAD10002`, Brightness, Idle Color, and Active Effect.
- **Sensitivity Config (Bytes 16-39)**: Magic `0xCAD30001`, Translational Deadzone, Rotational Deadzone, Kalman `Q`, Kalman `R`, and Sensitivity Exponent.

### 5. Serial Command Extensions
Expanded serial terminal communication (at 115200 baud) for total runtime configuration. See `LED_COLOR_CONFIG.md` for a comprehensive command reference.
