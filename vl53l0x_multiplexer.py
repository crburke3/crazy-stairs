import time
import board
import busio
import adafruit_vl53l0x
from adafruit_tca9548a import TCA9548A
import errno

class VL53L0XMultiplexer:
    def __init__(self, i2c_bus=None, tca_addresses=[0x70, 0x77]):
        """Initialize the VL53L0X multiplexer.
        
        Args:
            i2c_bus: Optional I2C bus instance. If None, will create one using board.SCL/SDA
            tca_addresses: List of I2C addresses for TCA9548A multiplexers (default: [0x70, 0x77])
        """
        # Create I2C bus if not provided
        self.i2c = i2c_bus if i2c_bus else busio.I2C(board.SCL, board.SDA)
        self.tca_addresses = tca_addresses
        
        # Helper to probe for I2C address
        def i2c_address_present(i2c, addr):
            try:
                i2c.writeto(addr, b"")
                return True
            except OSError as e:
                # errno 121 is Remote I/O error (no device)
                if hasattr(e, 'errno') and e.errno == errno.EREMOTEIO:
                    return False
                # Some platforms just raise OSError if no device
                return False
            except Exception:
                return False
        
        # Initialize the TCA9548A multiplexers
        self.tcas = []
        self.working_multiplexers = 0
        
        for addr in tca_addresses:
            if i2c_address_present(self.i2c, addr):
                try:
                    tca = TCA9548A(self.i2c, address=addr)
                    self.tcas.append((addr, tca))
                    self.working_multiplexers += 1
                    print(f"Successfully initialized multiplexer at address 0x{addr:02x}")
                except Exception as e:
                    print(f"Failed to initialize multiplexer at address 0x{addr:02x}: {str(e)}")
                    print("System will continue with remaining multiplexers")
                    self.tcas.append((addr, None))  # Add None to maintain indexing
            else:
                print(f"Multiplexer not found at address 0x{addr:02x}. Skipping.")
                self.tcas.append((addr, None))
        
        if self.working_multiplexers == 0:
            raise RuntimeError("No multiplexers could be initialized. Please check connections.")
        
        # Lists to store sensor objects and status (16 channels total, 8 per multiplexer)
        self.sensors = [None] * (8 * len(self.tcas))
        self.initialized = [False] * (8 * len(self.tcas))
        
        # Disable all channels initially
        self._disable_all_channels()
        
    def _get_multiplexer_and_channel(self, global_channel):
        """Convert global channel number to multiplexer and local channel.
        
        Args:
            global_channel: Channel number (0-15)
            
        Returns:
            tuple: (multiplexer_index, local_channel) or (None, None) if invalid
        """
        if not 0 <= global_channel < (8 * len(self.tcas)):
            return None, None
        return divmod(global_channel, 8)
        
    def _disable_all_channels(self):
        """Disable all multiplexer channels."""
        # Writing 0 disables all channels
        for addr, tca in self.tcas:
            if tca is not None:  # Only try to disable channels on working multiplexers
                self.i2c.writeto(addr, bytes([0]))
        time.sleep(0.1)  # Give time for channels to settle
        
    def _select_channel(self, global_channel):
        """Select a specific channel and disable all others.
        
        Args:
            global_channel: Global channel number (0-15)
        """
        mux_idx, local_channel = self._get_multiplexer_and_channel(global_channel)
        if mux_idx is None:
            return False
            
        # Check if the multiplexer is working
        if self.tcas[mux_idx][1] is None:
            print(f"Cannot select channel {global_channel} - multiplexer at 0x{self.tcas[mux_idx][0]:02x} is not working")
            return False
            
        # First disable all channels on all multiplexers
        self._disable_all_channels()
        
        # Then enable the selected channel on the correct multiplexer
        addr = self.tcas[mux_idx][0]
        self.i2c.writeto(addr, bytes([1 << local_channel]))
        time.sleep(0.1)  # Give time for channel to settle
        return True
            
    def init_sensor(self, global_channel):
        """Initialize a VL53L0X sensor on the specified channel.
        
        Args:
            global_channel: Global channel number (0-15)
            
        Returns:
            bool: True if initialization successful, False otherwise
        """
        mux_idx, local_channel = self._get_multiplexer_and_channel(global_channel)
        if mux_idx is None:
            print(f"Invalid channel number: {global_channel}")
            return False
            
        # Check if the multiplexer is working
        if self.tcas[mux_idx][1] is None:
            print(f"Cannot initialize sensor on channel {global_channel} - multiplexer at 0x{self.tcas[mux_idx][0]:02x} is not working")
            return False
            
        try:
            # Select the channel
            if not self._select_channel(global_channel):
                return False
            
            # Initialize VL53L0X on this channel
            i2c_channel = self.tcas[mux_idx][1][local_channel]
            sensor = adafruit_vl53l0x.VL53L0X(i2c_channel)
            
            # Configure for long range mode
            sensor.measurement_timing_budget = 33000  # 33ms timing budget
            
            # Store sensor object
            self.sensors[global_channel] = sensor
            self.initialized[global_channel] = True
            
            print(f"Successfully initialized sensor on channel {global_channel}")
            return True
            
        except Exception as e:
            print(f"Failed to initialize sensor on channel {global_channel}: {str(e)}")
            self.initialized[global_channel] = False
            return False
            
    def read_range(self, global_channel):
        """Read the range from a sensor.
        
        Args:
            global_channel: Global channel number (0-15)
            
        Returns:
            int: Range in millimeters, or None if error
        """
        if not 0 <= global_channel < (8 * len(self.tcas)) or not self.initialized[global_channel]:
            return None
            
        try:
            # Select the channel before reading
            if not self._select_channel(global_channel):
                return None
                
            return self.sensors[global_channel].range
        except Exception as e:
            print(f"Error reading sensor on channel {global_channel}: {str(e)}")
            return None
            
    def read_all_ranges(self):
        """Read ranges from all initialized sensors.
        
        Returns:
            dict: Dictionary mapping channel numbers to ranges (in mm)
        """
        ranges = {}
        for channel in range(8 * len(self.tcas)):
            if self.initialized[channel]:
                range_mm = self.read_range(channel)
                if range_mm is not None:
                    ranges[channel] = range_mm
        return ranges 