"""Controller-mode checks: tilt->stick mapping + gamepad backend safety.

Pure mapping math is verified directly; the OS-level backend is exercised only
to confirm it degrades to a harmless no-op when no virtual-gamepad device can be
created (the normal case in CI).
"""
from linapse import gamepad


def test_center_is_zero():
    assert gamepad.tilt_to_stick(0.0, 0.0, 350.0, 0.08) == (0.0, 0.0)


def test_axis_mapping_x_follows_ry_y_follows_rx():
    # ry only -> stick x deflects, y stays 0
    sx, sy = gamepad.tilt_to_stick(0.0, 350.0, 350.0, 0.0)
    assert sx == 1.0 and sy == 0.0
    # rx only -> stick y deflects, x stays 0
    sx, sy = gamepad.tilt_to_stick(350.0, 0.0, 350.0, 0.0)
    assert sx == 0.0 and sy == 1.0


def test_clamps_beyond_full_deflection():
    sx, sy = gamepad.tilt_to_stick(-700.0, 700.0, 350.0, 0.0)
    assert sx == 1.0 and sy == -1.0


def test_deadzone_collapses_small_tilt():
    # 10/350 = 0.0286, under an 0.08 deadzone -> 0
    sx, sy = gamepad.tilt_to_stick(10.0, 10.0, 350.0, 0.08)
    assert sx == 0.0 and sy == 0.0


def test_bad_range_falls_back_to_350():
    sx, _ = gamepad.tilt_to_stick(0.0, 350.0, 0.0, 0.0)
    assert sx == 1.0


def test_backend_is_safe_without_device():
    # Must never raise even if no uinput/vgamepad is available.
    gamepad.set_left_stick(0.5, -0.5)
    gamepad.pulse_button(0, ms=1)
    gamepad.reset()


def _actions(mode, mode_cfg=None):
    return {"current_mode": mode, "modes": {mode: mode_cfg or {}, "Default": {}}}


def test_mode_uses_gamepad_builtin_controller():
    assert gamepad.mode_uses_gamepad(_actions("Controller"), "Controller")


def test_mode_uses_gamepad_custom_binding():
    cfg = {"buttons": {"0": {"action": "gamepad_button", "button": 0}}}
    assert gamepad.mode_uses_gamepad(_actions("Racing", cfg), "Racing")
    cfg = {"taps": {"PosZ:1": {"action": "gamepad_button", "button": 1}}}
    assert gamepad.mode_uses_gamepad(_actions("Racing", cfg), "Racing")


def test_mode_without_gamepad_bindings_does_not_use_pad():
    cfg = {"buttons": {"0": {"action": "key", "value": "space"}}}
    assert not gamepad.mode_uses_gamepad(_actions("Default", cfg), "Default")
    assert not gamepad.mode_uses_gamepad(None, None)


def test_sync_mode_destroys_pad_outside_gamepad_modes():
    # Entering Controller mode instantiates a pad (NullPad in CI); leaving it
    # must drop the pad so no joystick device lingers for games to latch onto.
    # sync_mode is async (pad creation is slow); join the worker before asserting.
    gamepad.sync_mode(_actions("Controller"), "Controller").join(5)
    assert gamepad._pad is not None
    gamepad.sync_mode(_actions("Default"), "Default").join(5)
    assert gamepad._pad is None


def test_destroy_is_idempotent_and_safe():
    gamepad.destroy()
    gamepad.destroy()
    # Lazy creation still works after a destroy.
    gamepad.set_left_stick(0.0, 0.0)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
    print("all passed")
