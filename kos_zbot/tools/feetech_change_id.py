import argparse
import sys
import time
from kos_zbot.actuator import SCSMotorController
import logging
logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description='Change ID for a Feetech servo on the bus')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                        help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=1000000,
                        help='Baudrate for communication (default: 1000000)')
    parser.add_argument('--current-id', type=int, required=True,
                        help='Current ID of the servo (required)')
    parser.add_argument('--new-id', type=int, required=True,
                        help='New ID to set for the servo (required, 0-253)')

    args = parser.parse_args()

    try:
        if not (0 <= args.current_id <= 253 and 0 <= args.new_id <= 253):
            print("Error: IDs must be between 0 and 253")
            sys.exit(1)

        print(f"\nInitializing controller on {args.device} at {args.baudrate} baud...")
        controller = SCSMotorController(
            device=args.device,
            baudrate=args.baudrate,
            rate=10
        )

        time.sleep(2)  # Brief pause to ensure serial connection is established TODO: necessary?

        success = controller.change_id(args.current_id, args.new_id)

        if success:
            print(f"\nSuccessfully changed servo ID from {args.current_id} to {args.new_id}.")
        else:
            print("\nFailed to change servo ID. See logs for details.")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'controller' in locals():
            controller.stop()
            

if __name__ == '__main__':
    main()