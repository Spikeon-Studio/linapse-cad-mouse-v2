#include "controllers/TapDetector.h"
#include "controllers/MotionController.h"
#include "Config.h"
#include "SensConfig.h"
#include <math.h>

void TapDetector::reset() {
  phase_     = Phase::Idle;
  riseDir_   = TapDir::None;
  phaseMs_   = 0;
  prevValid_ = false;
  multiDir_  = TapDir::None;
  tapCount_  = 0;
  lastTapMs_ = 0;
  pending_          = false;
  lastConfirmedDir_ = TapDir::None;
  lastConfirmedMs_  = 0;
  suppressMotion_   = false;
}

void TapDetector::update(const float raw[9], const float* baseline, unsigned long now) {
  // Flush a completed multi-tap if the window has expired
  flushMulti(now);

  float axes[6];
  MotionController::geometricDecomp(raw, baseline, axes);

  if (sensConfig.invertTapZ) {
    axes[2] = -axes[2];
  }

  if (!prevValid_) {
    for (int i = 0; i < 6; i++) prevAxes_[i] = axes[i];
    prevValid_ = true;
    return;
  }

  switch (phase_) {
    case Phase::Idle: {
      // Look for a fast velocity spike on TX, TY, or TZ (translation only — taps on head)
      float maxVel = 0.0f;
      for (int i = 0; i < 3; i++) {  // TX=0, TY=1, TZ=2
        float vel = fabsf(axes[i] - prevAxes_[i]);
        if (vel > maxVel) maxVel = vel;
      }
      if (maxVel >= sensConfig.tapThreshold) {
        TapDir dir = dirFromAxes(axes, prevAxes_);
        // Suppress opposite-direction spring rebound (e.g. NegX tap → PosX rebound)
        if (lastConfirmedDir_ != TapDir::None &&
            isOpposite(dir, lastConfirmedDir_) &&
            (now - lastConfirmedMs_) < Config::TAP_REBOUND_MS) {
          phase_   = Phase::Cooldown;
          phaseMs_ = now;
        } else {
          riseDir_ = dir;
          phase_   = Phase::Rising;
          phaseMs_ = now;
        }
      }
      break;
    }

    case Phase::Rising: {
      // Wait for translation axes to return near zero (spring return)
      float mag = sqrtf(axes[0]*axes[0] + axes[1]*axes[1] + axes[2]*axes[2]);
      if (mag < Config::TAP_RETURN_ZONE) {
        // PosZ is physically impossible (can't tap from below) — suppress, enter cooldown
        if (riseDir_ != TapDir::PosZ) emitTap(riseDir_, now);
        phase_   = Phase::Cooldown;
        phaseMs_ = now;
      } else if ((now - phaseMs_) > Config::TAP_MAX_DURATION_MS) {
        // Took too long — intentional motion, not a tap
        phase_ = Phase::Idle;
      }
      break;
    }

    case Phase::Cooldown: {
      unsigned long elapsed = now - phaseMs_;
      if (elapsed >= Config::TAP_COOLDOWN_MAX_MS) {
        phase_ = Phase::Idle;
      } else if (elapsed >= Config::TAP_COOLDOWN_MIN_MS) {
        // Early exit once head settles — wobble amplitude and position both near zero
        float maxVel = 0.0f;
        for (int i = 0; i < 3; i++) {
          float vel = fabsf(axes[i] - prevAxes_[i]);
          if (vel > maxVel) maxVel = vel;
        }
        float mag = sqrtf(axes[0]*axes[0] + axes[1]*axes[1] + axes[2]*axes[2]);
        if (maxVel < Config::TAP_SETTLE_VELOCITY && mag < Config::TAP_RETURN_ZONE) {
          phase_ = Phase::Idle;
        }
      }
      break;
    }

    case Phase::Falling:
      break;
  }

  for (int i = 0; i < 6; i++) prevAxes_[i] = axes[i];

  suppressMotion_ = (phase_ != Phase::Idle) ||
                    (tapCount_ > 0) ||
                    (lastConfirmedMs_ > 0 && (now - lastConfirmedMs_) < Config::TAP_MULTI_WINDOW_MS + 300);
}

bool TapDetector::isOpposite(TapDir a, TapDir b) {
  return (a == TapDir::PosX && b == TapDir::NegX) ||
         (a == TapDir::NegX && b == TapDir::PosX) ||
         (a == TapDir::PosY && b == TapDir::NegY) ||
         (a == TapDir::NegY && b == TapDir::PosY) ||
         (a == TapDir::PosZ && b == TapDir::NegZ) ||
         (a == TapDir::NegZ && b == TapDir::PosZ);
}

void TapDetector::emitTap(TapDir dir, unsigned long now) {
  lastConfirmedDir_ = dir;
  lastConfirmedMs_  = now;
  if (tapCount_ > 0 && dir != multiDir_) {
    // Direction changed — flush previous multi-tap first
    if (!pending_) {
      pending_    = true;
      pendingEvt_ = {multiDir_, tapCount_};
    }
    tapCount_ = 0;
  }
  multiDir_  = dir;
  tapCount_++;
  lastTapMs_ = now;
}

void TapDetector::flushMulti(unsigned long now) {
  if (tapCount_ == 0) return;
  if ((now - lastTapMs_) >= Config::TAP_MULTI_WINDOW_MS) {
    if (!pending_) {
      pending_    = true;
      pendingEvt_ = {multiDir_, tapCount_};
    }
    tapCount_ = 0;
    multiDir_ = TapDir::None;
  }
}

bool TapDetector::hasTap() const { return pending_; }

TapEvent TapDetector::takeTap() {
  pending_ = false;
  return pendingEvt_;
}

TapDir TapDetector::dirFromAxes(const float axes[6], const float prev[6]) {
  float vel[3];
  for (int i = 0; i < 3; i++) vel[i] = fabsf(axes[i] - prev[i]);

  int maxIdx = 0;
  for (int i = 1; i < 3; i++) if (vel[i] > vel[maxIdx]) maxIdx = i;

  // If X or Y wins but Z is competitive (within 1.5×), prefer Z —
  // top-surface edge taps produce diagonal vectors but intent is Z.
  if (maxIdx != 2 && vel[2] > 0.0f && vel[maxIdx] < vel[2] * 2.0f) maxIdx = 2;

  float delta = axes[maxIdx] - prev[maxIdx];
  if (maxIdx == 0) return (delta > 0) ? TapDir::PosX : TapDir::NegX;
  if (maxIdx == 1) return (delta > 0) ? TapDir::PosY : TapDir::NegY;
  return (delta > 0) ? TapDir::PosZ : TapDir::NegZ;
}
