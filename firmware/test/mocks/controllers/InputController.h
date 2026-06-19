#pragma once

#include <stdint.h>

class InputController {
 public:
  InputController() {}
  void begin() {}
  void update() {}

  uint16_t buttonBits() const { return buttonBits_; }
  bool areBothHeld() const { return bothHeld_; }
  bool takeCalibrationRequest() {
    bool req = calibrationRequested_;
    calibrationRequested_ = false;
    return req;
  }
  bool takeColorConfigRequest() {
    bool req = colorConfigRequested_;
    colorConfigRequested_ = false;
    return req;
  }
  bool takeLeftClick() {
    bool req = leftClicked_;
    leftClicked_ = false;
    return req;
  }
  bool takeRightClick() {
    bool req = rightClicked_;
    rightClicked_ = false;
    return req;
  }
  bool takeActivity() {
    bool req = hadActivity_;
    hadActivity_ = false;
    return req;
  }

  // Helpers for setting mock state in tests
  void setButtonBits(uint16_t bits) { buttonBits_ = bits; }
  void setBothHeld(bool held) { bothHeld_ = held; }
  void setCalibrationRequest(bool req) { calibrationRequested_ = req; }
  void setColorConfigRequest(bool req) { colorConfigRequested_ = req; }
  void setLeftClick(bool req) { leftClicked_ = req; }
  void setRightClick(bool req) { rightClicked_ = req; }
  void setActivity(bool req) { hadActivity_ = req; }

 private:
  uint16_t buttonBits_ = 0;
  bool bothHeld_ = false;
  bool calibrationRequested_ = false;
  bool colorConfigRequested_ = false;
  bool leftClicked_ = false;
  bool rightClicked_ = false;
  bool hadActivity_ = false;
};
