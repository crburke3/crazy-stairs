#!/usr/bin/env python3

import time
from vl53l0x_multiplexer import VL53L0XMultiplexer
from rpi_ws281x import PixelStrip, Color
from bluetooth_audio import setup_bluetooth_audio
import os
import colorsys

# LED strip configuration
LED_COUNT = 1000        # Number of LED pixels
LED_PIN = 18          # GPIO18 (PWM0) - DO NOT use TXD/GPIO14
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_CHANNEL = 0       # PWM channel (0 for GPIO18, 1 for GPIO13)
LED_INVERT = False    # True to invert the signal

# Distance configuration (in millimeters)
MAX_DISTANCE = 2000.0  # Distance at which LED starts to change color (2 meters)
MIN_DISTANCE = 200.0   # Distance at which LED reaches maximum intensity
TRIGGER_DISTANCE = 685.8  # 27 inches in mm - when to consider "triggered"

# LED segments for each stair (adjust these numbers based on your setup)
LEDS_PER_STAIR = 30  # Assuming 30 LEDs per stair
STAIR_SEGMENTS = {
    1: (0, 29),      # First stair: LEDs 0-29
    4: (30, 59),     # Second stair: LEDs 30-59
    # Add more stairs as needed, matching your sensor channels
}

# Sound configuration
SOUND_FILE = "stair_trigger.wav"  # Sound file to play when triggered
SOUND_COOLDOWN = 2.0  # Minimum time between sound triggers in seconds

def init_led_strip():
    """Initialize the LED strip."""
    print("NOTE: WS2812B LEDs must be connected to GPIO18 (PWM0), not TXD/GPIO14")
    print("Please ensure your LED data line is connected to GPIO18")
    strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    strip.begin()
    return strip

def get_color_from_distance(distance):
    """
    Convert distance to color with smooth transition.
    Blue (far) -> Purple -> Red (near)
    Returns Color object
    """
    # Clamp distance between MIN_DISTANCE and MAX_DISTANCE
    distance = max(MIN_DISTANCE, min(distance, MAX_DISTANCE))
    
    # Calculate intensity (0.0 to 1.0)
    intensity = 1.0 - ((distance - MIN_DISTANCE) / (MAX_DISTANCE - MIN_DISTANCE))
    
    # Create smooth transition from blue to red
    red = int(255 * intensity)
    blue = int(255 * (1.0 - intensity))
    green = 0  # Keep green at 0 for more vibrant colors
    
    return Color(red, green, blue)

def set_all_stair_lights(strip, color):
    """Set all stair lights to the same color."""
    for segment_start, segment_end in STAIR_SEGMENTS.values():
        for i in range(segment_start, segment_end + 1):
            strip.setPixelColor(i, color)

def clear_all_lights(strip):
    """Turn off all LEDs."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 0))
    strip.show()

def rainbow_fade(strip):
    """Fade all LEDs through a smooth rainbow effect."""
    while True:
        for i in range(strip.numPixels()):
            hue = (i / strip.numPixels() + time.time() * 0.1) % 1.0
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
            strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(0.01)

def main():
    # Create multiplexer instance
    print("Initializing VL53L0X multiplexer...")
    multiplexer = VL53L0XMultiplexer()
    
    # Initialize LED strip
    print("Initializing LED strip...")
    strip = init_led_strip()
    clear_all_lights(strip)
    
    # Test LED strip with a simple pattern
    print("\nTesting LED strip...")
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(255, 0, 0))  # Set all LEDs to red
    strip.show()
    time.sleep(1)
    
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 255, 0))  # Set all LEDs to green
    strip.show()
    time.sleep(1)
    
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0, 0, 255))  # Set all LEDs to blue
    strip.show()
    time.sleep(1)
    
    # Set up Bluetooth audio
    print("\nSetting up Bluetooth audio...")
    bt_audio = setup_bluetooth_audio()
    if bt_audio:
        # Set the sound file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sound_path = os.path.join(script_dir, SOUND_FILE)
        if not os.path.exists(sound_path):
            print(f"Warning: Sound file {sound_path} not found")
            print("Please place an MP3 file named 'stair_trigger.mp3' in the same directory")
        else:
            bt_audio.set_sound_file(sound_path)
    
    last_update = time.time()
    last_sound_trigger = 0  # Track last time sound was played
    was_triggered = False  # Track if sensor was previously triggered
    update_interval = 0.02  # 20ms refresh rate (50Hz)
    sensor_retry_interval = 5.0  # How often to retry initializing sensors
    last_sensor_init = 0
    active_sensors = []  # List of working sensor channel numbers
    current_sensor_idx = 0  # Index into active_sensors for round-robin reading
    
    print("\nInitializing sensors...")
    
    try:
        while True:
            current_time = time.time()
            
            # Try to initialize sensors if we don't have any working ones
            if len(active_sensors) == 0 and current_time - last_sensor_init >= sensor_retry_interval:
                print("\nTrying to initialize sensors...")
                
                # Try each channel one at a time
                for channel in range(16):  # Now checking all 16 channels (2 multiplexers * 8 channels)
                    mux_num = channel // 8 + 1  # Multiplexer number (1 or 2)
                    local_channel = channel % 8  # Local channel on the multiplexer (0-7)
                    print(f"\nTrying multiplexer {mux_num} channel {local_channel} (global channel {channel})...")
                    if multiplexer.init_sensor(channel):
                        print(f"Sensor on multiplexer {mux_num} channel {local_channel} initialized successfully")
                        active_sensors.append(channel)
                
                if len(active_sensors) == 0:
                    print("\nNo working sensors found. Will retry in 5 seconds...")
                else:
                    print(f"\nFound {len(active_sensors)} working sensors:")
                    for channel in active_sensors:
                        mux_num = channel // 8 + 1
                        local_channel = channel % 8
                        print(f"- Multiplexer {mux_num} channel {local_channel} (global channel {channel})")
                    print("\nStarting sensor and LED control loop...")
                
                last_sensor_init = current_time
                continue
            
            # Only update if we have working sensors and enough time has passed
            if len(active_sensors) > 0 and current_time - last_update >= update_interval:
                # Read from next sensor in round-robin fashion
                channel = active_sensors[current_sensor_idx]
                mux_num = channel // 8 + 1
                local_channel = channel % 8
                distance = multiplexer.read_range(channel)
                
                if distance is not None and distance < MAX_DISTANCE:
                    # Update all LED segments based on this sensor's distance
                    color = get_color_from_distance(distance)
                    set_all_stair_lights(strip, color)
                    
                    # Check if sensor is triggered and enough time has passed since last sound
                    is_triggered = distance < TRIGGER_DISTANCE
                    print(f"\nMultiplexer {mux_num} Channel {local_channel}: distance={distance:.1f}mm, threshold={TRIGGER_DISTANCE}mm")
                    print(f"Was triggered: {was_triggered}, Is triggered: {is_triggered}")
                    print(f"Time since last sound: {current_time - last_sound_trigger:.1f}s")
                    
                    if is_triggered and not was_triggered and \
                       bt_audio and bt_audio.sound_file and \
                       current_time - last_sound_trigger >= SOUND_COOLDOWN:
                        print("Playing sound...")
                        # bt_audio.play_sound()
                        last_sound_trigger = current_time
                        print("Skipping playing the audio right now.")
                        # return  # Skip playing audio after trigger
                    was_triggered = is_triggered
                else:
                    # Turn off all LEDs if distance is invalid or too far
                    clear_all_lights(strip)
                    was_triggered = False
                    # If we got an invalid reading, remove this sensor from active list
                    if distance is None:
                        print(f"\nLost connection to multiplexer {mux_num} channel {local_channel}")
                        active_sensors.remove(channel)
                        if len(active_sensors) > 0:
                            current_sensor_idx = current_sensor_idx % len(active_sensors)
                        continue
                
                # Update LED strip
                strip.show()
                
                # Move to next sensor
                current_sensor_idx = (current_sensor_idx + 1) % len(active_sensors)
                
                last_update = current_time
            else:
                # Small sleep to prevent CPU hogging
                time.sleep(0.001)  # 1ms sleep
            
    except KeyboardInterrupt:
        print("\nExiting...")
        clear_all_lights(strip)
        strip.show()

if __name__ == "__main__":
    strip = init_led_strip()
    rainbow_fade(strip)
    main() 