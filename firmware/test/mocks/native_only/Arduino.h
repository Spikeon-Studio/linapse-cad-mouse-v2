#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>
#include <string>
#include <algorithm>
#include <iostream>
#include <chrono>
#include <thread>

// Arduino Types
typedef bool boolean;
typedef uint8_t byte;

// Arduino Pins / Constants
#define D0 0
#define D1 1
#define D2 2
#define D3 3
#define D8 8
#define D9 9
#define D10 10

#define INPUT 0
#define OUTPUT 1
#define INPUT_PULLUP 2
#define HIGH 1
#define LOW 0

// Basic String class mimicking Arduino String
class String {
private:
    std::string s_;
public:
    String() : s_("") {}
    String(const char* s) : s_(s ? s : "") {}
    String(const std::string& s) : s_(s) {}
    String(char c) : s_(1, c) {}
    String(int val) : s_(std::to_string(val)) {}
    String(unsigned int val) : s_(std::to_string(val)) {}
    String(long val) : s_(std::to_string(val)) {}
    String(unsigned long val) : s_(std::to_string(val)) {}
    String(float val) : s_(std::to_string(val)) {}

    const char* c_str() const { return s_.c_str(); }
    unsigned int length() const { return s_.length(); }

    int toInt() const {
        try {
            return std::stoi(s_);
        } catch (...) {
            return 0;
        }
    }

    bool startsWith(const String& prefix) const {
        if (prefix.length() > s_.length()) return false;
        return s_.compare(0, prefix.length(), prefix.s_) == 0;
    }

    bool startsWith(const char* prefix) const {
        return startsWith(String(prefix));
    }

    String substring(unsigned int from, unsigned int to = -1) const {
        if (from >= s_.length()) return String("");
        if (to == (unsigned int)-1 || to > s_.length()) {
            return String(s_.substr(from));
        }
        if (to <= from) return String("");
        return String(s_.substr(from, to - from));
    }

    void trim() {
        // Trim leading space
        s_.erase(s_.begin(), std::find_if(s_.begin(), s_.end(), [](unsigned char ch) {
            return !std::isspace(ch);
        }));
        // Trim trailing space
        s_.erase(std::find_if(s_.rbegin(), s_.rend(), [](unsigned char ch) {
            return !std::isspace(ch);
        }).base(), s_.end());
    }

    int indexOf(char ch, unsigned int fromIndex = 0) const {
        if (fromIndex >= s_.length()) return -1;
        auto pos = s_.find(ch, fromIndex);
        return (pos == std::string::npos) ? -1 : (int)pos;
    }

    int indexOf(const String& str, unsigned int fromIndex = 0) const {
        if (fromIndex >= s_.length()) return -1;
        auto pos = s_.find(str.s_, fromIndex);
        return (pos == std::string::npos) ? -1 : (int)pos;
    }

    bool operator==(const String& rhs) const { return s_ == rhs.s_; }
    bool operator==(const char* rhs) const { return s_ == (rhs ? rhs : ""); }
    bool operator!=(const String& rhs) const { return s_ != rhs.s_; }
    bool operator!=(const char* rhs) const { return s_ != (rhs ? rhs : ""); }
    
    String& operator+=(const String& rhs) {
        s_ += rhs.s_;
        return *this;
    }
    String& operator+=(char c) {
        s_ += c;
        return *this;
    }
    String& operator+=(const char* rhs) {
        s_ += (rhs ? rhs : "");
        return *this;
    }

    friend String operator+(String lhs, const String& rhs) {
        lhs += rhs;
        return lhs;
    }
    friend String operator+(String lhs, const char* rhs) {
        lhs += rhs;
        return lhs;
    }
    friend String operator+(String lhs, char c) {
        lhs += c;
        return lhs;
    }
};

inline std::ostream& operator<<(std::ostream& os, const String& s) {
    os << s.c_str();
    return os;
}

// Mock Serial class
class MockSerial {
public:
    void begin(unsigned long baud) {}
    int available() { return 0; }
    int read() { return -1; }
    
    template<typename T>
    size_t print(T val) {
        std::cout << val;
        return 1;
    }
    
    template<typename T>
    size_t println(T val) {
        std::cout << val << std::endl;
        return 1;
    }
    
    size_t println() {
        std::cout << std::endl;
        return 1;
    }
};

inline MockSerial Serial;

// Mock rp2040 reboot to bootloader
struct MockRP2040 {
    void rebootToBootloader() {}
};

inline MockRP2040 rp2040;

// Standard control/time functions
inline unsigned long millis() {
    static auto start_time = std::chrono::steady_clock::now();
    auto current_time = std::chrono::steady_clock::now();
    return std::chrono::duration_cast<std::chrono::milliseconds>(current_time - start_time).count();
}

inline void delay(unsigned long ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

inline void pinMode(uint8_t pin, uint8_t mode) {}
inline void digitalWrite(uint8_t pin, uint8_t val) {}
inline int digitalRead(uint8_t pin) { return 0; }
