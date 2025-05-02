import time
import logging
import threading
import adafruit_bno055
import board
import busio
from kos_zbot.utils.logging import get_logger

class BNO055Manager:
    def __init__(self, update_rate=50):
        self.log = get_logger(__name__)
        self.target_period = 1.0 / update_rate
        
        # Initialize I2C connection
        self.i2c = busio.I2C(board.SCL, board.SDA)
        self.sensor = adafruit_bno055.BNO055_I2C(self.i2c)
        
        # Initialize sensor data containers
        self.accel = (0, 0, 0)
        self.gyro = (0, 0, 0)
        self.mag = (0, 0, 0)
        self.quaternion = (0, 0, 0, 0)
        self.euler = (0, 0, 0)
        self.linear_accel = (0, 0, 0)
        self.gravity = (0, 0, 0)
        self.temperature = 0
        
        # Initialize timing statistics
        self.last_loop_time = 0
        self.max_loop_time = 0
        self.consecutive_overruns = 0
        self.timing_stats = {
            'accel': [],
            'gyro': [],
            'quaternion': [],
            'overruns': 0,
            'total_cycles': 0
        }
        
        # Threading control
        self._stop_event = threading.Event()
        self._thread = None

    def start(self):
        """Start the IMU update thread."""
        if self._thread is not None and self._thread.is_alive():
            self.log.warning("IMU thread already running")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop)
        self._thread.daemon = True
        self._thread.start()
        self.log.info("IMU thread started")

    def stop(self):
        """Stop the IMU update thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        self._thread = None
        self.log.info("IMU thread stopped")

    def _update_loop(self):
        """Main update loop for reading sensor data."""
        while not self._stop_event.is_set():
            loop_start = time.time()
            
            try:
                # Read all sensor data
                start_time = time.time()
                #self.temperature = self.sensor.temperature
                self.accel = self.sensor.acceleration
                #self.mag = self.sensor.magnetic
                self.gyro = self.sensor.gyro
                self.euler = self.sensor.euler
                self.quaternion = self.sensor.quaternion
                #self.linear_accel = self.sensor.linear_acceleration
                #self.gravity = self.sensor.gravity
                
                read_time = time.time() - start_time
                self.timing_stats['accel'].append(read_time)

                # Calculate and store loop timing
                loop_time = time.time() - loop_start
                self.last_loop_time = loop_time
                self.max_loop_time = max(self.max_loop_time, loop_time)
                
                if loop_time > self.target_period:
                    self.timing_stats['overruns'] += 1
                    self.consecutive_overruns += 1
                    if self.consecutive_overruns >= 3:
                        logging.warning(f"IMU timing overrun: {loop_time*1000:.2f}ms (target: {self.target_period*1000:.2f}ms)")
                else:
                    self.consecutive_overruns = 0
                
                self.timing_stats['total_cycles'] += 1
                
                # Sleep for remaining time if any
                sleep_time = self.target_period - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                self.log.error(f"Error in IMU update loop: {str(e)}")
                time.sleep(0.1)  # Brief pause on error

    def get_values(self):
        """Get the latest IMU readings.
        
        Returns:
            tuple: (acceleration, gyro, magnetic) tuples in their respective units
        """
        return self.accel, self.gyro, self.mag

    def get_quaternion(self):
        """Get the latest quaternion reading.
        
        Returns:
            tuple: (w, x, y, z) quaternion values
        """
        return self.quaternion

    def get_euler(self):
        """Get the latest euler angles.
        
        Returns:
            tuple: (roll, pitch, yaw) in degrees
        """
        return self.euler

    def get_advanced_values(self):
        """Get additional sensor readings.
        
        Returns:
            tuple: (linear_acceleration, gravity, temperature)
        """
        return self.linear_accel, self.gravity, self.temperature

    def get_timing_stats(self):
        """Get current timing statistics."""
        stats = {
            'target_period': self.target_period,
            'last_loop_time': self.last_loop_time,
            'max_loop_time': self.max_loop_time,
            'overruns': self.timing_stats['overruns'],
            'total_cycles': self.timing_stats['total_cycles'],
            'average_read_times': {
                'sensors': sum(self.timing_stats['accel']) / len(self.timing_stats['accel']) if self.timing_stats['accel'] else 0,
            }
        }
        return stats

# Example usage:
if __name__ == "__main__":
    # Initialize and start the IMU manager
    imu = BNO055Manager(update_rate=50)
    imu.start()
    
    try:
        while True:
            # Clear screen and print all sensor data
            print("\033[H\033[J")  # Clear screen
            print(f"Temperature: {imu.temperature} degrees C")
            print(f"Accelerometer (m/s^2): {imu.accel}")
            print(f"Magnetometer (microteslas): {imu.mag}")
            print(f"Gyroscope (rad/sec): {imu.gyro}")
            print(f"Euler angle: {imu.euler}")
            print(f"Quaternion: {imu.quaternion}")
            print(f"Linear acceleration (m/s^2): {imu.linear_accel}")
            print(f"Gravity (m/s^2): {imu.gravity}")
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        imu.stop()