#pragma once

#include <stdint.h>
#include <vector>

#define NEO_GRB 0
#define NEO_KHZ800 0

typedef uint32_t neoPixelType;

class Adafruit_NeoPixel {
private:
    uint16_t numLEDs_;
    uint8_t brightness_;
    std::vector<uint32_t> pixels_;
public:
    Adafruit_NeoPixel() : numLEDs_(0), brightness_(255) {}
    Adafruit_NeoPixel(uint16_t n, int16_t pin = -1, neoPixelType type = NEO_GRB + NEO_KHZ800)
        : numLEDs_(n), brightness_(255), pixels_(n, 0) {}

    void begin() {}
    void show() {}
    
    void setPixelColor(uint16_t n, uint32_t c) {
        if (n < pixels_.size()) {
            pixels_[n] = c;
        }
    }
    
    void setBrightness(uint8_t b) {
        brightness_ = b;
    }
    
    uint16_t numPixels() const {
        return numLEDs_;
    }
    
    static uint32_t Color(uint8_t r, uint8_t g, uint8_t b) {
        return ((uint32_t)r << 16) | ((uint32_t)g << 8) | b;
    }

    // Custom helper for testing/debugging
    uint32_t getPixelColor(uint16_t n) const {
        if (n < pixels_.size()) return pixels_[n];
        return 0;
    }
    
    uint8_t getBrightness() const {
        return brightness_;
    }
};
