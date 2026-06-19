# Firmware Testing & Mocking Infrastructure

This document describes the native testing environment and mocking infrastructure configured for the Linapse CAD Mouse MK2 firmware.

## Architecture

To verify firmware logic (such as the State Machine, configurations, LED controllers, motion algorithms, and tap detection) without physical RP2040 hardware, a `native` environment has been added to PlatformIO.

This environment runs tests on the host machine using standard gcc/g++ compilers.

### Source Filtering

Because hardware-bound controllers (`SensorController`, `InputController`, `HIDController`, `TelemetryController`) depend on physical libraries like `Wire` or USB hardware, they are excluded from native compilation. 

The native test environment selectively compiles the hardware-independent core logic:
- `StateMachine.cpp` (FSM)
- `LedConfig.cpp` & `SensConfig.cpp` (Settings storage and parsing)
- `controllers/MotionController.cpp` (Kalman filtering and geometric decomposition)
- `controllers/TapDetector.cpp` (Impulse gesture classification)
- `controllers/EffectEngine.cpp` (LED lighting math)
- `controllers/LEDController.cpp` (LED color routing)
- `states/*.cpp` (Idle, Sleep, Calibrating, ColorConfig states)

### Mock Headers

To satisfy dependencies, a set of high-fidelity mocks is located in `firmware/test/mocks/`:

1. **`Arduino.h`**: Defines basic types (`byte`, `boolean`), pin definitions, time/delay utilities (`millis()`, `delay()`), serial interface (`Serial` stub), and a helper `String` class wrapping `std::string`.
2. **`EEPROM.h`**: Emulates persistent storage with a RAM-backed `eeprom_data` array to support configuration loading/saving.
3. **`Adafruit_NeoPixel.h`**: Emulates the RGB LED ring by capturing colors/brightness in memory for assertion.
4. **`controllers/*.h`**: Stub class interfaces for hardware-bound controllers that capture state and publish/receive events.

---

## Running Tests

To build and run tests natively on your host machine:

```bash
pio test -e native
```

Tests are located under the `firmware/test/` directory. Each test subdirectory can contain test scripts using the Unity testing framework.
