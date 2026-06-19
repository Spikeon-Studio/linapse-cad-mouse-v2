#include "controllers/LEDController.h"
#include "Config.h"
#include "LedConfig.h"

LEDController::LEDController()
    : ring_(Config::LED_COUNT, Config::PIN_LED_DATA,
            NEO_GRB + NEO_KHZ800) {}

void LEDController::fillAll(unsigned long color) {
  for (int i = 0; i < ring_.numPixels(); i++) {
    ring_.setPixelColor(i, color);
  }
}

unsigned long LEDController::toNeoColor(unsigned long color) {
  int r = (color >> 16) & 0xFF;
  int g = (color >> 8) & 0xFF;
  int b = color & 0xFF;
  return ring_.Color(r, g, b);
}

void LEDController::begin() {
  pinMode(Config::PIN_LED_LS, OUTPUT);
  digitalWrite(Config::PIN_LED_LS, LOW);

  ring_.begin();
  ring_.setBrightness(ledConfig.brightness);
  ring_.show();
}

void LEDController::applyConfig() {
  ring_.setBrightness(ledConfig.brightness);
  if (mode_ == Mode::Solid) {
    setSolid(ledConfig.idleColor);
  }
}

void LEDController::setPreview(uint8_t brightness, unsigned long color) {
  ring_.setBrightness(brightness);
  setSolid(color);
}

void LEDController::setPower(bool enabled) {
  if (enabled == isPowered_) {
    return;
  }

  isPowered_ = enabled;
  digitalWrite(Config::PIN_LED_LS, enabled ? HIGH : LOW);
  delay(10);
  
}

void LEDController::setSolid(unsigned long color) {
  mode_ = Mode::Solid;
  color_ = toNeoColor(color);
  setPower(true);
  fillAll(color_);
  ring_.show();
}

void LEDController::startSpinner(unsigned long color) {
  mode_ = Mode::Spinner;
  color_ = toNeoColor(color);
  spinnerIndex_ = 0;
  lastSpinnerStepMs_ = 0;
  setPower(true);
}

void LEDController::updateSpinner() {
  if (mode_ != Mode::Spinner) {
    return;
  }

  const unsigned long now = millis();
  if (lastSpinnerStepMs_ != 0 && (now - lastSpinnerStepMs_) < 60) {
    return;
  }
  lastSpinnerStepMs_ = now;

  fillAll(0);
  int pixelCount = ring_.numPixels();
  ring_.setPixelColor(spinnerIndex_, color_);
  ring_.show();

  spinnerIndex_++;
  if (spinnerIndex_ >= pixelCount) {
    spinnerIndex_ = 0;
  }
}

void LEDController::off() {
  mode_ = Mode::Off;
  fillAll(0);
  ring_.show();
  setPower(false);
}

void LEDController::effectBegin() {
  mode_ = Mode::Solid;  // suppress spinner
  setPower(true);
  ring_.setBrightness(255);  // EffectEngine provides pre-scaled colors
}

void LEDController::effectPixel(int idx, uint32_t rrggbb) {
  int r = (rrggbb >> 16) & 0xFF;
  int g = (rrggbb >> 8)  & 0xFF;
  int b =  rrggbb        & 0xFF;
  ring_.setPixelColor(idx, ring_.Color(r, g, b));
}

void LEDController::effectCommit() {
  ring_.show();
}

int LEDController::numPixels() const {
  return ring_.numPixels();
}

uint32_t LEDController::getPixelColor(int idx) const {
  return ring_.getPixelColor(idx);
}
