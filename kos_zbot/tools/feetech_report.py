#!/usr/bin/env python3

import argparse
import sys
from kos_zbot.feetech_actuator import SCSMotorController
import time
from tabulate import tabulate

def steps_to_degrees(steps: int) -> float:
    """Convert steps to degrees"""
    return (steps * 360 / 4095) - 180

def steps_to_rpm(steps: int) -> float:
    """Convert velocity steps to RPM"""
    # Note: This conversion factor might need adjustment based on your servo specs
    return steps * (60 / 4095)  # Approximate conversion

def main():
    parser = argparse.ArgumentParser(description='Report Feetech servo status')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                      help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=500000,
                      help='Baudrate (default: 500000)')
    parser.add_argument('--ids', type=str, required=True,
                      help='Comma-separated list of actuator IDs to report')
    parser.add_argument('--watch', action='store_true',
                      help='Continuously watch servo status')
    parser.add_argument('--interval', type=float, default=0.5,
                      help='Update interval in seconds when watching (default: 0.5)')

    args = parser.parse_args()

    try:
        # Parse actuator IDs
        actuator_ids = [int(id_str) for id_str in args.ids.split(',')]
        if not actuator_ids:
            print("Error: At least one actuator ID is required")
            sys.exit(1)

        # Initialize motor controller
        controller = SCSMotorController(
            device=args.device,
            baudrate=args.baudrate,
            rate=100
        )

        time.sleep(0.5)  # Brief pause to ensure serial connection is stable

        def print_status():
            # Get status for all servos
            headers = ["ID", "Position (°)", "Velocity (RPM)", "Load (%)", "Current (mA)", "Voltage (V)", "Temp (°C)"]
            rows = []
            
            for aid in actuator_ids:
                params = controller.read_all_servo_params(aid, show_results=False)
                if params:
                    position_deg = steps_to_degrees(params.get("Present Position", 0))
                    velocity_rpm = steps_to_rpm(params.get("Present Speed", 0))
                    
                    row = [
                        aid,
                        f"{position_deg:.1f}",
                        f"{velocity_rpm:.1f}",
                        f"{params.get('Present Load', 0)}",
                        f"{params.get('Present Current', 0)}",
                        f"{params.get('Present Voltage', 0) / 10:.1f}",  # Convert to volts
                        f"{params.get('Present Temperature', 0)}"
                    ]
                    rows.append(row)
                else:
                    rows.append([aid, "ERROR", "ERROR", "ERROR", "ERROR", "ERROR", "ERROR"])

            # Clear screen in watch mode
            if args.watch:
                print("\033[2J\033[H")  # ANSI escape codes to clear screen and move cursor to top
                print(f"Servo Status Report (Press Ctrl+C to exit) - {time.strftime('%H:%M:%S')}")
            
            print(tabulate(
                rows,
                headers=headers,
                tablefmt="grid",
                numalign="right",
                stralign="right"
            ))

        if args.watch:
            try:
                while True:
                    print_status()
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nStopping status watch...")
        else:
            print_status()

    except ValueError as e:
        print(f"Error parsing actuator IDs: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'controller' in locals():
            controller.stop()

if __name__ == '__main__':
    main()