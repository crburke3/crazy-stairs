#!/usr/bin/env python3

import time
from rpi_ws281x import PixelStrip, Color

# LED strip configuration
LED_COUNT = 300        # Number of LED pixels
LED_PIN = 18          # GPIO18 (PWM0) - DO NOT use TXD/GPIO14
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_CHANNEL = 0       # PWM channel (0 for GPIO18, 1 for GPIO13)
LED_INVERT = False    # True to invert the signal

def main():
    print("Initializing LED strip...")
    print("NOTE: WS2812B LEDs must be connected to GPIO18 (PWM0), not TXD/GPIO14")
    print("Please ensure your LED data line is connected to GPIO18")
    
    # Create NeoPixel object with appropriate configuration
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    
    # Initialize the library (must be called once before other functions)
    strip.begin()
    
    try:
        print("\nStarting LED test pattern...")
        while True:
            # Test pattern: Red -> Green -> Blue -> Off
            print("Setting all LEDs to RED")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(255, 0, 0))
            strip.show()
            time.sleep(2)
            
            print("Setting all LEDs to GREEN")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(0, 255, 0))
            strip.show()
            time.sleep(2)
            
            print("Setting all LEDs to BLUE")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(0, 0, 255))
            strip.show()
            time.sleep(2)
            
            print("Turning off all LEDs")
            for i in range(strip.numPixels()):
                strip.setPixelColor(i, Color(0, 0, 0))
            strip.show()
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\nExiting...")
        # Turn off all LEDs
        for i in range(strip.numPixels()):
            strip.setPixelColor(i, Color(0, 0, 0))
        strip.show()

if __name__ == "__main__":
    main() 