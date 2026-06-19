#pragma once

#include <stdint.h>

class HIDController {
 public:
  void begin() {}
  void task() {}
  bool sendReports(const float motion[6], uint16_t buttonBits) {
    for (int i = 0; i < 6; i++) {
      lastSentMotion_[i] = motion[i];
    }
    lastSentButtons_ = buttonBits;
    return true;
  }

  // Helpers for testing
  float lastSentMotion_[6] = {0.0f};
  uint16_t lastSentButtons_ = 0;
};
