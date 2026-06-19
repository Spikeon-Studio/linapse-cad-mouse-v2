#include "controllers/InputController.h"

#include "Config.h"

using namespace ace_button;

namespace {
const long kCalibrationHoldMs  = 3000;
const long kColorConfigHoldMs  = 6000;
const uint16_t leftButtonMask  = 0x0001;
const uint16_t rightButtonMask = 0x0002;
}

InputController* InputController::instance_ = nullptr;

InputController::InputController()
    : leftBtn_(Config::PIN_LEFT_BTN), rightBtn_(Config::PIN_RIGHT_BTN) {}

void InputController::begin() {
  pinMode(Config::PIN_LEFT_BTN, INPUT_PULLUP);
  pinMode(Config::PIN_RIGHT_BTN, INPUT_PULLUP);

  ButtonConfig* cfg = ButtonConfig::getSystemButtonConfig();
  cfg->setEventHandler(handleButtonEvent);

  instance_ = this;
  calibrationRequested_ = false;
  colorConfigRequested_ = false;
  hadActivity_ = false;
  bothHeldStartMs_ = 0;
  calibrationHoldFired_ = false;
  colorConfigHoldFired_ = false;
  leftPressed_ = false;
  rightPressed_ = false;
  leftClicked_ = false;
  rightClicked_ = false;
}

void InputController::update() {
  const unsigned long now = millis();
  leftBtn_.check();
  rightBtn_.check();

  if (!areBothPressed()) {
    bothHeldStartMs_ = 0;
    calibrationHoldFired_ = false;
    colorConfigHoldFired_ = false;
    return;
  }

  if (bothHeldStartMs_ == 0) {
    bothHeldStartMs_ = now;
    return;
  }

  const unsigned long heldMs = now - bothHeldStartMs_;

  if (!calibrationHoldFired_ && heldMs >= kCalibrationHoldMs) {
    calibrationRequested_ = true;
    hadActivity_ = true;
    calibrationHoldFired_ = true;
  }

  if (!colorConfigHoldFired_ && heldMs >= kColorConfigHoldMs) {
    colorConfigRequested_ = true;
    hadActivity_ = true;
    colorConfigHoldFired_ = true;
  }
}

uint16_t InputController::buttonBits() const {
  uint16_t bits = 0;
  if (leftPressed_)  bits |= leftButtonMask;
  if (rightPressed_) bits |= rightButtonMask;
  return bits;
}

bool InputController::areBothHeld() const {
  return areBothPressed();
}

bool InputController::takeCalibrationRequest() {
  const bool out = calibrationRequested_;
  calibrationRequested_ = false;
  return out;
}

bool InputController::takeColorConfigRequest() {
  const bool out = colorConfigRequested_;
  colorConfigRequested_ = false;
  return out;
}

bool InputController::takeLeftClick() {
  const bool out = leftClicked_;
  leftClicked_ = false;
  return out;
}

bool InputController::takeRightClick() {
  const bool out = rightClicked_;
  rightClicked_ = false;
  return out;
}

bool InputController::takeActivity() {
  const bool out = hadActivity_;
  hadActivity_ = false;
  return out;
}

void InputController::handleButtonEvent(AceButton* button, uint8_t eventType,
                                        uint8_t /*buttonState*/) {
  if (instance_ == nullptr) return;
  instance_->onButtonEvent(button, eventType);
}

void InputController::onButtonEvent(AceButton* button, uint8_t eventType) {
  if (eventType == AceButton::kEventPressed) {
    int btnIdx = -1;
    if (button->getPin() == Config::PIN_LEFT_BTN) {
      leftPressed_ = true;
      leftClicked_ = true;
      btnIdx = 0;
    } else if (button->getPin() == Config::PIN_RIGHT_BTN) {
      rightPressed_ = true;
      rightClicked_ = true;
      btnIdx = 1;
    } else {
      return;
    }
    hadActivity_ = true;
    if (btnIdx != -1) {
      Serial.print("BUTTON:");
      Serial.print(btnIdx);
      Serial.println(":1");
    }
    return;
  }

  if (eventType == AceButton::kEventReleased) {
    int btnIdx = -1;
    if (button->getPin() == Config::PIN_LEFT_BTN) {
      leftPressed_ = false;
      btnIdx = 0;
    } else if (button->getPin() == Config::PIN_RIGHT_BTN) {
      rightPressed_ = false;
      btnIdx = 1;
    } else {
      return;
    }
    hadActivity_ = true;
    if (btnIdx != -1) {
      Serial.print("BUTTON:");
      Serial.print(btnIdx);
      Serial.println(":0");
    }
  }
}

bool InputController::areBothPressed() const {
  return leftPressed_ && rightPressed_;
}
