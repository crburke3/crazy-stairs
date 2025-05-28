#!/usr/bin/env python3

import subprocess
import time
import os
import re

class BluetoothAudio:
    def __init__(self, device_mac=None, device_name=None):
        self.sound_file = None
        self.device_mac = device_mac
        self.device_name = device_name
        self.connected = False
        
    def set_sound_file(self, file_path):
        """Set the sound file to be played when triggered"""
        if not os.path.exists(file_path):
            print(f"Warning: Sound file {file_path} does not exist")
            return False
        self.sound_file = file_path
        print(f"Sound file set to: {file_path}")
        return True
    
    def connect_bluetooth(self):
        """Connect to the Bluetooth speaker"""
        try:
            # If no MAC address provided, try to find the speaker by name
            if not self.device_mac and self.device_name:
                print(f"Looking for Bluetooth device with name: {self.device_name}")
                result = subprocess.run(['bluetoothctl', 'devices'], 
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
            result = subprocess.run(['bluetoothctl', 'info', self.device_mac],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 text=True)
            
            if "Connected: yes" in result.stdout:
                print("Bluetooth device already connected")
                self.connected = True
                return True
            
            print(f"Attempting to connect to Bluetooth device: {self.device_mac}")
            
            # Power on Bluetooth if needed
            subprocess.run(['bluetoothctl', 'power', 'on'])
            time.sleep(1)
            
            # Try to connect
            max_attempts = 3
            for attempt in range(max_attempts):
                print(f"Connection attempt {attempt + 1}/{max_attempts}")
                
                result = subprocess.run(['bluetoothctl', 'connect', self.device_mac],
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
    
    def play_sound(self):
        """Play the configured sound file"""
        if not self.sound_file:
            print("No sound file configured")
            return False
        
        # Try to reconnect if not connected
        if not self.connected:
            print("Bluetooth not connected, attempting to reconnect...")
            if not self.connect_bluetooth():
                print("Failed to reconnect Bluetooth")
                return False
        
        try:
            print(f"Attempting to play sound: {self.sound_file}")
            result = subprocess.run(['paplay', '--server=/run/user/1000/pulse/native', self.sound_file], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE,
                                 env={'XDG_RUNTIME_DIR': '/run/user/1000'})
            
            # If playback fails, try reconnecting once
            if result.returncode != 0:
                print("Playback failed, attempting to reconnect...")
                if self.connect_bluetooth():
                    # Retry playback after reconnection
                    result = subprocess.run(['paplay', '--server=/run/user/1000/pulse/native', self.sound_file], 
                                         stdout=subprocess.PIPE, 
                                         stderr=subprocess.PIPE,
                                         env={'XDG_RUNTIME_DIR': '/run/user/1000'})
            
            if result.returncode != 0:
                print(f"Error playing sound. Return code: {result.returncode}")
                print(f"Error output: {result.stderr.decode()}")
                self.connected = False
            else:
                print("Sound played successfully")
            return result.returncode == 0
        except Exception as e:
            print(f"Error playing sound: {e}")
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