import asyncio
import matplotlib.pyplot as plt
from pykos import KOS
from collections import defaultdict
import time
import numpy as np

class MotionDataPlotter:
    def __init__(self, ip="192.168.42.1", poll_rate_hz=50):
        self.kos = KOS(ip)
        self.poll_interval = 1.0 / poll_rate_hz
        
        # Servo IDs to monitor
        self.servo_ids = [
            11, 12, 13, 14,  # Left Arm
            21, 22, 23, 24,  # Right Arm
            31, 32, 33, 34, 35, 36,  # Left Leg
            41, 42, 43, 44, 45, 46,  # Right Leg
        ]
        
        # Initialize data storage
        self.timestamps = []
        self.servo_positions = defaultdict(list)
        self.active_servo_ids = set()
        self.imu_data = {
            'accel': defaultdict(list),  # x, y, z
            'gyro': defaultdict(list),   # x, y, z
        }
        
        # Setup plots
        plt.ion()
        self.fig, self.axes = plt.subplots(3, 1, figsize=(12, 12))
        self.fig.suptitle('Robot Motion Analysis')
        
        # Configure subplots
        self.lines = {}
        
        # Servo positions plot
        self.axes[0].set_ylabel('Servo Position (degrees)')
        self.axes[0].set_title('Joint Positions')
        self.axes[0].grid(True)
        
        # Accelerometer plot
        self.axes[1].set_ylabel('Acceleration (m/s²)')
        self.axes[1].set_title('IMU Acceleration')
        self.axes[1].grid(True)
        self.lines['accel_x'], = self.axes[1].plot([], [], label='X', color='red')
        self.lines['accel_y'], = self.axes[1].plot([], [], label='Y', color='green')
        self.lines['accel_z'], = self.axes[1].plot([], [], label='Z', color='blue')
        self.axes[1].legend()
        
        # Gyroscope plot
        self.axes[2].set_xlabel('Time (s)')
        self.axes[2].set_ylabel('Angular Velocity (rad/s)')
        self.axes[2].set_title('IMU Angular Velocity')
        self.axes[2].grid(True)
        self.lines['gyro_x'], = self.axes[2].plot([], [], label='X', color='red')
        self.lines['gyro_y'], = self.axes[2].plot([], [], label='Y', color='green')
        self.lines['gyro_z'], = self.axes[2].plot([], [], label='Z', color='blue')
        self.axes[2].legend()
        
        # Adjust layout to make room for servo legend
        self.fig.subplots_adjust(left=0.25, right=0.95)
        self.start_time = None

    def _add_new_servo(self, servo_id):
        """Add a new servo line to the position plot"""
        if servo_id not in self.lines:
            line, = self.axes[0].plot([], [], label=f'Servo {servo_id}')
            self.lines[f'servo_{servo_id}'] = line
            self.active_servo_ids.add(servo_id)
            # Update legend with only active servos
            handles = [self.lines[f'servo_{sid}'] for sid in sorted(self.active_servo_ids)]
            labels = [f'Servo {sid}' for sid in sorted(self.active_servo_ids)]
            self.axes[0].legend(handles, labels, 
                              bbox_to_anchor=(-0.2, 0.5),
                              loc='center right',
                              borderaxespad=0)

 async def poll_data(self, duration_seconds=30):
    self.start_time = time.time()
    plot_update_rate = 10  # Update plot at 10Hz instead of 50Hz
    samples_per_plot = int(self.poll_interval * plot_update_rate)
    sample_count = 0
    
    try:
        while time.time() - self.start_time < duration_seconds:
            loop_start = time.time()
            
            try:
                # Gather both requests concurrently
                servo_future = self.kos.actuator.get_actuators_state(self.servo_ids)
                imu_future = self.kos.imu.get_imu_values()
                response, imu_values = await asyncio.gather(servo_future, imu_future)
                
                current_time = time.time() - self.start_time
                self.timestamps.append(current_time)
                
                # Process servo data
                for state in response.states:
                    servo_id = state.actuator_id
                    if abs(state.position) < 1e-6:
                        continue
                    if servo_id not in self.active_servo_ids:
                        self._add_new_servo(servo_id)
                    self.servo_positions[servo_id].append(state.position)
                
                # Store IMU data
                self.imu_data['accel']['x'].append(imu_values.accel_x)
                self.imu_data['accel']['y'].append(imu_values.accel_y)
                self.imu_data['accel']['z'].append(imu_values.accel_z)
                self.imu_data['gyro']['x'].append(imu_values.gyro_x)
                self.imu_data['gyro']['y'].append(imu_values.gyro_y)
                self.imu_data['gyro']['z'].append(imu_values.gyro_z)
                
                # Update plot less frequently
                sample_count += 1
                if sample_count >= samples_per_plot:
                    await asyncio.create_task(self._update_plot())
                    sample_count = 0
                
                # Precise timing control
                elapsed = time.time() - loop_start
                sleep_time = self.poll_interval - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    print(f"Warning: Loop took {elapsed*1000:.1f}ms, longer than target {self.poll_interval*1000:.1f}ms")
                    
            except Exception as e:
                print(f"Error polling data: {e}")
                break
                
    except KeyboardInterrupt:
        print("\nStopping data collection...")
    finally:
        plt.ioff()

    def _update_plot(self):
        # Update servo position lines
        for servo_id in self.active_servo_ids:
            line = self.lines[f'servo_{servo_id}']
            line.set_xdata(self.timestamps)
            line.set_ydata(self.servo_positions[servo_id])
        
        # Update accelerometer lines
        self.lines['accel_x'].set_xdata(self.timestamps)
        self.lines['accel_y'].set_xdata(self.timestamps)
        self.lines['accel_z'].set_xdata(self.timestamps)
        self.lines['accel_x'].set_ydata(self.imu_data['accel']['x'])
        self.lines['accel_y'].set_ydata(self.imu_data['accel']['y'])
        self.lines['accel_z'].set_ydata(self.imu_data['accel']['z'])
        
        # Update gyroscope lines
        self.lines['gyro_x'].set_xdata(self.timestamps)
        self.lines['gyro_y'].set_xdata(self.timestamps)
        self.lines['gyro_z'].set_xdata(self.timestamps)
        self.lines['gyro_x'].set_ydata(self.imu_data['gyro']['x'])
        self.lines['gyro_y'].set_ydata(self.imu_data['gyro']['y'])
        self.lines['gyro_z'].set_ydata(self.imu_data['gyro']['z'])
        
        # Adjust plot limits for all subplots
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def save_data(self, filename):
        """Save collected data to a numpy file."""
        data_dict = {
            'timestamps': np.array(self.timestamps),
            'accel_x': np.array(self.imu_data['accel']['x']),
            'accel_y': np.array(self.imu_data['accel']['y']),
            'accel_z': np.array(self.imu_data['accel']['z']),
            'gyro_x': np.array(self.imu_data['gyro']['x']),
            'gyro_y': np.array(self.imu_data['gyro']['y']),
            'gyro_z': np.array(self.imu_data['gyro']['z']),
        }
        
        # Add servo positions
        for servo_id in self.active_servo_ids:
            data_dict[f'servo_{servo_id}'] = np.array(self.servo_positions[servo_id])
        
        np.savez(filename, **data_dict)

async def main():
    plotter = MotionDataPlotter(poll_rate_hz=50)
    try:
        await plotter.poll_data(duration_seconds=60)
        # Optionally save the data
        plotter.save_data('motion_data.npz')
    except KeyboardInterrupt:
        pass
    
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    asyncio.run(main())