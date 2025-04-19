import asyncio
import matplotlib.pyplot as plt
from pykos import KOS
from collections import defaultdict
import time
import numpy as np

class IMUDataPlotter:
    def __init__(self, ip="192.168.42.1", poll_rate_hz=50):
        self.kos = KOS(ip)
        self.poll_interval = 1.0 / poll_rate_hz
        
        # Initialize data storage
        self.timestamps = []
        self.data = {
            'accel': defaultdict(list),  # x, y, z
            'gyro': defaultdict(list),   # x, y, z
            'euler': defaultdict(list),  # roll, pitch, yaw
        }
        
        # Setup plots
        plt.ion()
        self.fig, self.axes = plt.subplots(3, 1, figsize=(12, 10))
        self.fig.suptitle('IMU Data Over Time')
        
        # Configure subplots
        self.lines = {}
        
        # Accelerometer plot
        self.axes[0].set_ylabel('Acceleration (m/s²)')
        self.axes[0].grid(True)
        self.lines['accel_x'], = self.axes[0].plot([], [], label='X')
        self.lines['accel_y'], = self.axes[0].plot([], [], label='Y')
        self.lines['accel_z'], = self.axes[0].plot([], [], label='Z')
        self.axes[0].legend()
        
        # Gyroscope plot
        self.axes[1].set_ylabel('Angular Velocity (rad/s)')
        self.axes[1].grid(True)
        self.lines['gyro_x'], = self.axes[1].plot([], [], label='X')
        self.lines['gyro_y'], = self.axes[1].plot([], [], label='Y')
        self.lines['gyro_z'], = self.axes[1].plot([], [], label='Z')
        self.axes[1].legend()
        
        # Euler angles plot
        self.axes[2].set_xlabel('Time (s)')
        self.axes[2].set_ylabel('Angle (degrees)')
        self.axes[2].grid(True)
        self.lines['euler_roll'], = self.axes[2].plot([], [], label='Roll')
        self.lines['euler_pitch'], = self.axes[2].plot([], [], label='Pitch')
        self.lines['euler_yaw'], = self.axes[2].plot([], [], label='Yaw')
        self.axes[2].legend()
        
        self.fig.tight_layout()
        self.start_time = None

    async def poll_imu_data(self, duration_seconds=30):
        self.start_time = time.time()
        
        try:
            while time.time() - self.start_time < duration_seconds:
                try:
                    current_time = time.time() - self.start_time
                    self.timestamps.append(current_time)
                    
                    # Get IMU data
                    values = await self.kos.imu.get_imu_values()
                    euler = await self.kos.imu.get_euler_angles()
                    
                    # Store accelerometer data
                    self.data['accel']['x'].append(values.accel_x)
                    self.data['accel']['y'].append(values.accel_y)
                    self.data['accel']['z'].append(values.accel_z)
                    
                    # Store gyroscope data
                    self.data['gyro']['x'].append(values.gyro_x)
                    self.data['gyro']['y'].append(values.gyro_y)
                    self.data['gyro']['z'].append(values.gyro_z)
                    
                    # Store euler angles
                    self.data['euler']['roll'].append(euler.roll)
                    self.data['euler']['pitch'].append(euler.pitch)
                    self.data['euler']['yaw'].append(euler.yaw)
                    
                    # Update plot
                    self._update_plot()
                    
                    # Wait for next polling interval
                    await asyncio.sleep(self.poll_interval)
                    
                except Exception as e:
                    print(f"Error polling IMU: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("\nStopping data collection...")
        finally:
            plt.ioff()

    def _update_plot(self):
        # Update accelerometer lines
        self.lines['accel_x'].set_xdata(self.timestamps)
        self.lines['accel_y'].set_xdata(self.timestamps)
        self.lines['accel_z'].set_xdata(self.timestamps)
        self.lines['accel_x'].set_ydata(self.data['accel']['x'])
        self.lines['accel_y'].set_ydata(self.data['accel']['y'])
        self.lines['accel_z'].set_ydata(self.data['accel']['z'])
        
        # Update gyroscope lines
        self.lines['gyro_x'].set_xdata(self.timestamps)
        self.lines['gyro_y'].set_xdata(self.timestamps)
        self.lines['gyro_z'].set_xdata(self.timestamps)
        self.lines['gyro_x'].set_ydata(self.data['gyro']['x'])
        self.lines['gyro_y'].set_ydata(self.data['gyro']['y'])
        self.lines['gyro_z'].set_ydata(self.data['gyro']['z'])
        
        # Update euler angle lines
        self.lines['euler_roll'].set_xdata(self.timestamps)
        self.lines['euler_pitch'].set_xdata(self.timestamps)
        self.lines['euler_yaw'].set_xdata(self.timestamps)
        self.lines['euler_roll'].set_ydata(self.data['euler']['roll'])
        self.lines['euler_pitch'].set_ydata(self.data['euler']['pitch'])
        self.lines['euler_yaw'].set_ydata(self.data['euler']['yaw'])
        
        # Adjust plot limits for all subplots
        for ax in self.axes:
            ax.relim()
            ax.autoscale_view()
        
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

    def save_data(self, filename):
        """Save collected data to a numpy file."""
        np.savez(filename,
                 timestamps=np.array(self.timestamps),
                 accel_x=np.array(self.data['accel']['x']),
                 accel_y=np.array(self.data['accel']['y']),
                 accel_z=np.array(self.data['accel']['z']),
                 gyro_x=np.array(self.data['gyro']['x']),
                 gyro_y=np.array(self.data['gyro']['y']),
                 gyro_z=np.array(self.data['gyro']['z']),
                 euler_roll=np.array(self.data['euler']['roll']),
                 euler_pitch=np.array(self.data['euler']['pitch']),
                 euler_yaw=np.array(self.data['euler']['yaw']))

async def main():
    plotter = IMUDataPlotter(poll_rate_hz=50)
    try:
        await plotter.poll_imu_data(duration_seconds=60)
        # Optionally save the data
        plotter.save_data('imu_data.npz')
    except KeyboardInterrupt:
        pass
    
    plt.ioff()
    plt.show()

if __name__ == "__main__":
    asyncio.run(main())