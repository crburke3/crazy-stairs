# VL53L0X Distance Sensor Array

This project implements a Python interface for multiple VL53L0X time-of-flight distance sensors connected through a TCA9548A I2C multiplexer.

## Hardware Requirements

- Raspberry Pi
- TCA9548A I2C Multiplexer
- Up to 8 VL53L0X Distance Sensors
- I2C connections (SDA, SCL)

## Installation

1. Enable I2C on your Raspberry Pi:
```bash
sudo raspi-config
# Navigate to Interface Options -> I2C -> Enable
```

2. Install required packages:
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3-pip i2c-tools

# Install Python dependencies
pip3 install -r requirements.txt
```

## Usage

1. Connect your hardware:
   - Connect TCA9548A to Raspberry Pi's I2C bus (SDA, SCL)
   - Connect VL53L0X sensors to TCA9548A channels
   - Power all devices appropriately

2. Run the example program:
```bash
python3 main.py
```

The program will:
- Initialize the TCA9548A multiplexer
- Initialize all connected VL53L0X sensors
- Continuously read and display distances from all sensors
- Press Ctrl+C to exit

## Customization

You can modify the following parameters in `vl53l0x_multiplexer.py`:
- TCA9548A I2C address (default: 0x70)
- Measurement timing budget
- Reading interval

## Troubleshooting

1. Check I2C connections:
```bash
sudo i2cdetect -y 1
```

2. Verify permissions:
```bash
sudo usermod -aG i2c $USER
```

3. Common issues:
   - If sensors not detected, check wiring and power
   - If readings are unstable, adjust timing budget
   - If getting I2C errors, check bus connections 