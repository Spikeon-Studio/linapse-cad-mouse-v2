#pragma once

#include <Arduino.h>

// Runtime sensitivity configuration, persisted to flash via EEPROM emulation.
// Serial commands:
//   sens get                       — JSON dump of all sensitivity params
//   sens set <param> <value>       — set a parameter (dead_t|dead_r|kalman_q|kalman_r|exp)
//   sens reset                     — restore firmware defaults
class SensConfig {
 public:
  float deadT;          // translation deadzone
  float deadR;          // rotation deadzone
  float kalmanQ;        // Kalman process noise (higher = more responsive)
  float kalmanR;        // Kalman measurement noise (higher = smoother)
  float sensitivityExp; // power curve exponent (1=linear, 3=cubic)
  float tapThreshold;   // tap detection velocity threshold
  bool  invertTapZ;     // whether Z axis tap detection is inverted
  bool  sphericalMode;   // whether spherical vector processing is active

  void load();
  void save();
  void reset();
};

extern SensConfig sensConfig;
