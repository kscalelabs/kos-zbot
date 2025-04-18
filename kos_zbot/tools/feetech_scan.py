#!/usr/bin/env python3

import argparse
import sys
from kos_zbot.actuator import SCSMotorController
import time
from tabulate import tabulate
from tqdm import tqdm

MODEL_MAP = {
    777: "STS3215",   # 0x0309
    2825: "STS3250"   # 0x0B09
}

def scan_servos(controller: SCSMotorController, id_range: range) -> list:
    """Scan for servos in the given ID range and return their basic info"""
    found_servos = []
    
    with tqdm(id_range, desc="Scanning servos", unit="ID") as pbar:
        for servo_id in pbar:
            model_number, result, error = controller.packet_handler.ping(servo_id)
            if result == 0:  # COMM_SUCCESS
                found_servos.append({
                    "id": servo_id,
                    "model": MODEL_MAP.get(model_number, f"Unknown Model {model_number}")
                })
                
                pbar.set_description(f"Found servo ID {servo_id}")
    
    return found_servos

def main():
    parser = argparse.ArgumentParser(description='Scan for Feetech servos on the bus')
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                      help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=500000,
                      help='Baudrate (default: 500000)')
    parser.add_argument('--start-id', type=int, default=1,
                      help='Start ID for scanning (default: 1)')
    parser.add_argument('--end-id', type=int, default=255,
                      help='End ID for scanning (default: 255)')

    args = parser.parse_args()

    try:
        # Validate ID range
        if not 0 <= args.start_id <= args.end_id <= 255:
            print("Error: ID range must be between 0 and 255")
            sys.exit(1)

        # Initialize motor controller
        print(f"\nInitializing controller on {args.device} at {args.baudrate} baud...")
        controller = SCSMotorController(
            device=args.device,
            baudrate=args.baudrate,
            rate=100
        )

        time.sleep(0.5)  # Brief pause to ensure serial connection is stable

        print(f"\nScanning for servos (ID range: {args.start_id}-{args.end_id})...")
        found_servos = scan_servos(controller, range(args.start_id, args.end_id + 1))

        if found_servos:
            print(f"\nFound {len(found_servos)} servo(s):")
            
            # Prepare table data
            headers = ["ID", "Model"]
            rows = [
                [servo["id"], servo["model"]]
                for servo in found_servos
            ]
            
            print(tabulate(
                rows,
                headers=headers,
                tablefmt="grid",
                numalign="right",
                stralign="right"
            ))
        else:
            print("\nNo servos found on the bus!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'controller' in locals():
            controller.stop()

if __name__ == '__main__':
    main()