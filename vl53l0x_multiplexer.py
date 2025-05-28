import time
import board
import busio
import adafruit_vl53l0x
from adafruit_tca9548a import TCA9548A

class VL53L0XMultiplexer:
    def __init__(self, i2c_bus=None, tca_address=0x70):
        """Initialize the VL53L0X multiplexer.
        
        Args:
            i2c_bus: Optional I2C bus instance. If None, will create one using board.SCL/SDA
            tca_address: I2C address of the TCA9548A multiplexer (default: 0x70)
        """
        # Create I2C bus if not provided
        self.i2c = i2c_bus if i2c_bus else busio.I2C(board.SCL, board.SDA)
        self.tca_address = tca_address
        
        # Initialize the TCA9548A multiplexer
        self.tca = TCA9548A(self.i2c, address=tca_address)
        
        # List to store sensor objects
        self.sensors = [None] * 8
        self.initialized = [False] * 8
        
        # Disable all channels initially
        self._disable_all_channels()
        
    def _disable_all_channels(self):
        """Disable all multiplexer channels."""
        # Writing 0 disables all channels
        self.i2c.writeto(self.tca_address, bytes([0]))
        time.sleep(0.1)  # Give time for channels to settle
        
    def _select_channel(self, channel):
        """Select a specific channel and disable all others.
        
        Args:
            channel: Channel number (0-7) to select
        """
        if not 0 <= channel <= 7:
            return False
            
        # First disable all channels
        self._disable_all_channels()
        
        # Then enable the selected channel (1 << channel creates a byte with only that channel's bit set)
        self.i2c.writeto(self.tca_address, bytes([1 << channel]))
        time.sleep(0.1)  # Give time for channel to settle
        return True
            
    def init_sensor(self, channel):
        """Initialize a VL53L0X sensor on the specified channel.
        
        Args:
            channel: Channel number (0-7) on the TCA9548A
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        if not 0 <= channel <= 7:
            print(f"Invalid channel number: {channel}")
            return False
            
        try:
            # Select the channel
            if not self._select_channel(channel):
                return False
            
            # Initialize VL53L0X on this channel
            i2c_channel = self.tca[channel]
            sensor = adafruit_vl53l0x.VL53L0X(i2c_channel)
            
            # Configure for long range mode
            sensor.measurement_timing_budget = 33000  # 33ms timing budget
            
            # Store sensor object
            self.sensors[channel] = sensor
            self.initialized[channel] = True
            
            print(f"Successfully initialized sensor on channel {channel}")
            return True
            
        except Exception as e:
            print(f"Failed to initialize sensor on channel {channel}: {str(e)}")
            self.initialized[channel] = False
            return False
            
    def read_range(self, channel):
        """Read the range from a sensor.
        
        Args:
            channel: Channel number (0-7)
            
        Returns:
            int: Range in millimeters, or None if error
        """
        if not 0 <= channel <= 7 or not self.initialized[channel]:
            return None
            
        try:
            # Select the channel before reading
            if not self._select_channel(channel):
                return None
                
            return self.sensors[channel].range
        except Exception as e:
            print(f"Error reading sensor on channel {channel}: {str(e)}")
            return None
            
    def read_all_ranges(self):
        """Read ranges from all initialized sensors.
        
        Returns:
            dict: Dictionary mapping channel numbers to ranges (in mm)
        """
        ranges = {}
        for channel in range(8):
            if self.initialized[channel]:
                range_mm = self.read_range(channel)
                if range_mm is not None:
                    ranges[channel] = range_mm
        return ranges 