#include <FastLED.h>
#include <Arduino.h>
#include <Wire.h>
#include <APDS9930.h>

// I2C Pin Configuration
#define I2C_SDA 21
#define I2C_SCL 22

// LED Configuration
#define NUM_LEDS 122
#define DATA_PIN 16
#define POWER_PIN 12

// Global Variables
APDS9930 apds = APDS9930();
CRGB leds[NUM_LEDS];
uint8_t hue = 0;  // For color cycling

bool initializeSensor() {
    Serial.println("\nInitializing APDS-9930 sensor...");
    
    // First check if we can detect the device on I2C
    Wire.beginTransmission(APDS9930_I2C_ADDR);
    byte error = Wire.endTransmission();
    if (error != 0) {
        Serial.print("  ✗ I2C device not found at address 0x");
        Serial.println(APDS9930_I2C_ADDR, HEX);
        Serial.println("  Please check your connections and power supply");
        return false;
    }
    Serial.println("  ✓ I2C device found");
    
    // Try to initialize the sensor
    if (apds.init()) {
        Serial.println("  ✓ Sensor initialization successful");
        
        // Enable proximity sensor
        Serial.println("\nConfiguring proximity sensor...");
        if (apds.enableProximitySensor()) {
            Serial.println("  ✓ Proximity sensor enabled");
            
            // Set proximity gain to maximum (8X) for better range
            if (apds.setProximityGain(PGAIN_8X)) {
                Serial.println("  ✓ Proximity gain set to 8X");
                
                // Set LED drive strength to maximum (100mA)
                if (apds.setLEDDrive(LED_DRIVE_100MA)) {
                    Serial.println("  ✓ LED drive set to 100mA");
                    
                    // Read the proximity gain to verify
                    uint8_t gain = apds.getProximityGain();
                    Serial.print("  ✓ Verified proximity gain: ");
                    Serial.println(gain);
                    Serial.println("\nSensor setup complete!");
                    return true;
                } else {
                    Serial.println("  ✗ Failed to set LED drive!");
                }
            } else {
                Serial.println("  ✗ Failed to set proximity gain!");
            }
        } else {
            Serial.println("  ✗ Failed to enable proximity sensor!");
        }
    } else {
        Serial.println("  ✗ Sensor initialization failed!");
        Serial.println("  Please check your connections and power supply");
    }
    return false;
}

void setup() {
    // Wait for serial connection
    delay(2000);
    
    // Initialize Serial port
    Serial.begin(115200);
    Serial.println("\n----------------------------------------");
    Serial.println("APDS-9930 Proximity Sensor Test Program");
    Serial.println("----------------------------------------");
    
    // Initialize LEDs
    Serial.println("\nInitializing LEDs...");
    pinMode(POWER_PIN, OUTPUT);
    digitalWrite(POWER_PIN, HIGH);  // Enable 5V power supply
    FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
    
    // Turn on all LEDs with initial color
    fill_solid(leds, NUM_LEDS, CHSV(hue, 255, 255));
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
    
    // Keep trying to initialize the sensor until it succeeds
    bool sensorInitialized = false;
    while (!sensorInitialized) {
        sensorInitialized = initializeSensor();
        if (!sensorInitialized) {
            Serial.println("\nRetrying sensor initialization in 1 second...");
            delay(1000);
        }
    }
    
    Serial.println("\nStarting LED animation and sensor monitoring...");
}

void loop() {
    static unsigned long lastPrintTime = 0;
    unsigned long currentTime = millis();
    
    // Read proximity value continuously
    uint16_t proximity = 0;
    if (apds.readProximity(proximity)) {
        // Map proximity to hue (0-255)
        // Higher proximity = closer object = different color
        uint8_t newHue = map(proximity, 0, 1023, 0, 255);
        
        // Update LEDs with new color
        fill_solid(leds, NUM_LEDS, CHSV(newHue, 255, 255));
        FastLED.show();
        
        // Print proximity value every 500ms instead of 2000ms
        if (currentTime - lastPrintTime >= 500) {
            Serial.print("\nProximity: ");
            Serial.println(proximity);
            lastPrintTime = currentTime;
        }
    } else {
        Serial.println("Error reading proximity!");
    }
    
    // Remove the delay to make readings faster
    // delay(50);
}