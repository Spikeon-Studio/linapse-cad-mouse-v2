#pragma once

#include <Arduino.h>

enum class TapDir : uint8_t {
  None    = 0,
  PosX    = 1,  // right
  NegX    = 2,  // left
  PosY    = 3,  // forward
  NegY    = 4,  // back
  PosZ    = 5,  // top press (down)
  NegZ    = 6,  // upward
};

struct TapEvent {
  TapDir  dir;
  uint8_t count;  // 1–4
};

class TapDetector {
 public:
  void reset();
  // Call once per sensor frame from idle/color-config state.
  void update(const float raw[9], const float* baseline, unsigned long now);

  bool     hasTap() const;
  TapEvent takeTap();
  bool     isTapping() const { return suppressMotion_; }

 private:
  enum class Phase { Idle, Rising, Falling, Cooldown };

  Phase         phase_      = Phase::Idle;
  TapDir        riseDir_    = TapDir::None;
  unsigned long phaseMs_    = 0;

  float prevAxes_[6] = {};
  bool  prevValid_   = false;

  // Multi-tap accumulator
  TapDir        multiDir_   = TapDir::None;
  uint8_t       tapCount_   = 0;
  unsigned long lastTapMs_  = 0;

  bool     pending_     = false;
  TapEvent pendingEvt_  = {};

  void emitTap(TapDir dir, unsigned long now);
  void flushMulti(unsigned long now);
  static TapDir dirFromAxes(const float axes[6], const float prev[6]);
  static bool   isOpposite(TapDir a, TapDir b);

  TapDir        lastConfirmedDir_ = TapDir::None;
  unsigned long lastConfirmedMs_  = 0;
  bool          suppressMotion_   = false;
};
