# LED Ring and Device Configuration

The LED ring color, brightness, effects, and sensor sensitivity parameters can be configured at runtime without reflashing. All changes are stored in the RP2040's simulated EEPROM and persist across power cycles.

[Watch the LED configuration in action ↗](https://youtube.com/shorts/Vf_1ArsoVSY?si=YxogaUzM-TPjQ7zr)

---

## On-Device Configuration (Button Hold)

You can adjust basic LED color and brightness manually using the knob and physical buttons:

1. **Enter Config Mode**: With the device connected, hold both buttons for 6 seconds. The device will complete its normal 3-second calibration, then enter color configuration mode.
2. **Step 1 — Brightness**: The ring will breathe at the current color. Twist the knob to adjust brightness. Press the **right button to confirm/save** or the **left button to cancel**.
3. **Step 2 — Color**: The ring will breathe through the selected color. Twist the knob to cycle through the color wheel (Red → Yellow → Green → Cyan → Blue → Magenta → Red). Press the **right button to save** or the **left button to cancel**.

---

## Runtime Configuration (USB Serial)

Connect a serial terminal to the device's USB COM port at **115200 baud** to read and write parameters dynamically. 

### 1. LED Control Commands

| Command | Description |
| :--- | :--- |
| `led show` | Prints the current state: `brightness=N color=RRGGBB effect=NAME` |
| `led brightness <0-255>` | Sets the overall brightness level. |
| `led color <RRGGBB>` | Sets the idle color using a 6-digit hex code (e.g., `led color FF8800`). |
| `led effect <effect_name>` | Selects the active lighting animation. Supported names:<br>• `solid`: Static color.<br>• `breathing`: Pulse configured color.<br>• `reactive`: Brightens on motion, fades to black when idle.<br>• `dot_swirl`: Single moving dot.<br>• `gradient_swirl`: Orbiting tail gradient.<br>• `rainbow_swirl`: Rotating full-spectrum rainbow.<br>• `volume`: Visualizes system volume. |
| `led reset` | Restores default LED settings (brightness = 128, color = FF2400, effect = breathing). |

### 2. Sensitivity & Kalman Filter Commands

| Command | Description |
| :--- | :--- |
| `sens get` | Dumps current sensor configuration values as a JSON string. |
| `sens set <parameter> <value>` | Sets a sensitivity parameter (updates in real-time). Parameters:<br>• `dead_t`: Translation deadzone threshold.<br>• `dead_r`: Rotation deadzone threshold.<br>• `kalman_q`: Kalman process noise (higher = more responsive, lower = smoother).<br>• `kalman_r`: Kalman measurement noise (higher = smoother, lower = less latency).<br>• `exp`: Sensitivity power curve exponent (1.0 = linear, 3.0 = cubic). |
| `sens reset` | Restores default calibration/sensitivity variables to firmware defaults. |

### 3. System Configuration Commands

| Command | Description |
| :--- | :--- |
| `config get` | Dumps all LED and Sensitivity configurations as a combined JSON object. |
| `config reset` | Restores LED configuration to defaults and saves. |

### 4. Telemetry & Host Synchronization Commands

| Command | Description |
| :--- | :--- |
| `debug axes on` | Enters axis debug mode, streaming raw XYZ translation vectors over serial at 100Hz: `AX:Tx,Ty,Tz` (useful for calibrating tap thresholds). |
| `debug axes off` | Disables the axis telemetry stream. |
| `volume <0-100>` | Sets the current system volume level. Used by the `volume` LED effect to light up the corresponding fraction of the 8-LED ring. |
