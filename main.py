#!/usr/bin/env python3

import time
from vl53l0x_multiplexer import VL53L0XMultiplexer
from rpi_ws281x import PixelStrip, Color
from bluetooth_audio import setup_bluetooth_audio
import os
import colorsys
import numpy as np
from scipy.io import wavfile
import json
import subprocess

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
        for brightness in range(0, 256, 150):  # Steps of 51 to reach 255 in 5 steps
        
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
    time.sleep(1)
    
    # Turn off all LEDs
    print("\nTurning off all LEDs")
    clear_all_lights(strip)
    print("LED test complete")

# Sound configuration
SOUND_FILE = "/home/connor/crazy-stairs/stair_sounds/harp/harp01.wav"  # Sound file to play when triggered
SOUND_COOLDOWN = 2.0  # Minimum time between sound triggers in seconds
TONE_DURATION = 0.25  # Duration of each tone in seconds
SAMPLE_RATE = 44100   # Standard audio sample rate
TONE_CACHE_DIR = "tone_cache"  # Directory to store generated tones

# Define frequencies for each stair (in Hz)
STAIR_FREQUENCIES = {
    1: 440,   # A4
    2: 494,   # B4
    3: 523,   # C5
    4: 587,   # D5
    5: 659,   # E5
    6: 698,   # F5
    7: 784,   # G5
    8: 880,   # A5
    9: 988,   # B5
    10: 1047, # C6
    11: 1175, # D6
    12: 1319, # E6
    13: 1397, # F6
    14: 1568, # G6
}

def generate_tone(frequency, duration=TONE_DURATION, sample_rate=SAMPLE_RATE):
    """Generate a sine wave tone of specified frequency and duration.
    
    Args:
        frequency: Frequency of the tone in Hz
        duration: Duration of the tone in seconds
        sample_rate: Audio sample rate in Hz
        
    Returns:
        numpy array containing the audio samples
    """
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    tone = np.sin(2 * np.pi * frequency * t)
    
    # Apply fade in/out to avoid clicks
    fade_duration = int(0.01 * sample_rate)  # 10ms fade
    fade_in = np.linspace(0, 1, fade_duration)
    fade_out = np.linspace(1, 0, fade_duration)
    
    tone[:fade_duration] *= fade_in
    tone[-fade_duration:] *= fade_out
    
    # Convert to 16-bit PCM
    tone = np.int16(tone * 32767)
    return tone

def ensure_tone_cache():
    """Ensure the tone cache directory exists and generate all tones."""
    if not os.path.exists(TONE_CACHE_DIR):
        os.makedirs(TONE_CACHE_DIR)
    
    # Generate and save tones for each stair
    for stair_num, frequency in STAIR_FREQUENCIES.items():
        tone_file = os.path.join(TONE_CACHE_DIR, f"stair_{stair_num}.wav")
        if not os.path.exists(tone_file):
            tone = generate_tone(frequency)
            wavfile.write(tone_file, SAMPLE_RATE, tone)
            print(f"Generated tone for stair {stair_num} ({frequency}Hz)")

def get_tone_file_for_stair(stair_num):
    """Get the path to the tone file for a given stair number."""
    return os.path.join(TONE_CACHE_DIR, f"stair_{stair_num}.wav")

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

def fade_stair_leds(strip, stair_num, target_brightness, fade_steps=10, fade_delay=0.001):
    """Fade a stair's LEDs to a target brightness level.
    
    Args:
        strip: LED strip object
        stair_num: Stair number to fade
        target_brightness: Target brightness (0-255)
        fade_steps: Number of steps for fade
        fade_delay: Delay between steps in seconds
    """
    if strip is None or stair_num not in STAIR_LED_COUNTS:
        return
        
    # Calculate LED range for this stair
    start_led = sum(STAIR_LED_COUNTS[i] for i in range(1, stair_num))
    end_led = start_led + STAIR_LED_COUNTS[stair_num] - 1
    
    # Get current brightness of first LED in stair (assuming all LEDs in stair have same brightness)
    current_color = strip.getPixelColor(start_led)
    current_brightness = max(
        (current_color >> 16) & 0xFF,  # Red
        (current_color >> 8) & 0xFF,   # Green
        current_color & 0xFF           # Blue
    )
    
    # Calculate step size
    step_size = (target_brightness - current_brightness) / fade_steps
    
    # Fade to target brightness
    for step in range(fade_steps):
        brightness = int(current_brightness + (step_size * (step + 1)))
        color = Color(brightness, 0, brightness)  # Purple color with current brightness
        
        for i in range(start_led, end_led + 1):
            strip.setPixelColor(i, color)
        strip.show()
        time.sleep(fade_delay)

def set_volume_to_max():
    """Set the Raspberry Pi's volume to maximum."""
    try:
        # Set ALSA volume to 30%
        subprocess.run(['amixer', 'set', 'Master', '30%'], check=True)
        # Set ALSA volume to unmuted
        subprocess.run(['amixer', 'set', 'Master', 'unmute'], check=True)
        print("Volume set to 30%")
    except subprocess.CalledProcessError as e:
        print(f"Warning: Failed to set volume: {e}")
    except Exception as e:
        print(f"Warning: Error setting volume: {e}")

def get_sound_file_for_stair(stair_num):
    """Get the path to the harp sound file for a given stair number."""
    return f"stair_sounds/harp/harp{stair_num:02d}.wav"

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
    
    print("Waiting 5 seconds to start the main loop")
    time.sleep(5)
    last_update = time.time()
    last_table_update = 0  # Track when we last updated the table
    table_update_interval = 0.05  # Update table 20 times per second
    update_interval = 0.01  # 10ms refresh rate (100Hz)
    sensor_retry_interval = 5.0  # How often to retry initializing sensors
    last_sensor_init = 0
    active_sensors = []  # List of working sensor channel numbers
    current_sensor_idx = 0  # Index into active_sensors for round-robin reading
    
    # Dictionaries to track sensor states and current distances
    sensor_states = {}  # channel -> triggered state
    current_distances = {}  # channel -> current distance
    
    print("\nInitializing sensors...")
    
    try:
        while True:
            current_time = time.time()
            
            # Try to initialize sensors if we don't have any working ones
            if len(active_sensors) == 0 and current_time - last_sensor_init >= sensor_retry_interval:
                print("\nTrying to initialize sensors...")
                
                # Try each channel one at a time
                for channel in range(16):
                    mux_num = channel // 8 + 1
                    local_channel = channel % 8
                    if multiplexer.init_sensor(channel):
                        active_sensors.append(channel)
                        sensor_states[channel] = False
                
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
                    
                    # If state changed, update LED and play sound
                    if is_triggered != was_triggered:
                        sensor_states[channel] = is_triggered
                        
                        # Get corresponding stair number
                        stair_num = STAIR_MAPPING.get(channel)
                        if stair_num is not None and strip is not None:
                            if is_triggered:
                                # Fade in over 0.5 seconds (50 steps, 10ms delay)
                                fade_stair_leds(strip, stair_num, 255, fade_steps=5, fade_delay=0.01)
                            else:
                                # Fade out slowly (20 steps, 2ms delay)
                                fade_stair_leds(strip, stair_num, 0, fade_steps=5, fade_delay=0.002)
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