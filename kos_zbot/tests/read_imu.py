import asyncio
import time
from pykos import KOS
import numpy as np

async def run_imu_test(
    kos_ip: str = "127.0.0.1",
    # Test parameters
    sample_time: float = 10.0,     # Total test duration in seconds
    sample_rate: float = 50.0,     # Desired sampling rate in Hz
    # Test modes
    read_basic: bool = True,       # Read accelerometer, gyro, magnetometer
    read_quaternion: bool = True,  # Read quaternion orientation
    read_euler: bool = True,       # Read euler angles
    read_advanced: bool = True,    # Read linear acceleration, gravity, temperature
    print_stats: bool = True      # Calculate and print statistics at end
):
    """Run a test of the IMU service reading various measurements.
    
    Args:
        kos_ip: IP address of the KOS device
        sample_time: How long to run the test in seconds
        sample_rate: Target rate for reading measurements in Hz
        read_basic: Whether to read basic IMU values
        read_quaternion: Whether to read quaternion orientation
        read_euler: Whether to read euler angles
        read_advanced: Whether to read advanced values
        print_stats: Whether to calculate and print statistics at end
    """
    # Connect to KOS
    kos = KOS(kos_ip)
    
    # Calculate timing parameters
    period = 1.0 / sample_rate
    iterations = int(sample_time * sample_rate)
    
    # Storage for timing statistics
    timing_stats = {
        'loop_times': [],
        'basic_times': [],
        'quat_times': [],
        'euler_times': [],
        'advanced_times': []
    }
    
    print(f"\nStarting IMU test:")
    print(f"- Duration: {sample_time:.1f} seconds")
    print(f"- Target rate: {sample_rate:.1f} Hz")
    print(f"- Target period: {period*1000:.1f} ms")
    print("\nReading measurements...")
    
    try:
        for i in range(iterations):
            loop_start = time.time()
            
            # Read all requested measurements
            if read_basic:
                t0 = time.time()
                values = await kos.imu.get_imu_values()
                timing_stats['basic_times'].append(time.time() - t0)
                print(f"\rAccel: {values.accel_x:.2f}, {values.accel_y:.2f}, {values.accel_z:.2f} m/s²", end='')
            
            if read_quaternion:
                t0 = time.time()
                quat = await kos.imu.get_quaternion()
                timing_stats['quat_times'].append(time.time() - t0)
                if i % 10 == 0:  # Print less frequently
                    print(f" | Quat: {quat.w:.2f}, {quat.x:.2f}, {quat.y:.2f}, {quat.z:.2f}", end='')
            
            if read_euler:
                t0 = time.time()
                euler = await kos.imu.get_euler_angles()
                timing_stats['euler_times'].append(time.time() - t0)
                print(f" | Euler: {euler.roll:.1f}, {euler.pitch:.1f}, {euler.yaw:.1f}°", end='')
            
            if read_advanced:
                t0 = time.time()
                advanced = await kos.imu.get_imu_advanced_values()
                timing_stats['advanced_times'].append(time.time() - t0)
                if i % 10 == 0:  # Print less frequently
                    print(f" | Temp: {advanced.temp:.1f}°C", end='')
            
            # Calculate loop timing and sleep if needed
            loop_time = time.time() - loop_start
            timing_stats['loop_times'].append(loop_time)
            
            sleep_time = period - loop_time
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    
    if print_stats:
        print("\n\nTiming Statistics:")
        loop_times = np.array(timing_stats['loop_times']) * 1000  # Convert to ms
        print(f"Loop timing (ms): mean={loop_times.mean():.1f}, min={loop_times.min():.1f}, "
              f"max={loop_times.max():.1f}, std={loop_times.std():.1f}")
        
        if read_basic:
            times = np.array(timing_stats['basic_times']) * 1000
            print(f"Basic read (ms): mean={times.mean():.1f}, min={times.min():.1f}, "
                  f"max={times.max():.1f}, std={times.std():.1f}")
        
        if read_quaternion:
            times = np.array(timing_stats['quat_times']) * 1000
            print(f"Quaternion read (ms): mean={times.mean():.1f}, min={times.min():.1f}, "
                  f"max={times.max():.1f}, std={times.std():.1f}")
        
        if read_euler:
            times = np.array(timing_stats['euler_times']) * 1000
            print(f"Euler read (ms): mean={times.mean():.1f}, min={times.min():.1f}, "
                  f"max={times.max():.1f}, std={times.std():.1f}")
        
        if read_advanced:
            times = np.array(timing_stats['advanced_times']) * 1000
            print(f"Advanced read (ms): mean={times.mean():.1f}, min={times.min():.1f}, "
                  f"max={times.max():.1f}, std={times.std():.1f}")
    
    await kos.close()
    print("\nTest complete!")

if __name__ == "__main__":
    # Test configuration
    TEST_CONFIG = {
        # Connection settings
        "kos_ip": "127.0.0.1",  # Replace with your KOS IP
        
        # Test parameters
        "sample_time": 30.0,    # Run for 30 seconds
        "sample_rate": 50.0,    # Target 50 Hz sampling
        
        # Test modes
        "read_basic": True,     # Read accelerometer, gyro, magnetometer
        "read_quaternion": True, # Read quaternion orientation
        "read_euler": True,     # Read euler angles
        "read_advanced": True,  # Read linear acceleration, gravity, temperature
        "print_stats": True     # Print timing statistics at end
    }
    
    asyncio.run(run_imu_test(**TEST_CONFIG))