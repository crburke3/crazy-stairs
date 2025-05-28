#!/usr/bin/env python3

import time
import board
import busio
from adafruit_tca9548a import TCA9548A

def main():
    print("Initializing I2C bus...")
    i2c = busio.I2C(board.SCL, board.SDA)
    
    print("\nScanning I2C bus for devices before multiplexer initialization:")
    devices = i2c.scan()
    for device in devices:
        print(f"Found device at address 0x{device:02x}")
    
    print("\nInitializing TCA9548A multiplexer...")
    tca = TCA9548A(i2c, address=0x70)
    
    # First, write to multiplexer to disable all channels
    print("\nDisabling all multiplexer channels...")
    i2c.try_lock()
    try:
        i2c.writeto(0x70, bytes([0x00]))
    finally:
        i2c.unlock()
    
    print("\nTesting each multiplexer channel in isolation:")
    for channel in range(8):
        print(f"\nChannel {channel}:")
        
        # Enable only this channel
        i2c.try_lock()
        try:
            i2c.writeto(0x70, bytes([1 << channel]))
            print(f"  Enabled channel {channel} (wrote {1 << channel:08b})")
            
            # Try to communicate with VL53L0X
            try:
                # Try to read VL53L0X ID registers
                i2c.writeto(0x29, bytes([0xC0]), stop=False)
                result = bytearray(1)
                i2c.readfrom_into(0x29, result)
                print(f"  VL53L0X ID register 0xC0 = 0x{result[0]:02x}")
                
                i2c.writeto(0x29, bytes([0xC1]), stop=False)
                i2c.readfrom_into(0x29, result)
                print(f"  VL53L0X ID register 0xC1 = 0x{result[0]:02x}")
                
                i2c.writeto(0x29, bytes([0xC2]), stop=False)
                i2c.readfrom_into(0x29, result)
                print(f"  VL53L0X ID register 0xC2 = 0x{result[0]:02x}")
                
            except Exception as e:
                print(f"  Failed to read VL53L0X: {str(e)}")
            
            # Scan for all devices on this channel
            print("  Scanning for devices:")
            for addr in range(0x08, 0x78):
                try:
                    i2c.writeto(addr, bytes([0]))
                    print(f"    Found device at address 0x{addr:02x}")
                except:
                    pass
                    
        finally:
            i2c.unlock()
        
        # Disable all channels again
        i2c.try_lock()
        try:
            i2c.writeto(0x70, bytes([0x00]))
            print("  Disabled all channels")
        finally:
            i2c.unlock()
            
        # Small delay between tests
        time.sleep(0.1)

if __name__ == "__main__":
    main() 