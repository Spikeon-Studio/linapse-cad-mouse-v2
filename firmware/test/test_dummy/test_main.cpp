#include <unity.h>
#include <Arduino.h>
#include "Controllers.h"

// Define the external instances required by the linker
InputController     inputController;
LEDController       ledController;
SensorController    sensorController;
MotionController    motionController;
HIDController       hidController;
TelemetryController telemetryController;
TapDetector         tapDetector;
EffectEngine        effectEngine;

// Define global variables required by the linker
bool g_debugAxes = false;
int g_currentVolume = 50;

void setUp(void) {}
void tearDown(void) {}

void test_dummy(void) {
    TEST_ASSERT_EQUAL(1, 1);
}

int main(int argc, char **argv) {
    UNITY_BEGIN();
    RUN_TEST(test_dummy);
    return UNITY_END();
}
