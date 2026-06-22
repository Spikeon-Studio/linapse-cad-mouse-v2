import sys
import time
import glob
import os
import select
import threading
from . import state
from .config import get_active_mode_config
from .emulation import dispatch

BUTTON_REPORT_ID = 3
CHORD_WINDOW = 0.05
SCROLL_INTERVAL = 0.05

class ButtonClickState:
    def __init__(self, btn):
        self.btn = btn
        self.click_count = 0
        self.timer = None
        self.released = False

_click_states = {0: ButtonClickState(0), 1: ButtonClickState(1)}
_held = set()
_chord_fired = False
_timers = {}
_scroll_threads = {}

def reset_click_states():
    for state_obj in _click_states.values():
        if state_obj.timer:
            state_obj.timer.cancel()
            state_obj.timer = None
        state_obj.click_count = 0
        state_obj.released = False

def _scroll_loop(btn, stop_event, actions):
    while not stop_event.is_set():
        mode_buttons = get_active_mode_config(actions, "buttons")
        act = mode_buttons.get(f"{btn}:1")
        if not act:
            act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
        dispatch(act)
        time.sleep(SCROLL_INTERVAL)

def _on_single(btn, actions):
    global _chord_fired
    if _chord_fired:
        return
    state.broadcast_from_thread(f"BUTTON:{btn}:1")
    if actions.get("button_override", False):
        return
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:1")
    if not act:
        act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
    if act.get("action") in ("scroll_up", "scroll_down"):
        stop_event = threading.Event()
        t = threading.Thread(target=_scroll_loop, args=(btn, stop_event, actions), daemon=True)
        _scroll_threads[btn] = (t, stop_event)
        t.start()
    else:
        dispatch(act)

def _on_chord(actions):
    state.broadcast_from_thread("BUTTON:chord:1")
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get("chord", {"action": "key", "value": "shift+7"})
    dispatch(act)

def _fire_multi_click(btn, count, actions):
    global _chord_fired
    if _chord_fired:
        return
    state.broadcast_from_thread(f"BUTTON:{btn}:{count}")
    if actions.get("button_override", False):
        return
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:{count}")
    if not act and count == 1:
        act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
    if act:
        dispatch(act)

def _on_press(btn, actions):
    global _chord_fired
    _held.add(btn)
    if len(_held) == 2:
        _chord_fired = True
        for t in _timers.values():
            t.cancel()
        _timers.clear()
        for state_obj in _click_states.values():
            if state_obj.timer:
                state_obj.timer.cancel()
                state_obj.timer = None
            state_obj.click_count = 0
        _on_chord(actions)
        return

    mode_buttons = get_active_mode_config(actions, "buttons")
    has_double = f"{btn}:2" in mode_buttons

    if has_double:
        state_obj = _click_states[btn]
        if state_obj.timer:
            state_obj.timer.cancel()
            state_obj.timer = None
            state_obj.click_count += 1
        else:
            state_obj.click_count = 1
        state_obj.released = False
    else:
        t = threading.Timer(CHORD_WINDOW, _on_single, args=[btn, actions])
        _timers[btn] = t
        t.start()

def _on_release(btn, actions=None):
    global _chord_fired
    _held.discard(btn)
    if btn in _timers:
        _timers.pop(btn).cancel()
    if btn in _scroll_threads:
        _, stop_event = _scroll_threads.pop(btn)
        stop_event.set()
    if not _held:
        _chord_fired = False

    if actions is None:
        actions = state.actions_ref[0] or {}

    state_obj = _click_states.get(btn)
    if state_obj and state_obj.click_count > 0 and not state_obj.released:
        state_obj.released = True
        def fire():
            _fire_multi_click(btn, state_obj.click_count, actions)
            state_obj.click_count = 0
            state_obj.timer = None
        state_obj.timer = threading.Timer(0.25, fire)
        state_obj.timer.start()

    state.broadcast_from_thread(f"BUTTON:{btn}:0")

def hid_thread(actions_ref):
    if sys.platform in ("win32", "darwin"):
        print("[hid] disabled on Windows/macOS")
        return
    while True:
        candidates = (
            glob.glob("/dev/input/by-id/usb-*CAD_Mouse*-if02-hidraw") +
            glob.glob("/dev/input/by-id/usb-Seeed_Studio*-if02-hidraw")
        )
        if not candidates:
            time.sleep(3)
            continue
        try:
            with open(candidates[0], "rb") as fd:
                os.set_blocking(fd.fileno(), False)
                prev_bits = 0
                print(f"[hid] watching {fd.name}")
                while True:
                    r, _, _ = select.select([fd], [], [], 1)
                    if not r:
                        continue
                    data = fd.read(64)
                    if not data:
                        raise OSError("no data (disconnected)")
                    if data[0] != BUTTON_REPORT_ID:
                        continue
                    bits = data[1] & 0x03
                    if bits == prev_bits:
                        continue
                    # In HID emulation mode the serial BUTTON path is the sole
                    # button source; ignore reports here (they are service-driven
                    # native echoes and would double-dispatch).
                    if bool((actions_ref[0] or {}).get("custom_usb", {}).get("enabled", False)):
                        prev_bits = bits
                        continue
                    for btn in range(2):
                        mask = 1 << btn
                        was = bool(prev_bits & mask)
                        now = bool(bits & mask)
                        if now and not was:
                            _on_press(btn, actions_ref[0])
                        elif was and not now:
                            _on_release(btn)
                    prev_bits = bits
        except (OSError, IOError) as e:
            print(f"[hid] error/disconnect: {e} — retrying in 3s")
            for btn in list(_held):
                _on_release(btn)
            time.sleep(3)
