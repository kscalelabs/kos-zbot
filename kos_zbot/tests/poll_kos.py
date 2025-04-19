import asyncio
from pykos import KOS
import time
import numpy as np
from collections import deque
from statistics import mean, stdev

class MotionDataCollector:
    def __init__(self, ip="192.168.42.1", poll_rate_hz=50, buffer_size=3000):
        self.kos = KOS(ip)
        self.target_interval = 1.0 / poll_rate_hz
        self.buffer_size = buffer_size

        self.target_interval_ns = int(self.target_interval * 1e9)  # Convert to nanoseconds
        self.next_target_time = None
        
        # Servo IDs to monitor
        self.servo_ids = [
            11, 12, 13, 14,  # Left Arm
            21, 22, 23, 24,  # Right Arm
            31, 32, 33, 34, 35, 36,  # Left Leg
            41, 42, 43, 44, 45, 46,  # Right Leg
        ]
        
        # Initialize circular buffers for performance metrics
        self.loop_times = deque(maxlen=100)  # Last 100 loop execution times
        self.poll_intervals = deque(maxlen=100)  # Last 100 intervals between polls
        self.last_poll_time = None
        
        # Data storage
        self.timestamps = np.zeros(buffer_size)
        self.servo_positions = {sid: np.zeros(buffer_size) for sid in self.servo_ids}
        self.imu_data = {
            'accel': {axis: np.zeros(buffer_size) for axis in ['x', 'y', 'z']},
            'gyro': {axis: np.zeros(buffer_size) for axis in ['x', 'y', 'z']}
        }
        
        self.current_index = 0
        self.start_time = None

    async def _poll_single_cycle(self):
        """Execute a single polling cycle and return the data"""
        # Start concurrent requests
        servo_future = self.kos.actuator.get_actuators_state(self.servo_ids)
        imu_future = self.kos.imu.get_imu_values()
        
        # Wait for both responses
        servo_response, imu_values = await asyncio.gather(servo_future, imu_future)
        
        return servo_response, imu_values

    def _log_metrics(self, loop_time, current_time):
        """Log and calculate performance metrics"""
        self.loop_times.append(loop_time * 1000)  # Convert to ms
        
        if self.last_poll_time is not None:
            interval = current_time - self.last_poll_time
            self.poll_intervals.append(interval * 1000)  # Convert to ms
        
        self.last_poll_time = current_time

    def print_metrics(self):
        """Print current performance metrics"""
        if not self.loop_times or not self.poll_intervals:
            return
        
        print("\nPerformance Metrics:")
        print(f"Loop Execution Time (ms): mean={mean(self.loop_times):.2f}, std={stdev(self.loop_times):.2f}")
        print(f"Poll Interval (ms): mean={mean(self.poll_intervals):.2f}, std={stdev(self.poll_intervals):.2f}")
        print(f"Actual Poll Rate (Hz): {1000/mean(self.poll_intervals):.1f}")
        print(f"Samples Collected: {self.current_index}")
        
        # Calculate timing violations
        target_ms = self.target_interval * 1000
        violations = sum(1 for t in self.poll_intervals if abs(t - target_ms) > 1)  # >1ms deviation
        violation_rate = (violations / len(self.poll_intervals)) * 100
        print(f"Timing Violations: {violation_rate:.1f}% (>1ms deviation from target)")

    async def poll_data(self, duration_seconds=30):
        self.start_time = time.time()
        self.next_target_time = time.time_ns()  # Initialize first target time
        last_metrics_time = self.start_time
        metrics_interval = 1.0
        
        print(f"Starting data collection at target rate of {1/self.target_interval:.1f} Hz")
        
        try:
            while (time.time() - self.start_time < duration_seconds and 
                   self.current_index < self.buffer_size):
                
                loop_start = time.time()
                
                try:
                    # Poll data
                    servo_response, imu_values = await self._poll_single_cycle()
                    
                    # Record timestamp
                    current_time = time.time()
                    self.timestamps[self.current_index] = current_time - self.start_time
                    
                    # Store servo data
                    for state in servo_response.states:
                        if abs(state.position) > 1e-6:  # Skip zero positions
                            self.servo_positions[state.actuator_id][self.current_index] = state.position
                    
                    # Store IMU data
                    self.imu_data['accel']['x'][self.current_index] = imu_values.accel_x
                    self.imu_data['accel']['y'][self.current_index] = imu_values.accel_y
                    self.imu_data['accel']['z'][self.current_index] = imu_values.accel_z
                    self.imu_data['gyro']['x'][self.current_index] = imu_values.gyro_x
                    self.imu_data['gyro']['y'][self.current_index] = imu_values.gyro_y
                    self.imu_data['gyro']['z'][self.current_index] = imu_values.gyro_z
                    
                    # Log metrics
                    self._log_metrics(time.time() - loop_start, current_time)
                    
                    # Print metrics periodically
                    if current_time - last_metrics_time >= metrics_interval:
                        self.print_metrics()
                        last_metrics_time = current_time
                    
                    # Increment index
                    self.current_index += 1
                    
                                        # More precise timing control using nanosecond timing
                    self.next_target_time += self.target_interval_ns
                    current_ns = time.time_ns()
                    sleep_ns = self.next_target_time - current_ns
                    
                    if sleep_ns > 0:
                        # Convert back to seconds for asyncio.sleep
                        await asyncio.sleep(sleep_ns / 1e9)
                    else:
                        # If we're behind, reset the target time
                        self.next_target_time = current_ns + self.target_interval_ns
                        await asyncio.sleep(0)  # Yield to event loop
                    
                except Exception as e:
                    print(f"Error in polling cycle: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\nData collection interrupted by user")
        finally:
            self.print_metrics()

    def save_data(self, filename):
        """Save collected data to a numpy file"""
        data_dict = {
            'timestamps': self.timestamps[:self.current_index],
            'accel_x': self.imu_data['accel']['x'][:self.current_index],
            'accel_y': self.imu_data['accel']['y'][:self.current_index],
            'accel_z': self.imu_data['accel']['z'][:self.current_index],
            'gyro_x': self.imu_data['gyro']['x'][:self.current_index],
            'gyro_y': self.imu_data['gyro']['y'][:self.current_index],
            'gyro_z': self.imu_data['gyro']['z'][:self.current_index],
        }
        
        # Add servo positions
        for servo_id in self.servo_ids:
            data_dict[f'servo_{servo_id}'] = self.servo_positions[servo_id][:self.current_index]
        
        np.savez(filename, **data_dict)
        print(f"Data saved to {filename}")

async def main():
    collector = MotionDataCollector(poll_rate_hz=50)
    await collector.poll_data(duration_seconds=60)
    collector.save_data('motion_data.npz')

if __name__ == "__main__":
    asyncio.run(main())