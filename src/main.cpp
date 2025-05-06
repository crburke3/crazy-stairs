#include <FastLED.h>
#include <Arduino.h>
#include <Wire.h>
#include "vl53l0x_multiplexer.h"

// I2C Pin Configuration
#define I2C_SDA 21
#define I2C_SCL 22

// Stair Configuration
#define STAIR_LENGTH 30    // Number of LEDs per stair
#define NUM_STAIRS 10      // Total number of stairs
#define NUM_LEDS (STAIR_LENGTH * NUM_STAIRS)  // Total number of LEDs

// LED Configuration
#define DATA_PIN 16
#define POWER_PIN 12
#define TRIGGER_DISTANCE 740  // Distance in mm to trigger LED section 
#define FADE_DURATION 700  // Duration in ms for fade out (reduced from 2000ms to 1000ms)
#define STATUS_CHECK_INTERVAL 10000  // Check status every 10 seconds
#define DISTANCE_LOG_INTERVAL 5000    // Log distances every 5 seconds
#define LED_FRAME_UPDATE_INTERVAL 1    // Update LEDs every 3ms for smoother animation (16 = 60fps, 3 = 330fps)
#define SENSOR_CHECK_INTERVAL 300  // Check sensors every 100ms

// LED Section Definitions
struct LEDSection {
    int startIndex;
    int endIndex;
    bool isActive;
    unsigned long triggerTime;
    uint8_t brightness;
    bool isConnected;  // Track if this section's sensor is connected
    bool isInitialized;  // Track if this section's sensor has been initialized
    CRGB targetColor;   // The color to fade into
};

// Global Variables
VL53L0XMultiplexer* sensorMux1 = nullptr;
CRGB leds[NUM_LEDS];
unsigned long lastStatusCheck = 0;
unsigned long lastDistanceLog = 0;
bool multiplexerConnected = false;
LEDSection* sections = nullptr;  // Will be dynamically allocated
int numSections = 0;  // Will be set based on number of stairs

// Easing function for smooth fade out (easeOutQuad)
uint8_t easeOutQuad(unsigned long elapsed, unsigned long duration) {
    float t = (float)elapsed / duration;
    t = 1.0f - (t * t);  // Quadratic ease out
    return (uint8_t)(t * 255.0f);
}

// Function to blend between two colors
CRGB blendColors(CRGB color1, CRGB color2, uint8_t amount) {
    CRGB result;
    result.r = (color1.r * (255 - amount) + color2.r * amount) / 255;
    result.g = (color1.g * (255 - amount) + color2.g * amount) / 255;
    result.b = (color1.b * (255 - amount) + color2.b * amount) / 255;
    return result;
}

// Function to convert CRGB to hex string for logging
String colorToHex(CRGB color) {
    char hex[8];
    snprintf(hex, sizeof(hex), "#%02X%02X%02X", color.r, color.g, color.b);
    return String(hex);
}

void initializeLEDSections() {
    // Each stair gets its own section
    numSections = NUM_STAIRS;
    sections = new LEDSection[numSections];
    
    // Initialize each section
    for (int i = 0; i < numSections; i++) {
        sections[i] = {
            i * STAIR_LENGTH,           // startIndex
            (i + 1) * STAIR_LENGTH,     // endIndex
            false,                      // isActive
            0,                          // triggerTime
            0,                          // brightness
            false,                      // isConnected
            false,                      // isInitialized
            CRGB::Black                 // targetColor
        };
    }
    
    // Print section information
    Serial.println("\nLED Section Configuration:");
    for (int i = 0; i < numSections; i++) {
        Serial.print("Section ");
        Serial.print(i);
        Serial.print(": LEDs ");
        Serial.print(sections[i].startIndex);
        Serial.print(" to ");
        Serial.print(sections[i].endIndex - 1);
        Serial.print(" (");
        Serial.print(sections[i].endIndex - sections[i].startIndex);
        Serial.println(" LEDs)");
    }
    Serial.println();
}

bool initializeSensorChannel(uint8_t channel) {
    if (sensorMux1 != nullptr && channel < numSections) {
        if (sensorMux1->initSensor(channel, 0)) {
            Serial.print("Successfully initialized sensor on channel ");
            Serial.println(channel);
            sections[channel].isInitialized = true;
            return true;
        } else {
            Serial.print("Failed to initialize sensor on channel ");
            Serial.println(channel);
            sections[channel].isInitialized = false;
            return false;
        }
    }
    return false;
}

void checkMultiplexerStatus() {
    Serial.println("\n=== Multiplexer Status Check ===");
    bool foundAnyMux = false;
    
    // Check all possible multiplexer addresses (0x70 to 0x77)
    for (uint8_t addr = 0x70; addr <= 0x77; addr++) {
        Wire.beginTransmission(addr);
        uint8_t error = Wire.endTransmission();
        
        if (error == 0) {
            foundAnyMux = true;
            Serial.print("Found multiplexer at address 0x");
            Serial.println(addr, HEX);
            
            // Create temporary multiplexer instance to check channels
            VL53L0XMultiplexer tempMux(addr);
            if (tempMux.begin()) {
                Serial.println("Connected channels:");
                
                // Reset all section connection statuses
                for (int i = 0; i < numSections; i++) {
                    sections[i].isConnected = false;
                }
                
                // Check each channel (0-7)
                for (uint8_t channel = 0; channel < 8; channel++) {
                    Wire.beginTransmission(addr);
                    Wire.write(1 << channel);  // Select channel
                    if (Wire.endTransmission() == 0) {
                        // Try to read from VL53L0X address (0x29)
                        Wire.beginTransmission(0x29);
                        uint8_t sensorError = Wire.endTransmission();
                        if (sensorError == 0) {
                            Serial.print("  Channel ");
                            Serial.print(channel);
                            Serial.println(": VL53L0X sensor detected");
                            
                            // Update section connection status if within range
                            if (channel < numSections) {
                                sections[channel].isConnected = true;
                                // Initialize the sensor if it's newly connected
                                if (!sections[channel].isInitialized) {
                                    initializeSensorChannel(channel);
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    
    if (!foundAnyMux) {
        Serial.println("No multiplexers found!");
        multiplexerConnected = false;
        // Reset all section connection statuses
        for (int i = 0; i < numSections; i++) {
            sections[i].isConnected = false;
            sections[i].isInitialized = false;
        }
    } else {
        multiplexerConnected = true;
    }
    
    Serial.println("==============================\n");
}

// Function to generate a random color
CRGB getRandomColor() {
    // Generate random hue (0-255)
    uint8_t hue = random8();
    // Convert HSV to RGB
    CRGB color;
    hsv2rgb_rainbow(CHSV(hue, 255, 255), color);
    return color;
}

void updateLEDSection(LEDSection& section, bool triggered, int sectionIndex) {
    if (!section.isConnected) {
        // If section's sensor is not connected, keep LEDs off
        for (int i = section.startIndex; i < section.endIndex; i++) {
            leds[i] = CRGB::Black;
        }
        return;
    }

    if (triggered) {
        // If section is triggered, set to full brightness and record time
        section.isActive = true;
        section.triggerTime = millis();
        section.brightness = 255;
        section.targetColor = getRandomColor();  // Set new random color
        
        // Log the trigger and color information
        Serial.print("Sensor ");
        Serial.print(sectionIndex);
        Serial.print(" triggered! Fading to color: ");
        Serial.println(colorToHex(section.targetColor));
        
        // Set all LEDs in section to white at full brightness
        for (int i = section.startIndex; i < section.endIndex; i++) {
            leds[i] = CRGB::White;
        }
    } else if (section.isActive) {
        // If section was active, check if it's time to fade
        unsigned long elapsed = millis() - section.triggerTime;
        if (elapsed >= FADE_DURATION) {
            section.isActive = false;
            section.brightness = 0;
        } else {
            // Use easing function for smooth fade
            section.brightness = easeOutQuad(elapsed, FADE_DURATION);
        }
        
        // Apply brightness to all LEDs in section
        for (int i = section.startIndex; i < section.endIndex; i++) {
            // Blend from white to random color as it fades
            uint8_t colorBlend = 255 - section.brightness;
            leds[i] = blendColors(CRGB::White, section.targetColor, colorBlend);
            // Apply gamma correction for more natural-looking fade
            leds[i].nscale8_video(section.brightness);
        }
    }
}

void logSensorDistances() {
    if (!multiplexerConnected || sensorMux1 == nullptr) {
        return;
    }

    Serial.print("Distances: ");
    bool anySensorRead = false;

    // Check each section's sensor
    for (int i = 0; i < numSections; i++) {
        if (sections[i].isConnected) {
            uint16_t distance = 0;
            if (sensorMux1->readDistance(i, distance)) {
                Serial.print("S");
                Serial.print(i);
                Serial.print(":");
                Serial.print(distance);
                Serial.print("mm ");
                anySensorRead = true;
            } else {
                // Sensor is connected but failed to read
                Serial.print("S");
                Serial.print(i);
                Serial.print(":FAIL ");
            }
        }
    }

    if (!anySensorRead) {
        Serial.print("No sensors connected");
    }
    Serial.println();
}

void setup() {
    // Initialize Serial for debugging
    Serial.begin(115200);
    delay(4000);
    Serial.println("Starting Crazy Stairs...");
    
    // Initialize random seed
    random16_set_seed(analogRead(0));
    
    // Initialize I2C
    Wire.begin(I2C_SDA, I2C_SCL);
    
    // Initialize LED power pin
    pinMode(POWER_PIN, OUTPUT);
    digitalWrite(POWER_PIN, HIGH);
    
    // Initialize FastLED
    FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(255);
    FastLED.clear();
    FastLED.show();
    
    // Initialize LED sections
    initializeLEDSections();
    
    // Scan for multiplexer
    Serial.println("Scanning for multiplexer...");
    checkMultiplexerStatus();
    bool foundMux = false;
    uint8_t muxAddr = 0x70;
    
    for (uint8_t addr = 0x70; addr <= 0x77; addr++) {
        Wire.beginTransmission(addr);
        uint8_t error = Wire.endTransmission();
        
        if (error == 0) {
            Serial.print("Found multiplexer at address 0x");
            Serial.println(addr, HEX);
            muxAddr = addr;
            foundMux = true;
            break;
        }
    }
    
    if (foundMux) {
        // Initialize multiplexer with found address
        sensorMux1 = new VL53L0XMultiplexer(muxAddr);
        if (sensorMux1->begin()) {
            Serial.println("Initializing all detected sensors...");
            // Initialize all possible channels (0-7)
            for (uint8_t channel = 0; channel < 8; channel++) {
                if (sensorMux1->initSensor(channel, 0)) {
                    Serial.print("Successfully initialized sensor on channel ");
                    Serial.println(channel);
                }
            }
        } else {
            Serial.println("Warning: Failed to initialize multiplexer, continuing without sensors");
            delete sensorMux1;
            sensorMux1 = nullptr;
        }
    } else {
        Serial.println("Warning: No multiplexer found, continuing without sensors");
    }
    
    Serial.println("Setup complete!");
}

void loop() {
    static unsigned long lastUpdate = 0;
    static unsigned long lastSensorCheck = 0;
    
    // Check multiplexer status every 10 seconds
    if (millis() - lastStatusCheck >= STATUS_CHECK_INTERVAL) {
        checkMultiplexerStatus();
        lastStatusCheck = millis();
    }

    // Log distances every 0.5 seconds
    if (millis() - lastDistanceLog >= DISTANCE_LOG_INTERVAL) {
        logSensorDistances();
        lastDistanceLog = millis();
    }

    // Check sensor distances at regular intervals
    if (millis() - lastSensorCheck >= SENSOR_CHECK_INTERVAL) {
        lastSensorCheck = millis();
        
        // Only check sensors if multiplexer is connected
        if (multiplexerConnected && sensorMux1 != nullptr) {
            // Process each section
            for (int section = 0; section < numSections; section++) {
                if (sections[section].isConnected) {
                    uint16_t distance = 0;
                    bool triggered = false;
                    
                    if (sensorMux1->readDistance(section, distance)) {
                        // Check for sensor disconnection (65535mm is the error value)
                        if (distance == 65535) {
                            Serial.print("Sensor on channel ");
                            Serial.print(section);
                            Serial.println(" disconnected!");
                            sections[section].isConnected = false;
                            sections[section].isInitialized = false;
                            // Turn off LEDs for this section
                            for (int i = sections[section].startIndex; i < sections[section].endIndex; i++) {
                                leds[i] = CRGB::Black;
                            }
                        } else {
                            triggered = (distance < TRIGGER_DISTANCE);
                            // Update the LED section's trigger state
                            updateLEDSection(sections[section], triggered, section);
                        }
                    }
                }
            }
        }
    }

    // Update LED animations
    if (millis() - lastUpdate >= LED_FRAME_UPDATE_INTERVAL) {
        lastUpdate = millis();
        
        // Update all sections
        for (int section = 0; section < numSections; section++) {
            if (sections[section].isConnected) {
                if (sections[section].isActive) {
                    // If section was active, check if it's time to fade
                    unsigned long elapsed = millis() - sections[section].triggerTime;
                    if (elapsed >= FADE_DURATION) {
                        sections[section].isActive = false;
                        sections[section].brightness = 0;
                    } else {
                        // Use easing function for smooth fade
                        sections[section].brightness = easeOutQuad(elapsed, FADE_DURATION);
                        
                        // Calculate color blend amount (inverse of brightness)
                        uint8_t colorBlend = 255 - sections[section].brightness;
                        
                        // Apply color and brightness to all LEDs in section
                        for (int i = sections[section].startIndex; i < sections[section].endIndex; i++) {
                            // Blend from white to random color as it fades
                            leds[i] = blendColors(CRGB::White, sections[section].targetColor, colorBlend);
                            // Apply gamma correction for more natural-looking fade
                            leds[i].nscale8_video(sections[section].brightness);
                        }
                    }
                } else {
                    // If section is not active, ensure LEDs are off
                    for (int i = sections[section].startIndex; i < sections[section].endIndex; i++) {
                        leds[i] = CRGB::Black;
                    }
                }
            }
        }
        
        // Show the updated LEDs
        FastLED.show();
    }
    
    // Small delay to prevent overwhelming the system
    delay(1);
}