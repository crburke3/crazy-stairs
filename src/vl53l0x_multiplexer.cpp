#include "vl53l0x_multiplexer.h"

VL53L0XMultiplexer::VL53L0XMultiplexer(uint8_t tcaAddress) 
    : sensors{}, tcaAddress(tcaAddress), tca(nullptr) {
    for (int i = 0; i < 8; i++) {
        sensors[i].initialized = false;
    }
}

VL53L0XMultiplexer::~VL53L0XMultiplexer() {
    if (tca != nullptr) {
        delete tca;
    }
}

bool VL53L0XMultiplexer::begin() {
    Serial.print("Initializing TCA9548A at address 0x");
    Serial.println(tcaAddress, HEX);
    
    tca = new Adafruit_I2CDevice(tcaAddress);
    if (!tca->begin()) {
        Serial.println("  ✗ Failed to initialize TCA9548A - Check wiring and address");
        return false;
    }
    
    // Test communication with TCA9548A
    uint8_t data = 0;
    if (!tca->write(&data, 1)) {
        Serial.println("  ✗ Failed to write to TCA9548A - Check I2C connection");
        return false;
    }
    
    Serial.println("  ✓ TCA9548A initialized and responding");
    return true;
}

bool VL53L0XMultiplexer::selectChannel(uint8_t channel) {
    if (channel >= 8) {
        Serial.print("  ✗ Invalid channel number: ");
        Serial.println(channel);
        return false;
    }
    
    // First, disable all channels
    uint8_t disableData = 0x00;
    if (!tca->write(&disableData, 1)) {
        Serial.print("  ✗ Failed to disable all channels");
        return false;
    }
    delay(1);  // Small delay to ensure channels are disabled
    
    // Then enable only the requested channel
    uint8_t data = 1 << channel;
    if (!tca->write(&data, 1)) {
        Serial.print("  ✗ Failed to select channel ");
        Serial.println(channel);
        return false;
    }
    delay(1);  // Small delay to ensure channel is enabled
    
    // Verify the channel was actually selected
    uint8_t readData = 0;
    if (!tca->read(&readData, 1)) {
        Serial.print("  ✗ Failed to read back channel selection for channel ");
        Serial.println(channel);
        return false;
    }
    
    if (readData != data) {
        Serial.print("  ✗ Channel selection verification failed. Expected: ");
        Serial.print(data, BIN);
        Serial.print(" Got: ");
        Serial.println(readData, BIN);
        return false;
    }
    
    return true;
}

bool VL53L0XMultiplexer::initSensor(uint8_t channel, uint8_t address) {
    if (channel >= 8) {
        Serial.print("  ✗ Invalid channel number: ");
        Serial.println(channel);
        return false;
    }

    // Select the channel
    if (!selectChannel(channel)) {
        return false;
    }

    // Initialize the sensor
    if (!sensors[channel].sensor.begin()) {
        Serial.print("  ✗ Failed to initialize VL53L0X on channel ");
        Serial.println(channel);
        return false;
    }

    // Start continuous ranging
    sensors[channel].sensor.startRangeContinuous();
    sensors[channel].initialized = true;
    return true;
}

bool VL53L0XMultiplexer::readDistance(uint8_t channel, uint16_t &distance) {
    if (channel >= 8 || !sensors[channel].initialized) {
        return false;
    }

    // Select the channel and wait a bit for it to settle
    if (!selectChannel(channel)) {
        return false;
    }
    delay(10);  // Increased delay to ensure channel selection has settled

    // Read the distance
    distance = sensors[channel].sensor.readRange();

    // Check if the sensor is still connected
    if (sensors[channel].sensor.timeoutOccurred()) {
        return false;
    }

    return true;
}

void VL53L0XMultiplexer::setAddress(uint8_t channel, uint8_t address) {
    if (channel >= 8) {
        Serial.print("  ✗ Invalid channel number: ");
        Serial.println(channel);
        return;
    }

    Serial.print("Setting new address 0x");
    Serial.print(address, HEX);
    Serial.print(" for channel ");
    Serial.println(channel);

    // Select the channel
    if (!selectChannel(channel)) {
        return;
    }

    // Set the new address
    sensors[channel].sensor.setAddress(address);
    sensors[channel].address = address;
    Serial.println("  ✓ Address set successfully");
} 