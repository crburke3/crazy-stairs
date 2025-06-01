#!/usr/bin/env python3

import subprocess
import time
import os
import re
import pygame

os.environ['SDL_AUDIODRIVER'] = 'alsa'
class BluetoothAudio:
    def __init__(self, device_mac=None, device_name=None):
        self.device_mac = device_mac
        self.device_name = device_name
        self.connected = False
        # Initialize pygame and its mixer with multiple channels
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        # Reserve 14 channels (one for each stair)
        pygame.mixer.set_num_channels(14)
        # Store sound objects for each stair
        self.sounds = {}
        # Load all harp sounds
        for i in range(1, 15):
            sound_file = f"stair_sounds/harp/harp{i:02d}.wav"
            if os.path.exists(sound_file):
                self.sounds[i] = pygame.mixer.Sound(sound_file)
                print(f"Loaded sound for stair {i}")
        
    def set_sound_file(self, file_path):
        """Set the sound file to be played when triggered"""
        if not os.path.exists(file_path):
            print(f"Warning: Sound file {file_path} does not exist")
            return False
        print(f"Sound file set to: {file_path}")
        return True
    
    def connect_bluetooth(self):
        """Connect to the Bluetooth speaker"""
        try:
            # If no MAC address provided, try to find the speaker by name
            if not self.device_mac and self.device_name:
                print(f"Looking for Bluetooth device with name: {self.device_name}")
                result = subprocess.run(['sudo', 'bluetoothctl', 'devices'], 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.PIPE,
                                     text=True)
                
                for line in result.stdout.splitlines():
                    if self.device_name in line:
                        self.device_mac = line.split()[1]
                        print(f"Found device MAC: {self.device_mac}")
                        break
            
            if not self.device_mac:
                print("No Bluetooth device MAC address available")
                return False
            
            # Check if already connected
            result = subprocess.run(['sudo','bluetoothctl', 'info', self.device_mac],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True)
            
            if "Connected: yes" in result.stdout:
                print("Bluetooth device already connected")
                self.connected = True
                return True
            
            print(f"Attempting to connect to Bluetooth device: {self.device_mac}")
            
            # Power on Bluetooth if needed
            subprocess.run(['sudo', 'bluetoothctl', 'power', 'on'])
            time.sleep(1)
            
            # Try to connect
            max_attempts = 3
            for attempt in range(max_attempts):
                print(f"Connection attempt {attempt + 1}/{max_attempts}")
                
                result = subprocess.run(['sudo', 'bluetoothctl', 'connect', self.device_mac],
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,
                                     text=True)
                
                # Check if connection was successful
                if "Connection successful" in result.stdout:
                    print("Successfully connected to Bluetooth device")
                    self.connected = True
                    return True
                
                # If failed, wait before retrying
                if attempt < max_attempts - 1:
                    print("Connection failed, retrying in 2 seconds...")
                    time.sleep(2)
            
            print("Failed to connect to Bluetooth device after multiple attempts")
            return False
            
        except Exception as e:
            print(f"Error connecting to Bluetooth device: {e}")
            return False
    
    def play_sound(self, stair_num=None):
        """Play the configured sound file asynchronously"""
        # Try to reconnect if not connected
        if not self.connected:
            print("Bluetooth not connected, attempting to reconnect...")
            if not self.connect_bluetooth():
                print("Failed to reconnect Bluetooth")
                return False
        
        try:
            if stair_num is not None and stair_num in self.sounds:
                # Get the channel for this stair (0-13)
                channel_num = stair_num - 1
                # Get the channel object
                channel = pygame.mixer.Channel(channel_num)
                # Stop any currently playing sound on this channel
                channel.stop()
                # Play the sound on this channel without waiting
                channel.play(self.sounds[stair_num])
                print(f"Started playing sound for stair {stair_num} on channel {channel_num}")
                return True
            else:
                print(f"No sound found for stair {stair_num}")
                return False
                
        except Exception as e:
            print(f"Error in play_sound: {e}")
            self.connected = False
            return False

def setup_bluetooth_audio(device_name="JBL GO 2+"):
    """
    Set up audio playback with automatic Bluetooth connection.
    Args:
        device_name: Name of the Bluetooth device to connect to (default: "JBL GO 2+")
    Returns:
        BluetoothAudio instance if successful, None otherwise.
    """
    print(f"\nSetting up Bluetooth audio for device: {device_name}")
    print(os.getcwd())
    bt_audio = BluetoothAudio(device_name=device_name)
    
    if bt_audio.connect_bluetooth():
        print("Bluetooth audio setup complete")
        return bt_audio
    else:
        print("\nNOTE: Could not automatically connect to Bluetooth speaker")
        print("You can manually pair and connect your speaker using:")
        print("1. Raspberry Pi desktop Bluetooth settings")
        print("2. Or command line: bluetoothctl")
        print("3. Or using the system tray Bluetooth icon\n")
        return bt_audio  # Return instance anyway so it can retry connections later 