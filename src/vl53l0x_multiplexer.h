#ifndef VL53L0X_MULTIPLEXER_H
#define VL53L0X_MULTIPLEXER_H

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wreorder"

#include <Wire.h>
#include <Adafruit_I2CDevice.h>
#include <Adafruit_VL53L0X.h>

struct VL53L0XSensor {
    Adafruit_VL53L0X sensor;
    bool initialized;
    uint8_t address;
};

class VL53L0XMultiplexer {
public:
    VL53L0XMultiplexer(uint8_t tcaAddress);
    ~VL53L0XMultiplexer();

    bool begin();
    bool selectChannel(uint8_t channel);
    bool initSensor(uint8_t channel, uint8_t address);
    bool readDistance(uint8_t channel, uint16_t &distance);
    void setAddress(uint8_t channel, uint8_t address);

private:
    VL53L0XSensor sensors[8];
    uint8_t tcaAddress;
    Adafruit_I2CDevice* tca;
};

#pragma GCC diagnostic pop

#endif 