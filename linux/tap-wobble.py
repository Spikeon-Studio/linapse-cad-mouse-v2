#!/usr/bin/env python3
"""
CAD Mouse MK2 — tap wobble recorder.

Captures the full waveform of a tap + spring oscillation to tune:
  - TAP_COOLDOWN_MS   (how long to ignore after tap)
  - TAP_RETURN_ZONE   (what amplitude counts as "settled")
  - TAP_VELOCITY_THRESHOLD (delta between frames to count as tap)

Usage:
    sudo python3 linux/tap-wobble.py [/dev/ttyACM0]

Press Enter to arm, then tap once. The script captures the waveform,
plots it in-terminal, and reports settling time at various thresholds.

Requirements: pyserial
"""

import sys
import time
import glob
import serial
import argparse

BAUD        = 115200
CAPTURE_MS  = 2500   # record 2.5s after trigger (should cover any wobble)
NOISE_FLOOR = 5.0    # below this = settled

RESET  = "\033[0m"
BOLD   = "\033[1m"
GREEN  = "\033[32m"
CYAN   = "\033[36m"
YELLOW = "\033[33m"
RED    = "\033[31m"
DIM    = "\033[2m"


def find_port():
    candidates = (
        glob.glob("/dev/serial/by-id/usb-Seeed_Studio_CAD_Mouse*") +
        glob.glob("/dev/ttyACM*")
    )
    return candidates[0] if candidates else None


def send(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(0.05)


def drain(ser, timeout=0.3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ser.read(ser.in_waiting or 1)


def read_ax(ser):
    """Read one AX line, return (tx, ty, tz) or None."""
    line = ser.readline().decode(errors="replace").strip()
    if line.startswith("AX:"):
        try:
            vals = [float(v) for v in line[3:].split(",")]
            if len(vals) == 3:
                return tuple(vals)
        except ValueError:
            pass
    return None


# ── capture ───────────────────────────────────────────────────────────────────

def wait_for_trigger(ser, threshold=20.0):
    """
    Block until a velocity spike exceeds `threshold` on any axis.
    Shows live velocity so user can see data is flowing.
    Returns the triggering sample and the timestamp.
    """
    prev = None
    last_print = time.time()
    no_data_count = 0
    sample_count = 0
    max_vel_seen = 0.0

    print("  Live velocity (tap when ready):")
    print("  " + "-" * 50)

    while True:
        line = ser.readline().decode(errors="replace").strip()

        # Show unexpected non-AX, non-telemetry lines (telemetry starts with '>')
        if line and not line.startswith("AX:") and not line.startswith(">"):
            print(f"  {DIM}[raw] {line}{RESET}")

        if line.startswith("AX:"):
            try:
                vals = [float(v) for v in line[3:].split(",")]
                if len(vals) == 3:
                    sample = tuple(vals)
                    sample_count += 1
                    if prev is not None:
                        delta = max(abs(sample[i] - prev[i]) for i in range(3))
                        max_vel_seen = max(max_vel_seen, delta)
                        # Print live update every ~200ms
                        now = time.time()
                        if now - last_print >= 0.2:
                            bar_len = min(40, int(delta / threshold * 20))
                            bar_col = RED if delta >= threshold else (YELLOW if delta > threshold * 0.3 else GREEN)
                            bar = bar_col + "█" * bar_len + RESET
                            print(f"\r  vel={delta:6.1f}  max={max_vel_seen:6.1f}  [{bar:<40}]  ", end="", flush=True)
                            last_print = now
                        if delta >= threshold:
                            print()  # newline after live display
                            return sample, time.time()
                    prev = sample
                    no_data_count = 0
            except ValueError:
                pass
        else:
            no_data_count += 1
            if no_data_count == 50:
                print(f"\n  {YELLOW}WARNING: No AX data received yet. Is firmware in IdleState?{RESET}")
                print(f"  {DIM}Try: open a serial terminal and type 'debug axes on' manually{RESET}")
            elif no_data_count % 100 == 0 and no_data_count > 0:
                print(f"  {DIM}Still waiting for AX data... ({no_data_count} non-AX lines){RESET}")


def capture_waveform(ser, trigger_time, duration_ms):
    """Record raw AX samples for `duration_ms` ms after trigger_time."""
    samples = []   # list of (elapsed_ms, tx, ty, tz)
    deadline = trigger_time + duration_ms / 1000.0
    while time.time() < deadline:
        sample = read_ax(ser)
        if sample is not None:
            elapsed = (time.time() - trigger_time) * 1000.0
            samples.append((elapsed, *sample))
    return samples


# ── analysis ──────────────────────────────────────────────────────────────────

def velocity_series(samples):
    """Compute per-frame max-abs-delta, aligned to sample[1:]."""
    vels = []
    for i in range(1, len(samples)):
        prev = samples[i - 1]
        curr = samples[i]
        d = max(abs(curr[j + 1] - prev[j + 1]) for j in range(3))
        vels.append((curr[0], d))   # (elapsed_ms, velocity)
    return vels


def settling_time(vels, threshold):
    """
    Return the elapsed_ms of the last frame where velocity >= threshold.
    This is how long we need to ignore the axis after a tap.
    Returns 0 if never exceeded (tap wasn't detected at this threshold).
    """
    last = 0.0
    for ms, v in vels:
        if v >= threshold:
            last = ms
    return last


# ── terminal sparkline ────────────────────────────────────────────────────────

SPARKLINE_WIDTH = 72   # columns
SPARKLINE_HEIGHT = 12  # rows


def sparkline(vels, threshold, max_val=None):
    if not vels:
        return "(no data)"

    times = [v[0] for v in vels]
    values = [v[1] for v in vels]
    max_v = max_val or max(values) or 1.0
    total_ms = times[-1] if times else 1.0

    # Bucket into SPARKLINE_WIDTH columns
    buckets = [0.0] * SPARKLINE_WIDTH
    counts  = [0]   * SPARKLINE_WIDTH
    for ms, v in vels:
        col = int(ms / total_ms * (SPARKLINE_WIDTH - 1))
        col = min(col, SPARKLINE_WIDTH - 1)
        buckets[col] = max(buckets[col], v)
        counts[col]  += 1

    # Draw rows top to bottom
    rows = []
    for row in range(SPARKLINE_HEIGHT, 0, -1):
        row_thresh = max_v * row / SPARKLINE_HEIGHT
        line = ""
        for col in range(SPARKLINE_WIDTH):
            v = buckets[col]
            if v >= row_thresh:
                # colour: above detection threshold = red/yellow, below = green
                if v >= threshold:
                    line += f"\033[31m█\033[0m"
                else:
                    line += f"\033[32m▒\033[0m"
            else:
                line += DIM + "·" + RESET
        label = f"{row_thresh:6.0f} |"
        rows.append(label + line)

    # X-axis labels
    rows.append("       " + "-" * SPARKLINE_WIDTH)
    rows.append("       0ms" + " " * (SPARKLINE_WIDTH - 18) + f"{total_ms:.0f}ms")

    return "\n".join(rows)


# ── main ──────────────────────────────────────────────────────────────────────

def run(ser, trigger_threshold):
    print(f"\n{BOLD}{CYAN}=== TAP WOBBLE RECORDER ==={RESET}\n")
    print("Measures spring oscillation after a single tap.")
    print(f"Trigger threshold: velocity ≥ {trigger_threshold:.0f}\n")
    print(f"  {YELLOW}Red/orange{RESET} bars = velocity ≥ threshold (firmware would re-trigger)")
    print(f"  {GREEN}Green{RESET} bars    = settling wobble below threshold\n")

    send(ser, "debug axes on")
    drain(ser, 0.2)

    for trial in range(1, 4):
        input(f"[Trial {trial}/3] Press Enter, then tap ONCE on the head...")
        print("  Listening for tap...", end="", flush=True)

        sample, t0 = wait_for_trigger(ser, trigger_threshold)
        print(f" {GREEN}TAP DETECTED{RESET} at t=0ms")

        samples = [(0.0, *sample)] + capture_waveform(ser, t0, CAPTURE_MS)
        print(f"  Captured {len(samples)} samples over {CAPTURE_MS}ms\n")

        vels = velocity_series(samples)

        # Settling times at various thresholds
        thresholds = [trigger_threshold, trigger_threshold * 0.5, NOISE_FLOOR]
        print(f"  {'Threshold':>12}  {'Settled after':>14}")
        print(f"  {'-'*12}  {'-'*14}")
        for t in thresholds:
            st = settling_time(vels, t)
            flag = ""
            if t == trigger_threshold and st > 100:
                flag = f"  {RED}← cooldown too short!{RESET}"
            print(f"  {t:>12.1f}  {st:>12.0f}ms{flag}")

        print()
        print(sparkline(vels, trigger_threshold))
        print()

    send(ser, "debug axes off")
    drain(ser, 0.2)

    print(f"\n{BOLD}Recommendation:{RESET}")
    print("  Set TAP_COOLDOWN_MS to the 'Settled after' time at your trigger threshold,")
    print("  rounded up to the nearest 50ms, plus 20ms safety margin.")
    print()
    print("  In firmware/src/controllers/TapDetector.cpp, change:")
    print("    if ((now - phaseMs_) > 80) {")
    print("  to:")
    print("    if ((now - phaseMs_) > <your value>) {")
    print()
    print("  Consider also adding a TAP_COOLDOWN_MS constant to Config.h.")


def main():
    parser = argparse.ArgumentParser(description="CAD Mouse MK2 tap wobble recorder")
    parser.add_argument("port", nargs="?")
    parser.add_argument("--threshold", type=float, default=5.0,
                        help="Velocity threshold for trigger detection (default: 5)")
    args = parser.parse_args()

    port = args.port or find_port()
    if not port:
        print(RED + "ERROR: No serial port found." + RESET)
        sys.exit(1)

    print(f"Opening {port} at {BAUD} baud...")
    try:
        ser = serial.Serial(port, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(RED + f"ERROR: {e}" + RESET)
        print("Stop linapse-service first:  systemctl --user stop linapse-service")
        sys.exit(1)

    time.sleep(0.5)
    drain(ser, 0.3)

    try:
        run(ser, args.threshold)
    except KeyboardInterrupt:
        send(ser, "debug axes off")
        print("\nAborted.")
    finally:
        ser.close()


if __name__ == "__main__":
    main()
