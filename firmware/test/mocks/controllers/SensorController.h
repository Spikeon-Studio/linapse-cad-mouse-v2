#pragma once

class SensorController {
 public:
  SensorController() : calibrationActive_(false), calibrationDone_(true) {}

  void begin() {}
  bool readRaw(float out[9]) {
    for (int i = 0; i < 9; i++) out[i] = 0.0f;
    return true;
  }

  void beginCalibration() {
    calibrationActive_ = true;
    calibrationDone_ = false;
  }
  
  void updateCalibration() {
    calibrationActive_ = false;
    calibrationDone_ = true;
  }
  
  bool calibrationDone() const {
    return calibrationDone_;
  }

  const float* baseline() const {
    return baseline_;
  }

  // Helpers for testing
  bool calibrationActive_;
  bool calibrationDone_;
  float baseline_[9] = {0.0f};
};
