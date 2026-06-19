#pragma once

#include <stdint.h>
#include <string.h>
#include <stddef.h>

class EEPROMClass {
public:
    static constexpr int kMockSize = 512;

    void begin(size_t size) {}
    
    template<typename T>
    void get(int address, T& value) {
        if (address >= 0 && address + sizeof(T) <= kMockSize) {
            memcpy(&value, &eeprom_data[address], sizeof(T));
        }
    }
    
    template<typename T>
    void put(int address, const T& value) {
        if (address >= 0 && address + sizeof(T) <= kMockSize) {
            memcpy(&eeprom_data[address], &value, sizeof(T));
        }
    }
    
    bool commit() { return true; }

    static uint8_t eeprom_data[kMockSize];
};

inline uint8_t EEPROMClass::eeprom_data[kMockSize] = {0};
inline EEPROMClass EEPROM;
