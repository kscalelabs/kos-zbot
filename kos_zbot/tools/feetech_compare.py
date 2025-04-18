#!/usr/bin/env python3

import argparse
import sys
from kos_zbot.actuator import SCSMotorController
import time

def main():
    parser = argparse.ArgumentParser(description='Compare Feetech servo parameters')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                      help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=500000,
                      help='Baudrate (default: 500000)')
    parser.add_argument('--ids', type=str, required=True,
                      help='Comma-separated list of actuator IDs to compare')

    args = parser.parse_args()

    try:
        # Parse actuator IDs
        actuator_ids = [int(id_str) for id_str in args.ids.split(',')]
        if len(actuator_ids) < 2:
            print("Error: At least 2 actuator IDs are required for comparison")
            sys.exit(1)

        # Initialize motor controller
        controller = SCSMotorController(
            device=args.device,
            baudrate=args.baudrate,
            rate=100  # Rate doesn't matter since we're not using the update loop
        )

        # No need to start the controller thread since we're just reading parameters
        time.sleep(0.5)  # Brief pause to ensure serial connection is stable

        # Perform comparison
        controller.compare_actuator_params(actuator_ids=actuator_ids)

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