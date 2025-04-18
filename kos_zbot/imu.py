import time
import logging
import threading
import adafruit_bno055
import serial


class BNO055Manager:
    def __init__(self, port="/dev/ttyAMA4", baudrate=115200, update_rate=50):
       
        self.target_period = 1.0 / update_rate
        self.uart = serial.Serial(port, baudrate=baudrate)
        self.sensor = adafruit_bno055.BNO055_UART(self.uart)
        
        # Initialize sensor data containers
        self.accel = (0, 0, 0)
        self.gyro = (0, 0, 0)
        self.quaternion = (0, 0, 0, 0)
        
        # Initialize timing statistics
        self.last_loop_time = 0
        self.max_loop_time = 0
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
            logging.warning("IMU thread already running")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._update_loop)
        self._thread.daemon = True
        self._thread.start()
        logging.info("IMU thread started")

    def stop(self):
        """Stop the IMU update thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join()
        self._thread = None
        logging.info("IMU thread stopped")

    def _update_loop(self):
        """Main update loop for reading sensor data."""
        while not self._stop_event.is_set():
            loop_start = time.time()
            
            try:
                # Read acceleration data
                start_time = time.time()
                self.accel = self.sensor.acceleration  # Changed from read_accelerometer()
                accel_time = time.time() - start_time
                self.timing_stats['accel'].append(accel_time)

                # Read gyroscope data
                start_time = time.time()
                self.gyro = self.sensor.gyro  # Changed from read_gyroscope()
                gyro_time = time.time() - start_time
                self.timing_stats['gyro'].append(gyro_time)

                # Read quaternion data
                #start_time = time.time()
                #self.quaternion = self.sensor.quaternion  # Changed from read_quaternion()
                #quat_time = time.time() - start_time
               # self.timing_stats['quaternion'].append(quat_time)

                # Calculate and store loop timing
                loop_time = time.time() - loop_start
                self.last_loop_time = loop_time
                self.max_loop_time = max(self.max_loop_time, loop_time)
                
                if loop_time > self.target_period:
                    self.timing_stats['overruns'] += 1
                    logging.warning(f"IMU timing overrun: {loop_time*1000:.2f}ms (target: {self.target_period*1000:.2f}ms)")
                
                self.timing_stats['total_cycles'] += 1
                
                # Sleep for remaining time if any
                sleep_time = self.target_period - loop_time
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
            except Exception as e:
                logging.error(f"Error in IMU update loop: {str(e)}")
                time.sleep(0.1)  # Brief pause on error

    def get_timing_stats(self):
        """Get current timing statistics.
        
        Returns:
            dict: Dictionary containing timing statistics
        """
        stats = {
            'target_period': self.target_period,
            'last_loop_time': self.last_loop_time,
            'max_loop_time': self.max_loop_time,
            'overruns': self.timing_stats['overruns'],
            'total_cycles': self.timing_stats['total_cycles'],
            'average_read_times': {
                'accel': sum(self.timing_stats['accel']) / len(self.timing_stats['accel']) if self.timing_stats['accel'] else 0,
                'gyro': sum(self.timing_stats['gyro']) / len(self.timing_stats['gyro']) if self.timing_stats['gyro'] else 0,
                'quaternion': sum(self.timing_stats['quaternion']) / len(self.timing_stats['quaternion']) if self.timing_stats['quaternion'] else 0,
            }
        }
        return stats

    def get_accel(self):
        """Get the latest accelerometer reading.
        
        Returns:
            tuple: (x, y, z) acceleration in m/s^2
        """
        return self.accel

    def get_gyro(self):
        """Get the latest gyroscope reading.
        
        Returns:
            tuple: (x, y, z) angular velocity in rad/s
        """
        return self.gyro

    def get_quaternion(self):
        """Get the latest quaternion reading.
        
        Returns:
            tuple: (w, x, y, z) quaternion values
        """
        return self.quaternion

# Example usage:
if __name__ == "__main__":
    # Initialize and start the IMU manager
    imu = BNO055Manager("/dev/ttyUSB0", update_rate=50)
    imu.start()
    
    try:
        # Run for a few seconds to collect data
        time.sleep(5)
        
        # Get and print timing statistics
        stats = imu.get_timing_stats()
        print("\nIMU Timing Statistics:")
        print(f"Target Period: {stats['target_period']*1000:.2f}ms")
        print(f"Last Loop Time: {stats['last_loop_time']*1000:.2f}ms")
        print(f"Max Loop Time: {stats['max_loop_time']*1000:.2f}ms")
        print(f"Overruns: {stats['overruns']}")
        print(f"Total Cycles: {stats['total_cycles']}")
        print("\nAverage Read Times:")
        for sensor, avg_time in stats['average_read_times'].items():
            print(f"{sensor}: {avg_time*1000:.2f}ms")
            
    finally:
        imu.stop()