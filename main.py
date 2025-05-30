#!/usr/bin/env python3

import time
from vl53l0x_multiplexer import VL53L0XMultiplexer
from rpi_ws281x import PixelStrip, Color
from bluetooth_audio import setup_bluetooth_audio
import os
import colorsys

# LED strip configuration
LED_PIN = 18          # GPIO18 (PWM0) - DO NOT use TXD/GPIO14
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10          # DMA channel to use for generating signal
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_CHANNEL = 0       # PWM channel (0 for GPIO18, 1 for GPIO13)
LED_INVERT = False    # True to invert the signal

# Distance configuration (in millimeters)
MAX_DISTANCE = 2000.0  # Distance at which LED starts to change color (2 meters)
MIN_DISTANCE = 200.0   # Distance at which LED reaches maximum intensity
TRIGGER_DISTANCE = 609.6  # 24 inches in mm - when to consider "triggered"

# Mapping of multiplexer channels to stair numbers
# Format: {global_channel: stair_number}
# Use None for unconnected channels
STAIR_MAPPING = {
    0: 9,    # Multiplexer 1, Channel 0 -> Stair 9
    1: 10,    # Multiplexer 1, Channel 1 -> Stair 10
    2: None,    # Multiplexer 1, Channel 2 -> NOT CONNECTED
    3: None,    # Multiplexer 1, Channel 3 -> NOT CONNECTED
    4: 11,    # Multiplexer 1, Channel 4 -> Stair 11
    5: 12,    # Multiplexer 1, Channel 5 -> Stair 12
    6: 13,    # Multiplexer 1, Channel 6 -> Stair 13
    7: 14,    # Multiplexer 1, Channel 7 -> Stair 14

    8: 1,    # Multiplexer 2, Channel 0 -> Stair 1
    9: 2,   # Multiplexer 2, Channel 1 -> Stair 2
    10: 3,  # Multiplexer 2, Channel 2 -> Stair 3
    11: 4,  # Multiplexer 2, Channel 3 -> Stair 4
    12: 5,  # Multiplexer 2, Channel 4 -> Stair 5
    13: 6,  # Multiplexer 2, Channel 5 -> Stair 6
    14: 7,  # Multiplexer 2, Channel 6 -> Stair 7
    15: 8,  # Multiplexer 2, Channel 7 -> Stair 8
}

# Mapping of stair numbers to their LED counts
# Format: {stair_number: led_count}
# Default is 114 LEDs per stair if not specified
STAIR_LED_COUNTS = {
    1: 114,   # Stair 1: 
    2: 114,   # Stair 2: 
    3: 114,   # Stair 3: 
    4: 114,   # Stair 4: 
    5: 114,   # Stair 5: 
    6: 112,   # Stair 6: 
    7: 112,   # Stair 7: 
    8: 114,   # Stair 8: 
    9: 112,   # Stair 9: 
    10: 114,  # Stair 10:
    11: 114,  # Stair 11:
    12: 114,  # Stair 12:
    13: 114,  # Stair 13:
    14: 114,  # Stair 14:
}
LED_COUNT = sum(STAIR_LED_COUNTS.values())

def get_led_count_for_stair(stair_number):
    """Get the number of LEDs for a given stair number.
    
    Args:
        stair_number: The stair number to look up
        
    Returns:
        int: Number of LEDs for the stair (defaults to 130 if not specified)
    """
    return STAIR_LED_COUNTS.get(stair_number, 130)

def test_led_strip(strip):
    """Test the LED strip by fading in each stair sequentially with a cold-to-hot color gradient.
    
    Args:
        strip: The LED strip object to test
    """
    if strip is None:
        print("Skipping LED test - strip not initialized")
        return
        
    print("\nTesting LED strip with", strip.numPixels(), "LEDs")
    
    # First turn off all LEDs
    print("Turning off all LEDs")
    clear_all_lights(strip)
    
    # Calculate LED ranges for each stair
    current_led = 0
    stair_ranges = {}
    for stair_num in sorted(STAIR_LED_COUNTS.keys()):
        led_count = STAIR_LED_COUNTS[stair_num]
        stair_ranges[stair_num] = (current_led, current_led + led_count - 1)
        current_led += led_count
    
    # Define colors from cold to hot
    cold_to_hot_colors = [
        Color(0, 0, 255),      # Cold: Blue
        Color(0, 128, 255),    # Light Blue
        Color(0, 255, 255),    # Cyan
        Color(0, 255, 128),    # Blue-Green
        Color(0, 255, 0),      # Green
        Color(128, 255, 0),    # Yellow-Green
        Color(255, 255, 0),    # Yellow
        Color(255, 128, 0),    # Orange
        Color(255, 64, 0),     # Orange-Red
        Color(255, 0, 0),      # Red
        Color(255, 0, 64),     # Red-Pink
        Color(255, 0, 128),    # Pink
        Color(255, 0, 255),    # Hot Pink
        Color(255, 0, 255),    # Hot: Magenta
    ]
    
    # Test each stair with fade effect
    for stair_num in sorted(stair_ranges.keys()):
        start_led, end_led = stair_ranges[stair_num]
        color = cold_to_hot_colors[stair_num - 1]  # -1 because stairs start at 1
        print(f"Fading in Stair {stair_num}: LEDs {start_led}-{end_led} ({end_led - start_led + 1} LEDs)")
        
        # Fade in effect (5 steps instead of 10, faster steps)
        for brightness in range(0, 256, 51):  # Steps of 51 to reach 255 in 5 steps
            # Calculate color with current brightness
            r = int((color >> 16 & 0xFF) * brightness / 255)
            g = int((color >> 8 & 0xFF) * brightness / 255)
            b = int((color & 0xFF) * brightness / 255)
            current_color = Color(r, g, b)
            
            # Set all LEDs for this stair
            for i in range(start_led, end_led + 1):
                strip.setPixelColor(i, current_color)
            strip.show()
            # time.sleep(0.005)  # delay for faster fade
        
        # Keep stair lit briefly
        # time.sleep(0.001)
    
    # Keep all stairs lit for 5 seconds
    print("\nAll stairs are now lit with cold-to-hot gradient. Keeping lit for 5 seconds...")
    time.sleep(5)
    
    # Turn off all LEDs
    print("\nTurning off all LEDs")
    clear_all_lights(strip)
    print("LED test complete")

# Sound configuration
SOUND_FILE = "stair_trigger.wav"  # Sound file to play when triggered
SOUND_COOLDOWN = 2.0  # Minimum time between sound triggers in seconds

def init_led_strip():
    """Initialize the LED strip. Returns None if initialization fails."""
    print("NOTE: WS2812B LEDs must be connected to GPIO18 (PWM0), not TXD/GPIO14")
    print("Please ensure your LED data line is connected to GPIO18")
    try:
        strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        strip.begin()
        return strip
    except Exception as e:
        print(f"Failed to initialize LED strip: {str(e)}")
        print("Continuing without LED functionality...")
        return None

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

def rainbow_fade(strip, duration=3):
    """Fade all LEDs through a smooth rainbow effect for a specified duration.
    
    Args:
        strip: The LED strip object
        duration: How long to run the effect in seconds
    """
    start_time = time.time()
    while time.time() - start_time < duration:
        for i in range(strip.numPixels()):
            hue = (i / strip.numPixels() + time.time() * 0.1) % 1.0
            r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
            strip.setPixelColor(i, Color(r, g, b))
        strip.show()
        time.sleep(0.01)

def cycle_all_leds(strip, hue):
    """Set all LEDs to the same color based on hue value (0-1)."""
    r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(r, g, b))
    strip.show()

def print_sensor_status_table(active_sensors, sensor_states, current_distances):
    """Print a formatted table of all sensor statuses."""
    print("\033[2J\033[H")  # Clear screen and move cursor to top
    print("Sensor Status Table:")
    print("┌─────────────┬─────────────┬────────────┬──────────┬───────────┬──────────┐")
    print("│ Multiplexer │   Channel   │ Connected  │ Distance │ Triggered │   Stair  │")
    print("├─────────────┼─────────────┼────────────┼──────────┼───────────┼──────────┤")
    
    # Create a list of channels with their stair numbers for sorting
    channels_with_stairs = []
    for channel in range(16):
        mux_num = channel // 8 + 1
        local_channel = channel % 8
        is_active = channel in active_sensors
        distance = current_distances.get(channel, None)
        is_triggered = sensor_states.get(channel, False)
        stair_num = STAIR_MAPPING.get(channel, None)
        
        # Add to list with stair number for sorting
        channels_with_stairs.append((channel, mux_num, local_channel, is_active, distance, is_triggered, stair_num))
    
    # Sort by stair number (descending), with None values at the end
    channels_with_stairs.sort(key=lambda x: (x[6] is None, -x[6] if x[6] is not None else 0))
    
    # Print sorted rows
    for channel, mux_num, local_channel, is_active, distance, is_triggered, stair_num in channels_with_stairs:
        status = "Yes" if is_active else "No "
        distance_str = f"{distance:.1f}mm" if distance is not None else "---"
        triggered_str = "Yes" if is_triggered else "No "
        stair_str = str(stair_num) if stair_num is not None else "---"
        
        print(f"│     {mux_num}       │     {local_channel}       │    {status}    │ {distance_str:>8} │    {triggered_str}    │   {stair_str:>4}   │")
    
    print("└─────────────┴─────────────┴────────────┴──────────┴───────────┴──────────┘")
    print(f"\nTrigger threshold: {TRIGGER_DISTANCE:.1f}mm")

def main():
    # Create multiplexer instance
    print("Initializing VL53L0X multiplexer...")
    multiplexer = VL53L0XMultiplexer()
    
    # Initialize LED strip
    print("Initializing LED strip...")
    strip = init_led_strip()
    
    # Test LED strip if initialized successfully
    if strip is not None:
        test_led_strip(strip)
    else:
        print("Skipping LED initialization and test pattern")
    
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
    last_table_update = 0  # Track when we last updated the table
    table_update_interval = 0.05  # Update table 20 times per second (reduced from 0.1)
    update_interval = 0.01  # 10ms refresh rate (100Hz) (reduced from 0.02)
    sensor_retry_interval = 5.0  # How often to retry initializing sensors
    last_sensor_init = 0
    active_sensors = []  # List of working sensor channel numbers
    current_sensor_idx = 0  # Index into active_sensors for round-robin reading
    
    # Dictionaries to track sensor states and current distances
    sensor_states = {}  # channel -> triggered state
    current_distances = {}  # channel -> current distance
    
    print("\nInitializing sensors...")
    
    # For LED color cycling
    hue = 0.0
    color_speed = 0.001  # Adjust this to change color cycle speed
    
    try:
        while True:
            current_time = time.time()
            
            # Update LED colors for debugging
            if strip is not None:
                cycle_all_leds(strip, hue)
                hue = (hue + color_speed) % 1.0  # Keep hue between 0 and 1
            
            # Try to initialize sensors if we don't have any working ones
            if len(active_sensors) == 0 and current_time - last_sensor_init >= sensor_retry_interval:
                print("\nTrying to initialize sensors...")
                
                # Try each channel one at a time
                for channel in range(16):  # Now checking all 16 channels (2 multiplexers * 8 channels)
                    mux_num = channel // 8 + 1  # Multiplexer number (1 or 2)
                    local_channel = channel % 8  # Local channel on the multiplexer (0-7)
                    if multiplexer.init_sensor(channel):
                        active_sensors.append(channel)
                        sensor_states[channel] = False  # Initialize as not triggered
                
                if len(active_sensors) == 0:
                    print("\nNo working sensors found. Will retry in 5 seconds...")
                
                last_sensor_init = current_time
                continue
            
            # Only update if we have working sensors and enough time has passed
            if len(active_sensors) > 0 and current_time - last_update >= update_interval:
                # Read from next sensor in round-robin fashion
                channel = active_sensors[current_sensor_idx]
                distance = multiplexer.read_range(channel)
                
                # Update distance in tracking dictionary
                current_distances[channel] = distance
                
                if distance is not None:
                    # Update trigger state
                    was_triggered = sensor_states[channel]
                    is_triggered = distance < TRIGGER_DISTANCE
                    
                    # Only update state and play sound if state changed
                    if is_triggered != was_triggered:
                        sensor_states[channel] = is_triggered
                        if is_triggered and bt_audio and bt_audio.sound_file and \
                           current_time - last_sound_trigger >= SOUND_COOLDOWN:
                            print("Playing sound...")
                            # bt_audio.play_sound()
                            last_sound_trigger = current_time
                            print("Skipping playing the audio right now.")
                else:
                    # If we got an invalid reading, remove this sensor from active list
                    active_sensors.remove(channel)
                    sensor_states.pop(channel, None)
                    current_distances.pop(channel, None)
                    if len(active_sensors) > 0:
                        current_sensor_idx = current_sensor_idx % len(active_sensors)
                    continue
                
                # Move to next sensor
                current_sensor_idx = (current_sensor_idx + 1) % len(active_sensors)
                last_update = current_time
                
                # Update status table at regular intervals
                if current_time - last_table_update >= table_update_interval:
                    print_sensor_status_table(active_sensors, sensor_states, current_distances)
                    last_table_update = current_time
            else:
                # Small sleep to prevent CPU hogging
                time.sleep(0.001)  # 1ms sleep
            
    except KeyboardInterrupt:
        print("\nExiting...")
        if strip is not None:
            clear_all_lights(strip)
            strip.show()

if __name__ == "__main__":
    main() 