#pragma once

#include <Adafruit_NeoPixel.h>
#include <Arduino.h>

class LEDController {
 public:
  LEDController();
  void begin();
  void applyConfig();
  void setPreview(uint8_t brightness, unsigned long color);
  void setSolid(unsigned long color);
  void startSpinner(unsigned long color);
  void updateSpinner();
  void off();

  // Per-pixel access for EffectEngine.
  // effectBegin() → effectPixel() × N → effectCommit()
  void effectBegin();
  void effectPixel(int idx, uint32_t rrggbb);
  void effectCommit();
  int  numPixels() const;
  uint32_t getPixelColor(int idx) const;

 private:
  enum class Mode {
    Off,
    Solid,
    Spinner,
  };

  void setPower(bool enabled);
  void fillAll(unsigned long color);
  unsigned long toNeoColor(unsigned long color);

  bool isPowered_ = false;
  Mode mode_ = Mode::Off;
  unsigned long color_ = 0;
  int spinnerIndex_ = 0;
  unsigned long lastSpinnerStepMs_ = 0;
  Adafruit_NeoPixel ring_;
};
