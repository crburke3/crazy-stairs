#include <FastLED.h>
#include <Arduino.h>
#include <Wire.h>
#include "vl53l0x_multiplexer.h"

// I2C Pin Configuration
#define I2C_SDA 21
#define I2C_SCL 22

// LED Configuration
#define NUM_LEDS 400
#define DATA_PIN 16
#define POWER_PIN 12
#define FADE_SPEED 5  // How many brightness steps per update
#define TRIGGER_DISTANCE 300  // Distance in mm to trigger LED section
#define FADE_DURATION 2000  // Duration in ms for fade out

// LED Section Definitions
struct LEDSection {
    int startIndex;
    int endIndex;
    bool isActive;
    unsigned long triggerTime;
    uint8_t brightness;
};

// Define LED sections
LEDSection sections[] = {
    {0, 112, false, 0, 0},    // Section 1: LEDs 0-5 controlled by channel 0
    {112, 224, false, 0, 0}   // Section 2: LEDs 5-122 controlled by channel 1
};

// Global Variables
VL53L0XMultiplexer* sensorMux1 = nullptr;
CRGB leds[NUM_LEDS];

void updateLEDSection(LEDSection& section, bool triggered) {
    if (triggered) {
        // If section is triggered, set to full brightness and record time
        section.isActive = true;
        section.triggerTime = millis();
        section.brightness = 255;
        
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
            // Calculate fade based on elapsed time
            section.brightness = map(elapsed, 0, FADE_DURATION, 255, 0);
        }
        
        // Apply brightness to all LEDs in section
        for (int i = section.startIndex; i < section.endIndex; i++) {
            leds[i].nscale8(section.brightness);
        }
    }
}

bool scanForMultiplexers(uint8_t& mux1Addr) {
    Serial.println("\nScanning for TCA9548A multiplexer...");
    bool foundMux1 = false;
    int foundCount = 0;
    
    for (uint8_t addr = 0x70; addr <= 0x77; addr++) {
        Wire.beginTransmission(addr);
        uint8_t error = Wire.endTransmission();
        
        Serial.print("Address 0x");
        Serial.print(addr, HEX);
        Serial.print(": ");
        
        if (error == 0) {
            Serial.println("Found TCA9548A");
            foundCount++;
            
            if (!foundMux1) {
                mux1Addr = addr;
                foundMux1 = true;
            }
        } else {
            Serial.println("No device");
        }
    }
    
    Serial.print("\nFound ");
    Serial.print(foundCount);
    Serial.println(" TCA9548A multiplexers");
    
    if (!foundMux1) {
        Serial.println("✗ Could not find a TCA9548A multiplexer");
        return false;
    }
    
    Serial.print("Using multiplexer at address 0x");
    Serial.println(mux1Addr, HEX);
    
    return true;
}

bool initializeSensors() {
    uint8_t mux1Addr;
    if (!scanForMultiplexers(mux1Addr)) {
        return false;
    }
    
    // Create multiplexer instance with found address
    sensorMux1 = new VL53L0XMultiplexer(mux1Addr);
    
    Serial.println("\nInitializing TCA9548A multiplexer...");
    bool mux1Initialized = false;
    
    // Try to initialize multiplexer
    Serial.print("Attempting to initialize Multiplexer (0x");
    Serial.print(mux1Addr, HEX);
    Serial.println("):");
    mux1Initialized = sensorMux1->begin();
    if (mux1Initialized) {
        Serial.println("✓ Multiplexer initialized successfully");
    } else {
        Serial.println("✗ Failed to initialize multiplexer");
        return false;
    }

    // Initialize sensors on multiplexer
    Serial.println("\nInitializing VL53L0X sensors...");
    bool allSensorsInitialized = true;
    
    // Initialize sensor on channel 0
    if (!sensorMux1->initSensor(0, 0)) {
        Serial.println("✗ Failed to initialize sensor on channel 0");
        allSensorsInitialized = false;
    }
    
    // Initialize sensor on channel 1
    if (!sensorMux1->initSensor(1, 0)) {
        Serial.println("✗ Failed to initialize sensor on channel 1");
        allSensorsInitialized = false;
    }
    
    if (!allSensorsInitialized) {
        Serial.println("\nWarning: Not all sensors initialized successfully");
        Serial.println("The system will continue with available sensors");
    }
    
    return true;
}

void setup() {
    // Wait for serial connection
    delay(2000);
    
    // Initialize Serial port
    Serial.begin(115200);
    Serial.println("\n----------------------------------------");
    Serial.println("VL53L0X Distance Sensor Test Program");
    Serial.println("----------------------------------------");
    
    // Initialize LEDs
    Serial.println("\nInitializing LEDs...");
    pinMode(POWER_PIN, OUTPUT);
    digitalWrite(POWER_PIN, HIGH);  // Enable 5V power supply
    FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
    
    // Turn on all LEDs with initial color
    fill_solid(leds, NUM_LEDS, CHSV(0, 0, 0));
    FastLED.show();
    Serial.println("✓ LEDs initialized and turned on");
    
    // Initialize I2C with custom pins
    Serial.println("\nInitializing I2C communication...");
    Serial.print("  SDA pin: GPIO");
    Serial.println(I2C_SDA);
    Serial.print("  SCL pin: GPIO");
    Serial.println(I2C_SCL);
    Wire.begin(I2C_SDA, I2C_SCL);
    Serial.println("✓ I2C communication initialized");
    
    // Keep trying to initialize the sensors until the multiplexer is working
    bool sensorsInitialized = false;
    int attemptCount = 0;
    
    while (!sensorsInitialized) {
        attemptCount++;
        Serial.print("\nAttempt ");
        Serial.println(attemptCount);
        
        sensorsInitialized = initializeSensors();
        if (!sensorsInitialized) {
            Serial.println("\nRetrying sensor initialization in 1 second...");
            delay(1000);
        }
    }
    
    Serial.println("\n✓ All sensors initialized successfully");
    Serial.println("\nStarting LED animation and sensor monitoring...");
}

void loop() {
    // Read distances from multiplexer
    uint16_t distance1_ch0, distance1_ch1;
    bool ch0Triggered = false;
    bool ch1Triggered = false;
    
    if (sensorMux1->readDistance(0, distance1_ch0)) {
        ch0Triggered = (distance1_ch0 < TRIGGER_DISTANCE);
    }
    
    delay(10);  // Small delay between channel reads
    
    if (sensorMux1->readDistance(1, distance1_ch1)) {
        ch1Triggered = (distance1_ch1 < TRIGGER_DISTANCE);
    }
    
    // Update LED sections based on sensor readings
    updateLEDSection(sections[0], ch0Triggered);  // Update section controlled by channel 0
    updateLEDSection(sections[1], ch1Triggered);  // Update section controlled by channel 1
    
    // Show the updated LEDs
    FastLED.show();
    
    // Small delay to prevent overwhelming the system
    delay(10);
}