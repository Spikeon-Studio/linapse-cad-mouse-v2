"""Virtual gamepad backend for Controller mode.

One analog left stick (driven by device tilt) + 2 buttons. The OS-level virtual
device is created lazily on first use so importing this module is free when
Controller mode is never selected.

Backends:
  Linux   -> python-evdev UInput (needs read/write on /dev/uinput)
  Windows -> vgamepad (needs the ViGEmBus driver installed)
  macOS   -> no-op (no supported virtual-gamepad API)

# ponytail: single hardcoded layout (left stick + 2 buttons). Add right stick,
# triggers, or a d-pad only when a mode actually needs them.
"""
import sys
import threading


def _clampf(v):
    return -1.0 if v < -1.0 else (1.0 if v > 1.0 else v)


class _NullPad:
    available = False

    def set_left_stick(self, x, y): pass
    def press(self, idx): pass
    def release(self, idx): pass
    def reset(self): pass
    def close(self): pass


class _LinuxPad:
    def __init__(self):
        from evdev import UInput, ecodes, AbsInfo
        self._ec = ecodes
        self._btn = [ecodes.BTN_SOUTH, ecodes.BTN_EAST]
        abs_info = AbsInfo(value=0, min=-32767, max=32767, fuzz=0, flat=0, resolution=0)
        cap = {
            ecodes.EV_KEY: list(self._btn),
            ecodes.EV_ABS: [(ecodes.ABS_X, abs_info), (ecodes.ABS_Y, abs_info)],
        }
        self._ui = UInput(cap, name="Linapse CAD Mouse Controller", vendor=0x2886)
        self.available = True

    def set_left_stick(self, x, y):
        ec = self._ec
        self._ui.write(ec.EV_ABS, ec.ABS_X, int(_clampf(x) * 32767))
        self._ui.write(ec.EV_ABS, ec.ABS_Y, int(_clampf(y) * 32767))
        self._ui.syn()

    def press(self, idx):
        self._ui.write(self._ec.EV_KEY, self._btn[idx], 1)
        self._ui.syn()

    def release(self, idx):
        self._ui.write(self._ec.EV_KEY, self._btn[idx], 0)
        self._ui.syn()

    def reset(self):
        self.set_left_stick(0.0, 0.0)

    def close(self):
        self._ui.close()


class _WindowsPad:
    def __init__(self):
        import vgamepad as vg
        self._pad = vg.VX360Gamepad()
        self._btn = [vg.XUSB_BUTTON.XUSB_GAMEPAD_A, vg.XUSB_BUTTON.XUSB_GAMEPAD_B]
        self.available = True

    def set_left_stick(self, x, y):
        self._pad.left_joystick_float(x_value_float=_clampf(x), y_value_float=_clampf(y))
        self._pad.update()

    def press(self, idx):
        self._pad.press_button(button=self._btn[idx])
        self._pad.update()

    def release(self, idx):
        self._pad.release_button(button=self._btn[idx])
        self._pad.update()

    def reset(self):
        self._pad.reset()
        self._pad.update()

    def close(self):
        # Dropping the ref lets vgamepad remove the ViGEm target on GC.
        try:
            self.reset()
        except Exception:
            pass
        self._pad = None
        self.available = False


_pad = None
_lock = threading.Lock()


def get_pad():
    global _pad
    if _pad is not None:
        return _pad
    with _lock:
        if _pad is not None:
            return _pad
        try:
            if sys.platform.startswith("linux"):
                _pad = _LinuxPad()
            elif sys.platform == "win32":
                _pad = _WindowsPad()
            else:
                print("[gamepad] no virtual-gamepad backend for this platform; Controller mode inert")
                _pad = _NullPad()
        except Exception as e:
            print(f"[gamepad] init failed ({e}); Controller mode inert. "
                  "Linux: pip install evdev + access to /dev/uinput; "
                  "Windows: pip install vgamepad + ViGEmBus driver")
            _pad = _NullPad()
    return _pad


def destroy():
    """Tear down the OS-level virtual gamepad. Called when leaving gamepad-using
    modes so no joystick device lingers — games otherwise keep seeing a phantom
    controller and flip their input scheme (keyboard prompts/latency)."""
    global _pad
    with _lock:
        pad, _pad = _pad, None
    if pad is None:
        return
    try:
        pad.reset()
    except Exception:
        pass
    try:
        pad.close()
    except Exception as e:
        print(f"[gamepad] close error: {e}")


def mode_uses_gamepad(actions, mode_name):
    """True if a mode drives the virtual pad: the built-in Controller mode
    (tilt -> stick) or any button/tap bound to a gamepad_button action."""
    if mode_name == "Controller":
        return True
    mode = ((actions or {}).get("modes") or {}).get(mode_name) or {}
    for category in ("buttons", "taps"):
        for act in (mode.get(category) or {}).values():
            if isinstance(act, dict) and act.get("action") == "gamepad_button":
                return True
    return False


_desired_pad = None  # latest requested state: True = pad wanted, False = not
_sync_lock = threading.Lock()


def _apply_desired_pad():
    # Serialized so rapid mode flips converge on the latest request instead of
    # interleaving create/destroy.
    with _sync_lock:
        want = _desired_pad
        if want is None:
            return
        if want:
            get_pad()
        else:
            destroy()


def sync_mode(actions, mode_name):
    """Create the virtual pad on entering a mode that uses it (so games see the
    controller immediately, not on first motion) and destroy it on leaving, so
    the joystick device only exists while a gamepad mode is active.

    Runs asynchronously: uinput device creation takes ~100ms and callers sit on
    latency-sensitive paths (mode-switch chord timer). Returns the worker
    thread so tests can join it."""
    global _desired_pad
    _desired_pad = mode_uses_gamepad(actions, mode_name)
    t = threading.Thread(target=_apply_desired_pad, daemon=True)
    t.start()
    return t


def set_left_stick(x, y):
    try:
        get_pad().set_left_stick(x, y)
    except Exception as e:
        print(f"[gamepad] stick error: {e}")


def press_button(idx):
    try:
        get_pad().press(idx)
    except Exception as e:
        print(f"[gamepad] button {idx} press error: {e}")


def release_button(idx):
    # Never instantiate a pad just to release a button on it — releasing on a
    # nonexistent pad is a no-op. The startup hold-release sweep in hid.py
    # dispatches releases for every configured gamepad_button; creating a pad
    # here would register a phantom controller (and repeatedly churn uinput
    # device creation after every destroy()).
    pad = _pad
    if pad is None:
        return
    try:
        pad.release(idx)
    except Exception as e:
        print(f"[gamepad] button {idx} release error: {e}")


def pulse_button(idx, ms=60):
    """Press then release a button — a device tap maps to a momentary press."""
    pad = get_pad()
    try:
        pad.press(idx)
    except Exception as e:
        print(f"[gamepad] button {idx} press error: {e}")
        return
    threading.Timer(ms / 1000.0, lambda: _safe_release(pad, idx)).start()


def _safe_release(pad, idx):
    try:
        pad.release(idx)
    except Exception as e:
        print(f"[gamepad] button {idx} release error: {e}")


def reset():
    if _pad is not None:
        try:
            _pad.reset()
        except Exception:
            pass


def tilt_to_stick(rx, ry, axis_range, deadzone):
    """Map raw tilt (rx, ry) to a normalized left-stick (sx, sy) in [-1, 1].

    Returns the stick as (x, y) where x follows ry (left/right tilt) and y
    follows rx (forward/back tilt) — same axes Mouse mode uses for the cursor.
    Values under the deadzone collapse to 0. Pure function, no side effects.
    """
    if axis_range <= 0:
        axis_range = 350.0

    def norm(v):
        n = _clampf(v / axis_range)
        if abs(n) < deadzone:
            return 0.0
        return n

    return norm(ry), norm(rx)
