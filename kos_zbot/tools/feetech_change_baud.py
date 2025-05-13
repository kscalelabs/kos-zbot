#!/usr/bin/env python3

import argparse
import sys
import time
from kos_zbot.actuator import SCSMotorController
import logging
logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description='Change baudrate for all Feetech servos on the bus')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                        help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--current-baudrate', type=int, default=500000,
                        help='Current baudrate for communication (default: 500000)')
    parser.add_argument('--new-baudrate', type=int, required=True,
                        help='New baudrate to set (required, e.g. 1000000, 500000, 250000)')

    args = parser.parse_args()

    try:
        # Validate new baudrate
        if args.new_baudrate not in (1000000, 500000, 250000):
            print("Error: new-baudrate must be one of: 1000000, 500000, 250000")
            sys.exit(1)

        print(f"\nInitializing controller on {args.device} at {args.current_baudrate} baud...")
        controller = SCSMotorController(
            device=args.device,
            baudrate=args.current_baudrate,
            rate=10
        )

        time.sleep(2)  # Brief pause to ensure serial connection is stable

        print(f"\nChanging baudrate for all servos on the bus to {args.new_baudrate}...")
        success = controller.change_baudrate(args.new_baudrate)
        
        if success:
            print(f"\nSuccessfully changed baudrate to {args.new_baudrate} for all servos.")
        else:
            print("\nFailed to change baudrate for all servos. See logs for details.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'controller' in locals():
            controller.stop()

if __name__ == '__main__':
    main()