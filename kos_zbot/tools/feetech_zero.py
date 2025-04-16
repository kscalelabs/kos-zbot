#!/usr/bin/env python3

import argparse
import sys
from kos_zbot.feetech_actuator import SCSMotorController
import time

def main():
    parser = argparse.ArgumentParser(description='Zero Feetech servo positions')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                      help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=500000,
                      help='Baudrate (default: 500000)')
    parser.add_argument('--ids', type=str, required=True,
                      help='Comma-separated list of actuator IDs to zero')

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
            rate=100  # Rate doesn't matter since we're not using the update loop
        )

        # Brief pause to ensure serial connection is stable
        time.sleep(0.5)

        # Zero each actuator
        print("\nZeroing actuators...")
        for actuator_id in actuator_ids:
            print(f"\nZeroing actuator {actuator_id}...")
            try:
                controller.set_zero_position(actuator_id)
                print(f"Successfully zeroed actuator {actuator_id}")
            except Exception as e:
                print(f"Failed to zero actuator {actuator_id}: {e}")

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