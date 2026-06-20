#include "SensConfig.h"
#include "Config.h"
#include <EEPROM.h>

SensConfig sensConfig;

namespace {
constexpr uint32_t kMagic      = 0xCAD30001;
constexpr int      kBase       = 16;  // LedConfig occupies bytes 0-15
constexpr int      kAddrMagic  = kBase + 0;
constexpr int      kAddrDeadT  = kBase + 4;
constexpr int      kAddrDeadR  = kBase + 8;
constexpr int      kAddrKalQ   = kBase + 12;
constexpr int      kAddrKalR   = kBase + 16;
constexpr int      kAddrSExp   = kBase + 20;
constexpr int      kAddrTapSens = kBase + 24;
constexpr int      kAddrInvTapZ = kBase + 28;
}

void SensConfig::load() {
  EEPROM.begin(Config::EEPROM_SIZE);
  uint32_t magic = 0;
  EEPROM.get(kAddrMagic, magic);
  if (magic != kMagic) { reset(); return; }
  EEPROM.get(kAddrDeadT, deadT);
  EEPROM.get(kAddrDeadR, deadR);
  EEPROM.get(kAddrKalQ,  kalmanQ);
  EEPROM.get(kAddrKalR,  kalmanR);
  EEPROM.get(kAddrSExp,  sensitivityExp);
  EEPROM.get(kAddrTapSens, tapThreshold);
  EEPROM.get(kAddrInvTapZ, invertTapZ);
}

void SensConfig::save() {
  EEPROM.begin(Config::EEPROM_SIZE);
  uint32_t magic = kMagic;
  EEPROM.put(kAddrMagic, magic);
  EEPROM.put(kAddrDeadT, deadT);
  EEPROM.put(kAddrDeadR, deadR);
  EEPROM.put(kAddrKalQ,  kalmanQ);
  EEPROM.put(kAddrKalR,  kalmanR);
  EEPROM.put(kAddrSExp,  sensitivityExp);
  EEPROM.put(kAddrTapSens, tapThreshold);
  EEPROM.put(kAddrInvTapZ, invertTapZ);
  EEPROM.commit();
}

void SensConfig::reset() {
  deadT          = Config::DEAD_T;
  deadR          = Config::DEAD_R;
  kalmanQ        = Config::KALMAN_Q;
  kalmanR        = Config::KALMAN_R;
  sensitivityExp = Config::SENSITIVITY_EXP;
  tapThreshold   = Config::TAP_VELOCITY_THRESHOLD;
  invertTapZ     = false;
}
