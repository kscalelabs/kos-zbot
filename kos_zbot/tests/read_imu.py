import asyncio
import time
from pykos import KOS
import numpy as np
import argparse
import csv
from datetime import datetime

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
    print_stats: bool = True,      # Calculate and print statistics at end
    output_file: str = None        # Optional output file for logging data
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

    csv_file = None
    csv_writer = None
    if output_file:
        csv_file = open(output_file, 'w', newline='')
        csv_writer = csv.writer(csv_file)
        # Write header
        csv_writer.writerow(['timestamp', 
                           'accel_x', 'accel_y', 'accel_z',
                           'gyro_x', 'gyro_y', 'gyro_z'])
        print(f"Logging data to: {output_file}")
    
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
            timestamp = datetime.now().isoformat()
            
            # Read all requested measurements
            if read_basic:
                t0 = time.time()
                values = await kos.imu.get_imu_values()
                timing_stats['basic_times'].append(time.time() - t0)
                print(f"\rAccel: {values.accel_x:.2f}, {values.accel_y:.2f}, {values.accel_z:.2f} m/s²", end='')

                # Log to CSV if output file specified
                if csv_writer:
                    csv_writer.writerow([
                        timestamp,
                        values.accel_x, values.accel_y, values.accel_z,
                        values.gyro_x, values.gyro_y, values.gyro_z
                    ])
            
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
    finally:
        if csv_file:
            csv_file.close()
    
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
    parser = argparse.ArgumentParser(description='Run IMU test and log data')
    parser.add_argument('--ip', type=str, default='127.0.0.1',
                      help='IP address of the KOS device')
    parser.add_argument('--time', type=float, default=30.0,
                      help='Test duration in seconds')
    parser.add_argument('--rate', type=float, default=50.0,
                      help='Sampling rate in Hz')
    parser.add_argument('--output', type=str, required=False, default=None,
                      help='Optional output CSV file path for logging data')
    
    args = parser.parse_args()
    TEST_CONFIG = {
        "kos_ip": args.ip,
        "sample_time": args.time,
        "sample_rate": args.rate,
        "read_basic": True,      # Always true for logging accel/gyro
        "read_quaternion": False,  # Disabled for basic logging
        "read_euler": False,      # Disabled for basic logging
        "read_advanced": False,   # Disabled for basic logging
        "print_stats": True,
        "output_file": args.output
    }
    
    asyncio.run(run_imu_test(**TEST_CONFIG))