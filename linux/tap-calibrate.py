#!/usr/bin/env python3
"""
CAD Mouse MK2 — tap calibration recorder.

Streams raw TX/TY/TZ axis values from the firmware's debug mode,
records taps for each direction, and suggests Config.h thresholds.

Usage:
    python3 tap-calibrate.py [/dev/ttyACM0]
    python3 tap-calibrate.py --monitor    # just watch live TAP events

Requirements: pyserial  (pip install pyserial)
"""

import sys
import time
import serial
import glob
import statistics
import threading
import argparse
from collections import defaultdict

BAUD = 115200


def find_port():
    candidates = (
        glob.glob("/dev/serial/by-id/usb-Seeed_Studio_CAD_Mouse*") +
        glob.glob("/dev/ttyACM*")
    )
    if candidates:
        return candidates[0]
    return None


# ── colours ───────────────────────────────────────────────────────────────────

RESET = "\033[0m"
BOLD  = "\033[1m"
GREEN = "\033[32m"
CYAN  = "\033[36m"
YELLOW= "\033[33m"
RED   = "\033[31m"


def hdr(s):  return f"{BOLD}{CYAN}{s}{RESET}"
def ok(s):   return f"{GREEN}{s}{RESET}"
def warn(s): return f"{YELLOW}{s}{RESET}"


# ── serial helpers ────────────────────────────────────────────────────────────

def send(ser, cmd):
    ser.write((cmd + "\n").encode())
    ser.flush()
    time.sleep(0.05)


def drain(ser, timeout=0.3):
    """Read and discard buffered output for `timeout` seconds."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ser.read(ser.in_waiting or 1)


# ── monitor mode ──────────────────────────────────────────────────────────────

def run_monitor(ser):
    print(hdr("\n=== Live TAP monitor — press Ctrl-C to exit ===\n"))
    print("Tap the mouse head and watch events appear.\n")
    try:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            if line.startswith("TAP:"):
                parts = line.split(":")
                if len(parts) == 3:
                    _, direction, count = parts
                    bar = "█" * int(count)
                    print(f"  {ok(direction):12s}  count={count}  {bar}")
            # suppress telemetry (>X:) and AX debug lines — only show TAP events
    except KeyboardInterrupt:
        print("\nDone.")


# ── calibration session ───────────────────────────────────────────────────────

DIRECTIONS = [
    ("PosX",  "RIGHT  — tap the right side of the head"),
    ("NegX",  "LEFT   — tap the left side of the head"),
    ("PosY",  "FORWARD — tap the front of the head"),
    ("NegY",  "BACK   — tap the back of the head"),
    ("PosZ",  "TOP    — press down on the top of the head"),
]

RECORD_SECS   = 4      # recording window per direction
SAMPLE_HZ     = 60     # approximate firmware output rate in debug mode
MIN_TAPS      = 3      # minimum taps per direction for reliable statistics


def record_direction(ser, label, description):
    """
    Collect RECORD_SECS of raw AX lines.
    Returns list of (tx, ty, tz) tuples.
    """
    print(f"\n  {hdr(label)} — {description}")
    input("  Press Enter then immediately tap 4–5 times...")

    samples = []
    deadline = time.time() + RECORD_SECS
    while time.time() < deadline:
        line = ser.readline().decode(errors="replace").strip()
        if line.startswith("AX:"):
            try:
                vals = [float(v) for v in line[3:].split(",")]
                if len(vals) == 3:
                    samples.append(tuple(vals))
            except ValueError:
                pass

    print(f"  Captured {len(samples)} samples over {RECORD_SECS}s")
    return samples


def compute_deltas(samples):
    """Compute per-frame velocity (delta) for each axis."""
    deltas = []
    for i in range(1, len(samples)):
        dx = abs(samples[i][0] - samples[i-1][0])
        dy = abs(samples[i][1] - samples[i-1][1])
        dz = abs(samples[i][2] - samples[i-1][2])
        deltas.append((dx, dy, dz))
    return deltas


def analyse(label, samples):
    """
    Find peak velocity, dominant axis, and return stats dict.
    """
    if len(samples) < 10:
        print(f"  {warn('Too few samples — skipping')}")
        return None

    deltas = compute_deltas(samples)

    # Find top-N peaks (simple: sort by max-of-3)
    peaks = sorted(deltas, key=lambda d: max(d), reverse=True)

    # Report top-5 frames
    print(f"\n  Top velocity frames:")
    for i, (dx, dy, dz) in enumerate(peaks[:5]):
        dominant = ["TX", "TY", "TZ"][([dx, dy, dz].index(max(dx, dy, dz)))]
        print(f"    #{i+1}  TX={dx:6.1f}  TY={dy:6.1f}  TZ={dz:6.1f}  → {dominant}")

    peak_vals = [max(d) for d in peaks[:20]]  # top 20 for stats
    p50 = statistics.median(peak_vals) if peak_vals else 0
    p_max = max(peak_vals) if peak_vals else 0

    # Axis breakdown of the single biggest spike
    top = peaks[0]
    axis_names = ["TX", "TY", "TZ"]
    dominant_idx = [top[0], top[1], top[2]].index(max(top))
    dominant = axis_names[dominant_idx]

    return {
        "label": label,
        "dominant_axis": dominant,
        "peak_max": p_max,
        "peak_median": p50,
        "n_samples": len(samples),
    }


def suggest_threshold(results):
    """
    Look at all peak_median values across directions and suggest a threshold
    that's above typical noise but below real taps.
    We want threshold < smallest tap peak, > baseline noise.
    """
    medians = [r["peak_median"] for r in results if r]
    if not medians:
        return 60.0
    # Use 50% of the minimum observed tap peak as threshold
    suggested = min(medians) * 0.5
    # Clamp to reasonable range
    return max(20.0, min(suggested, 200.0))


def run_calibration(ser):
    print(hdr("\n=== TAP CALIBRATION ===\n"))
    print("This will record taps for each direction and suggest Config.h values.\n")
    print("Instructions:")
    print("  • Tap firmly on the HEAD (rigid part, not the base/neck)")
    print("  • Multiple taps per prompt — 4–5 is ideal")
    print("  • Rest the mouse on the desk between taps")
    print()

    send(ser, "debug axes on")
    drain(ser, 0.2)

    results = []
    for label, description in DIRECTIONS:
        samples = record_direction(ser, label, description)
        result = analyse(label, samples)
        results.append(result)

    send(ser, "debug axes off")
    drain(ser, 0.2)

    # ── Summary ────────────────────────────────────────────────────────────────

    print("\n" + "─" * 60)
    print(hdr("RESULTS"))
    print("─" * 60)
    print(f"{'Direction':<12}  {'Dominant axis':<14}  {'Peak max':>10}  {'Peak median':>12}")
    print("─" * 60)
    for r in results:
        if r:
            print(f"  {r['label']:<10}  {r['dominant_axis']:<14}  {r['peak_max']:>10.1f}  {r['peak_median']:>12.1f}")

    threshold = suggest_threshold(results)

    print("\n" + hdr("SUGGESTED Config.h VALUES:"))
    print()
    print(f"  const float TAP_VELOCITY_THRESHOLD = {threshold:.0f}f;")
    print()
    print("  (Current value in Config.h is shown for comparison — update if significantly different)")
    print()

    # Axis direction hints
    print(hdr("DIRECTION MAPPING (based on dominant axis):"))
    print()
    for r in results:
        if r:
            print(f"  {r['label']:6s} → {r['dominant_axis']}")
    print()
    print("If PosX and NegX both map to TX but you want left vs right distinguished,")
    print("the sign of the delta determines direction (firmware already handles this).")
    print()

    # Offer to write values
    ans = input("Write suggested threshold to Config.h? [y/N] ").strip().lower()
    if ans == "y":
        config_path = "firmware/include/Config.h"
        try:
            with open(config_path) as f:
                text = f.read()
            # Replace the threshold line
            import re
            new_line = f"const float TAP_VELOCITY_THRESHOLD = {threshold:.0f}f;"
            text = re.sub(r"const float TAP_VELOCITY_THRESHOLD\s*=\s*[\d.]+f;", new_line, text)
            with open(config_path, "w") as f:
                f.write(text)
            print(ok(f"Updated {config_path}"))
        except Exception as e:
            print(warn(f"Could not update Config.h: {e}"))
            print("Update manually.")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CAD Mouse MK2 tap calibration")
    parser.add_argument("port", nargs="?", help="Serial port (auto-detected if omitted)")
    parser.add_argument("--monitor", action="store_true", help="Monitor TAP events only")
    args = parser.parse_args()

    port = args.port or find_port()
    if not port:
        print(RED + "ERROR: No serial port found. Plug in the mouse or specify port." + RESET)
        sys.exit(1)

    print(f"Opening {port} at {BAUD} baud...")
    try:
        ser = serial.Serial(port, BAUD, timeout=0.1)
    except serial.SerialException as e:
        print(RED + f"ERROR: {e}" + RESET)
        print()
        print("If linapse-service has the port open, stop it first:")
        print("  systemctl --user stop linapse-service")
        sys.exit(1)

    time.sleep(0.5)  # let firmware settle
    drain(ser, 0.3)

    if args.monitor:
        run_monitor(ser)
    else:
        try:
            run_calibration(ser)
        except KeyboardInterrupt:
            send(ser, "debug axes off")
            print("\nAborted.")
    ser.close()


if __name__ == "__main__":
    main()
