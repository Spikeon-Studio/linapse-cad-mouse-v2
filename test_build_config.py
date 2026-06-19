from SCons.Script import DefaultEnvironment
import sys

env = DefaultEnvironment()

is_test = False
for arg in sys.argv:
    if "test" in arg:
        is_test = True
        break

if is_test:
    print("Applying test configuration for seeed_xiao_rp2040...")
    # Prepend to CCFLAGS to ensure mock directories are searched first by the compiler
    env.Prepend(CCFLAGS=[
        "-iquote", env.subst("$PROJECT_DIR/firmware/test/mocks"),
        "-I", env.subst("$PROJECT_DIR/firmware/test/mocks"),
        "-iquote", env.subst("$PROJECT_DIR/firmware/test/mocks/controllers"),
        "-I", env.subst("$PROJECT_DIR/firmware/test/mocks/controllers")
    ])
    # Apply source filtering
    env.Replace(SRC_FILTER=[
        "-<*>",
        "+<controllers/MotionController.cpp>",
        "+<controllers/TapDetector.cpp>",
        "+<controllers/EffectEngine.cpp>",
        "+<controllers/LEDController.cpp>",
        "+<StateMachine.cpp>",
        "+<LedConfig.cpp>",
        "+<SensConfig.cpp>",
        "+<states/CalibratingState.cpp>",
        "+<states/ColorConfigState.cpp>",
        "+<states/IdleState.cpp>",
        "+<states/SleepState.cpp>"
    ])
