#include <FastLED.h>
#include <Arduino.h>
#include <Wire.h>
#include "vl53l0x_multiplexer.h"
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>

// I2C Pin Configuration
#define I2C_SDA 21
#define I2C_SCL 22

// Stair Configuration
#define STAIR_LENGTH 30    // Number of LEDs per stair
#define NUM_STAIRS 8      // Total number of stairs
#define NUM_LEDS (STAIR_LENGTH * NUM_STAIRS)  // Total number of LEDs

// LED Configuration
#define DATA_PIN 16
#define POWER_PIN 12
#define TRIGGER_DISTANCE 740  // Distance in mm to trigger LED section 
#define FADE_DURATION 700  // Duration in ms for fade out (reduced from 2000ms to 1000ms)
#define STATUS_CHECK_INTERVAL 10000  // Check status every 10 seconds
#define DISTANCE_LOG_INTERVAL 5000    // Log distances every 5 seconds
#define LED_FRAME_UPDATE_INTERVAL 1    // Update LEDs every 3ms for smoother animation (16 = 60fps, 3 = 330fps)
#define SENSOR_CHECK_INTERVAL 50  // Check sensors every 100ms

// Add these constants at the top with other defines
#define I2C_FREQUENCY 100000  // 100kHz instead of default 100kHz
#define I2C_TIMEOUT 1000      // 1 second timeout
#define I2C_RETRY_DELAY 50    // 50ms between retries
#define MAX_I2C_RETRIES 3     // Maximum number of retries per read

// Animation Mode Enum
enum AnimationMode {
    IMPACT_FADE,
    CASCADE_FADE,
    GRADIENT_FADE,
    POLICE_LIGHTS,
    // Add more modes here as needed
    NUM_ANIMATION_MODES
};

// Animation Mode Names
const char* ANIMATION_MODE_NAMES[] = {
    "Impact Fade",
    "Cascade Fade",
    "Gradient Fade",
    "Police Lights",
    // Add more mode names here
};

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
    bool isAdjacent;    // Track if this section is an adjacent section
};

// Global Variables
VL53L0XMultiplexer* sensorMux1 = nullptr;
CRGB leds[NUM_LEDS];
unsigned long lastStatusCheck = 0;
unsigned long lastDistanceLog = 0;
bool multiplexerConnected = false;
LEDSection* sections = nullptr;  // Will be dynamically allocated
int numSections = 0;  // Will be set based on number of stairs
AnimationMode currentMode = CASCADE_FADE;  // Current animation mode

// Mutex for protecting shared resources
SemaphoreHandle_t ledMutex = NULL;

// Task handles
TaskHandle_t sensorTaskHandle = NULL;
TaskHandle_t ledTaskHandle = NULL;

// Add these global variables at the top with other globals
unsigned long lastI2CError = 0;
const unsigned long I2C_ERROR_RECOVERY_TIME = 1000; // 1 second recovery time
int consecutiveI2CErrors = 0;
const int MAX_CONSECUTIVE_ERRORS = 5;

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
            CRGB::Black,                // targetColor
            false                       // isAdjacent
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
        Serial.print("Attempting to initialize sensor on channel ");
        Serial.println(channel);
        
        // First check if we can communicate with the sensor
        Wire.beginTransmission(0x29);  // VL53L0X default address
        uint8_t error = Wire.endTransmission();
        
        if (error == 0) {
            Serial.print("Found VL53L0X on channel ");
            Serial.println(channel);
            sections[channel].isConnected = true;
            
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
        } else {
            Serial.print("No VL53L0X found on channel ");
            Serial.println(channel);
            sections[channel].isConnected = false;
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
                    sections[i].isInitialized = false;
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
                            
                            // Map the channel to a section if possible
                            if (channel < numSections) {
                                sections[channel].isConnected = true;
                                // Initialize the sensor if it's newly connected
                                if (!sections[channel].isInitialized) {
                                    initializeSensorChannel(channel);
                                }
                            } else {
                                Serial.print("  Warning: Channel ");
                                Serial.print(channel);
                                Serial.println(" has a sensor but no corresponding LED section");
                            }
                        } else {
                            Serial.print("  Channel ");
                            Serial.print(channel);
                            Serial.println(": No VL53L0X sensor");
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
    
    // Print final connection status
    Serial.println("\nFinal Sensor Status:");
    for (int i = 0; i < numSections; i++) {
        Serial.print("Section ");
        Serial.print(i);
        Serial.print(": ");
        if (sections[i].isConnected) {
            Serial.print("Connected");
            if (sections[i].isInitialized) {
                Serial.println(" and Initialized");
            } else {
                Serial.println(" but Not Initialized");
            }
        } else {
            Serial.println("Not Connected");
        }
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

// Animation Mode Functions
namespace AnimationModes {
    // Impact Fade Mode
    void updateImpactFade(LEDSection& section) {
        if (section.isActive) {
            unsigned long elapsed = millis() - section.triggerTime;
            if (elapsed >= FADE_DURATION) {
                section.isActive = false;
                section.brightness = 0;
            } else {
                section.brightness = easeOutQuad(elapsed, FADE_DURATION);
                uint8_t colorBlend = 255 - section.brightness;
                
                for (int i = section.startIndex; i < section.endIndex; i++) {
                    leds[i] = blendColors(CRGB::White, section.targetColor, colorBlend);
                    leds[i].nscale8_video(section.brightness);
                }
            }
        } else {
            for (int i = section.startIndex; i < section.endIndex; i++) {
                leds[i] = CRGB::Black;
            }
        }
    }

    // Cascade Fade Mode
    void updateCascadeFade(LEDSection& section) {
        if (section.isActive) {
            unsigned long elapsed = millis() - section.triggerTime;
            if (elapsed >= FADE_DURATION) {
                section.isActive = false;
                section.brightness = 0;
                section.isAdjacent = false;
            } else {
                // Calculate brightness based on whether it's the main section or adjacent
                if (section.isAdjacent) {
                    // Adjacent sections fade at 50% brightness
                    section.brightness = easeOutQuad(elapsed, FADE_DURATION) / 2;
                } else {
                    // Main section fades at full brightness
                    section.brightness = easeOutQuad(elapsed, FADE_DURATION);
                }
                
                uint8_t colorBlend = 255 - section.brightness;
                
                for (int i = section.startIndex; i < section.endIndex; i++) {
                    leds[i] = blendColors(CRGB::White, section.targetColor, colorBlend);
                    leds[i].nscale8_video(section.brightness);
                }
            }
        } else {
            for (int i = section.startIndex; i < section.endIndex; i++) {
                leds[i] = CRGB::Black;
            }
        }
    }
}

// Function to generate a random gradient
void generateRandomGradient(CRGB* gradient, int length) {
    // Generate two random colors for the gradient
    CRGB color1 = getRandomColor();
    CRGB color2 = getRandomColor();
    
    // Create gradient between the two colors
    for (int i = 0; i < length; i++) {
        uint8_t blend = map(i, 0, length - 1, 0, 255);
        gradient[i] = blendColors(color1, color2, blend);
    }
}

// Function to handle section updates based on current mode
void updateSection(LEDSection& section) {
    if (currentMode >= NUM_ANIMATION_MODES) {
        currentMode = IMPACT_FADE;  // Reset to first mode if invalid
    }
    
    switch (currentMode) {
        case IMPACT_FADE:
            AnimationModes::updateImpactFade(section);
            break;
        case CASCADE_FADE:
            AnimationModes::updateCascadeFade(section);
            break;
        case GRADIENT_FADE:
            if (section.isActive) {
                unsigned long elapsed = millis() - section.triggerTime;
                if (elapsed >= FADE_DURATION) {
                    section.isActive = false;
                    section.brightness = 0;
                    // Keep a dim glow for debugging
                    for (int i = section.startIndex; i < section.endIndex; i++) {
                        leds[i] = CRGB(5, 5, 5);  // Very dim white
                    }
                } else {
                    uint8_t fade = easeOutQuad(elapsed, FADE_DURATION);
                    for (int i = section.startIndex; i < section.endIndex; i++) {
                        leds[i].nscale8_video(fade);
                    }
                }
            } else {
                // Keep a dim glow for debugging
                for (int i = section.startIndex; i < section.endIndex; i++) {
                    leds[i] = CRGB(5, 5, 5);  // Very dim white
                }
            }
            break;
        case POLICE_LIGHTS:
            if (section.isActive) {
                unsigned long elapsed = millis() - section.triggerTime;
                if (elapsed >= FADE_DURATION) {
                    section.isActive = false;
                    section.brightness = 0;
                    // Keep a dim glow for debugging
                    for (int i = section.startIndex; i < section.endIndex; i++) {
                        leds[i] = CRGB(5, 5, 5);  // Very dim white
                    }
                } else {
                    // Flash between red and blue
                    bool isRed = (elapsed / 100) % 2 == 0;  // Switch every 100ms
                    CRGB color = isRed ? CRGB::Red : CRGB::Blue;
                    
                    // Apply color to all LEDs in section
                    for (int i = section.startIndex; i < section.endIndex; i++) {
                        leds[i] = color;
                    }
                }
            } else {
                // Keep a dim glow for debugging
                for (int i = section.startIndex; i < section.endIndex; i++) {
                    leds[i] = CRGB(5, 5, 5);  // Very dim white
                }
            }
            break;
        case NUM_ANIMATION_MODES:
            // This case should never be reached due to the check above
            break;
    }
}

// Function to handle section triggers based on current mode
void handleSectionTrigger(LEDSection& section, int sectionIndex) {
    // If section 1 (index 0) is triggered, change animation mode
    if (sectionIndex == 0) {
        currentMode = (AnimationMode)((currentMode + 1) % NUM_ANIMATION_MODES);
        Serial.print("Section 1 triggered - changing to mode: ");
        Serial.println(ANIMATION_MODE_NAMES[currentMode]);
    }
    
    if (currentMode >= NUM_ANIMATION_MODES) {
        currentMode = IMPACT_FADE;  // Reset to first mode if invalid
    }
    
    // Common setup for all modes
    section.isActive = true;
    section.triggerTime = millis();
    section.brightness = 255;
    
    switch (currentMode) {
        case IMPACT_FADE: {
            section.targetColor = getRandomColor();
            
            // Log the trigger and color information
            Serial.print("Sensor ");
            Serial.print(sectionIndex);
            Serial.print(" triggered! Fading to color: ");
            Serial.println(colorToHex(section.targetColor));
            
            // Set all LEDs in section to white at full brightness
            for (int i = section.startIndex; i < section.endIndex; i++) {
                leds[i] = CRGB::White;
            }
            break;
        }
            
        case CASCADE_FADE: {
            // Activate the main section
            section.isAdjacent = false;
            section.targetColor = getRandomColor();
            
            // Log the trigger and color information
            Serial.print("Sensor ");
            Serial.print(sectionIndex);
            Serial.print(" triggered! Cascade fading to color: ");
            Serial.println(colorToHex(section.targetColor));
            
            // Set all LEDs in main section to white at full brightness
            for (int i = section.startIndex; i < section.endIndex; i++) {
                leds[i] = CRGB::White;
            }
            
            // Activate previous section if it exists
            if (sectionIndex > 0 && sections[sectionIndex - 1].isConnected) {
                sections[sectionIndex - 1].isActive = true;
                sections[sectionIndex - 1].isAdjacent = true;
                sections[sectionIndex - 1].triggerTime = millis();
                sections[sectionIndex - 1].brightness = 128; // 50% brightness
                sections[sectionIndex - 1].targetColor = section.targetColor;
                
                // Set previous section LEDs to white at 50% brightness
                for (int i = sections[sectionIndex - 1].startIndex; i < sections[sectionIndex - 1].endIndex; i++) {
                    leds[i] = CRGB::White;
                    leds[i].nscale8(128);
                }
            }
            
            // Activate next section if it exists
            if (sectionIndex < numSections - 1 && sections[sectionIndex + 1].isConnected) {
                sections[sectionIndex + 1].isActive = true;
                sections[sectionIndex + 1].isAdjacent = true;
                sections[sectionIndex + 1].triggerTime = millis();
                sections[sectionIndex + 1].brightness = 128; // 50% brightness
                sections[sectionIndex + 1].targetColor = section.targetColor;
                
                // Set next section LEDs to white at 50% brightness
                for (int i = sections[sectionIndex + 1].startIndex; i < sections[sectionIndex + 1].endIndex; i++) {
                    leds[i] = CRGB::White;
                    leds[i].nscale8(128);
                }
            }
            break;
        }
            
        case GRADIENT_FADE: {
            // Generate random gradient for this section
            CRGB gradient[STAIR_LENGTH];
            generateRandomGradient(gradient, STAIR_LENGTH);
            
            // Apply gradient to section
            for (int i = 0; i < STAIR_LENGTH; i++) {
                leds[section.startIndex + i] = gradient[i];
            }
            
            Serial.print("Sensor ");
            Serial.print(sectionIndex);
            Serial.println(" triggered! Applied random gradient");
            break;
        }
            
        case POLICE_LIGHTS: {
            // Start with red
            for (int i = section.startIndex; i < section.endIndex; i++) {
                leds[i] = CRGB::Red;
            }
            
            Serial.print("Sensor ");
            Serial.print(sectionIndex);
            Serial.println(" triggered! Police lights activated");
            break;
        }
            
        case NUM_ANIMATION_MODES:
            // This case should never be reached due to the check above
            break;
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
        if (sections[i].isConnected && sections[i].isInitialized) {
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
        } else if (sections[i].isConnected) {
            Serial.print("S");
            Serial.print(i);
            Serial.print(":UNINIT ");
        }
    }

    if (!anySensorRead) {
        Serial.print("No sensors connected");
    }
    Serial.println();
}

// Add this new function for robust I2C recovery
void recoverI2CBus() {
    Serial.println("Performing full I2C bus recovery...");
    
    // 1. End I2C communication
    Wire.end();
    delay(100);
    
    // 2. Reset pins to default state
    pinMode(I2C_SDA, INPUT);
    pinMode(I2C_SCL, INPUT);
    delay(100);
    
    // 3. Manually clock the bus to clear any stuck devices
    pinMode(I2C_SCL, OUTPUT);
    for(int i = 0; i < 10; i++) {
        digitalWrite(I2C_SCL, HIGH);
        delayMicroseconds(5);
        digitalWrite(I2C_SCL, LOW);
        delayMicroseconds(5);
    }
    
    // 4. Re-enable pull-ups and restart I2C
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    delay(100);
    
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(I2C_FREQUENCY);
    Wire.setTimeout(I2C_TIMEOUT);
    
    // 5. Reinitialize multiplexer if it exists
    if (sensorMux1 != nullptr) {
        if (sensorMux1->begin()) {
            Serial.println("Multiplexer reinitialized successfully");
            // Reinitialize all connected sensors
            for (uint8_t channel = 0; channel < 8; channel++) {
                if (sections[channel].isConnected) {
                    if (sensorMux1->initSensor(channel, 0)) {
                        Serial.print("Reinitialized sensor on channel ");
                        Serial.println(channel);
                    }
                }
            }
        } else {
            Serial.println("Failed to reinitialize multiplexer");
        }
    }
}

// Modify the sensorTask function
void sensorTask(void *pvParameters) {
    while (1) {
        // Check multiplexer status every 10 seconds or after I2C errors
        if (millis() - lastStatusCheck >= STATUS_CHECK_INTERVAL || consecutiveI2CErrors >= MAX_CONSECUTIVE_ERRORS) {
            Serial.println("\nRestarting sensor scan due to timeout or errors...");
            checkMultiplexerStatus();
            lastStatusCheck = millis();
            consecutiveI2CErrors = 0;  // Reset error counter after scan
        }

        // Log distances every 5 seconds
        if (millis() - lastDistanceLog >= DISTANCE_LOG_INTERVAL) {
            logSensorDistances();
            lastDistanceLog = millis();
        }

        // Check sensor distances
        if (multiplexerConnected && sensorMux1 != nullptr) {
            // Process each section
            for (int section = 0; section < numSections; section++) {
                if (sections[section].isConnected && sections[section].isInitialized) {
                    uint16_t distance = 0;
                    bool readSuccess = false;
                    
                    // Try multiple times to read the sensor
                    for (int retry = 0; retry < MAX_I2C_RETRIES && !readSuccess; retry++) {
                        if (retry > 0) {
                            delay(I2C_RETRY_DELAY);
                        }
                        
                        readSuccess = sensorMux1->readDistance(section, distance);
                        
                        if (readSuccess) {
                            consecutiveI2CErrors = 0;
                            
                            if (distance == 65535) {
                                Serial.print("Sensor on channel ");
                                Serial.print(section);
                                Serial.println(" disconnected!");
                                sections[section].isConnected = false;
                                sections[section].isInitialized = false;
                                
                                if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdTRUE) {
                                    for (int i = sections[section].startIndex; i < sections[section].endIndex; i++) {
                                        leds[i] = CRGB::Black;
                                    }
                                    xSemaphoreGive(ledMutex);
                                }
                            } else if (distance < TRIGGER_DISTANCE) {
                                handleSectionTrigger(sections[section], section);
                            }
                            break;
                        }
                    }
                    
                    if (!readSuccess) {
                        consecutiveI2CErrors++;
                        lastI2CError = millis();
                        
                        if (consecutiveI2CErrors == 1) {
                            Serial.print("I2C read error on channel ");
                            Serial.println(section);
                        }
                        
                        // If we've hit the error threshold, break out of the loop
                        // The next iteration will trigger a full rescan
                        if (consecutiveI2CErrors >= MAX_CONSECUTIVE_ERRORS) {
                            break;
                        }
                    }
                }
            }
        }
        
        vTaskDelay(pdMS_TO_TICKS(SENSOR_CHECK_INTERVAL));
    }
}

// LED update task
void ledTask(void *pvParameters) {
    while (1) {
        if (xSemaphoreTake(ledMutex, portMAX_DELAY) == pdTRUE) {
            // Update all sections based on current mode
            for (int section = 0; section < numSections; section++) {
                if (sections[section].isConnected) {
                    updateSection(sections[section]);
                }
            }
            
            FastLED.show();
            xSemaphoreGive(ledMutex);
        }
        
        vTaskDelay(pdMS_TO_TICKS(LED_FRAME_UPDATE_INTERVAL));
    }
}

// Function to change animation mode
void setAnimationMode(AnimationMode mode) {
    if (mode < NUM_ANIMATION_MODES) {
        currentMode = mode;
        Serial.print("Animation mode changed to: ");
        Serial.println(ANIMATION_MODE_NAMES[mode]);
    }
}

void setup() {
    // Initialize Serial for debugging
    Serial.begin(115200);
    delay(4000);
    Serial.println("Starting Crazy Stairs...");
    
    // Initialize random seed
    random16_set_seed(analogRead(0));
    
    // Create mutex for LED access
    ledMutex = xSemaphoreCreateMutex();
    
    // Initialize I2C with custom configuration
    Wire.begin(I2C_SDA, I2C_SCL);
    Wire.setClock(I2C_FREQUENCY);
    Wire.setTimeout(I2C_TIMEOUT);
    
    // Enable internal pull-up resistors
    pinMode(I2C_SDA, INPUT_PULLUP);
    pinMode(I2C_SCL, INPUT_PULLUP);
    
    // Initialize LED power pin
    pinMode(POWER_PIN, OUTPUT);
    digitalWrite(POWER_PIN, HIGH);
    
    // Initialize FastLED
    FastLED.addLeds<WS2812B, DATA_PIN, GRB>(leds, NUM_LEDS);
    FastLED.setBrightness(255);
    FastLED.clear();
    
    // LED Test Sequence
    Serial.println("\nRunning LED Test Sequence...");
    
    // Turn all LEDs white
    Serial.println("Testing all LEDs - White");
    fill_solid(leds, NUM_LEDS, CRGB::White);
    FastLED.show();
    delay(1000);
    
    // Turn all LEDs red
    Serial.println("Testing all LEDs - Red");
    fill_solid(leds, NUM_LEDS, CRGB::Red);
    FastLED.show();
    delay(1000);
    
    // Turn all LEDs green
    Serial.println("Testing all LEDs - Green");
    fill_solid(leds, NUM_LEDS, CRGB::Green);
    FastLED.show();
    delay(1000);
    
    // Turn all LEDs blue
    Serial.println("Testing all LEDs - Blue");
    fill_solid(leds, NUM_LEDS, CRGB::Blue);
    FastLED.show();
    delay(1000);
    
    // Clear all LEDs
    Serial.println("LED Test Complete");
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
        sensorMux1 = new VL53L0XMultiplexer(muxAddr);
        if (sensorMux1->begin()) {
            Serial.println("Initializing all detected sensors...");
            // First check which sensors are connected
            checkMultiplexerStatus();
            
            // Then initialize only the connected sensors
            for (uint8_t channel = 0; channel < 8; channel++) {
                if (sections[channel].isConnected) {
                    initializeSensorChannel(channel);
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
    
    // Create tasks
    xTaskCreatePinnedToCore(
        sensorTask,    // Task function
        "SensorTask",  // Task name
        10000,        // Stack size
        NULL,         // Task parameters
        1,            // Task priority
        &sensorTaskHandle,  // Task handle
        0             // Run on core 0
    );
    
    xTaskCreatePinnedToCore(
        ledTask,      // Task function
        "LEDTask",    // Task name
        10000,        // Stack size
        NULL,         // Task parameters
        2,            // Task priority
        &ledTaskHandle,  // Task handle
        1             // Run on core 1
    );
    
    Serial.println("Setup complete!");
}

void loop() {
    // Main loop is empty as tasks handle everything
    vTaskDelay(pdMS_TO_TICKS(1000));
}