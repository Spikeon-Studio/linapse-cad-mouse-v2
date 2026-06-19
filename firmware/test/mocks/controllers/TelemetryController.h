#pragma once

class TelemetryController {
 public:
  void begin() {}
  void publish(const float motion[6], int buttonBits, bool hidReportSent) {
    for (int i = 0; i < 6; i++) {
      lastPublishedMotion_[i] = motion[i];
    }
    lastPublishedButtons_ = buttonBits;
    lastPublishedHidReportSent_ = hidReportSent;
  }
  bool enabled() const { return enabled_; }

  // Helpers for testing
  bool enabled_ = true;
  float lastPublishedMotion_[6] = {0.0f};
  int lastPublishedButtons_ = 0;
  bool lastPublishedHidReportSent_ = false;
};
