import asyncio
import time
import numpy as np
import sys
import argparse
from pykos import KOS

async def run_move_group(
        # Command
        actuator_ids: list[int], # Ordered list, Actuator id
        actuator_moves: list[float], # Ordered list, Move angles
        delay: float = 0, # seconds; Creates stepwise zero rather than all-at-once
        # Connectivity
        kos_ip: str = "127.0.0.1",
        # Motor Params
        kp: float = 20.0,
        kd: float = 5.0,
        ki: float = 0.0,
        max_torque: float = 100.0,
        acceleration: float = 0.0,
        torque_enabled: bool = True,
):
    # Cleaning inputs
    if delay < 0.0:
        delay = 0.0


    print(f"kos_ip {kos_ip}")
    kos = KOS(kos_ip)

    # Configure each actuator
    print("\nConfiguring actuators...")
    for actuator_id in actuator_ids:
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=kp, kd=kd, ki=ki,
            acceleration=acceleration,
            max_torque=max_torque,
            torque_enabled=torque_enabled
        )

    print("\nMoving to Position")
    try:
        await asyncio.sleep(1.0)

        if delay > 0.001:
            for i in range(len(actuator_ids)):
                command = []
                command.append({
                    'actuator_id': actuator_ids[i],
                    'position': actuator_moves[i],
                })
                await kos.actuator.command_actuators(command)
                await asyncio.sleep(delay)
        else:
            commands = []
            for i in range(len(actuator_ids)):
                commands.append({
                    'actuator_id': actuator_ids[i],
                    'position': actuator_moves[i],
                })
            await kos.actuator.command_actuators(commands)

    except KeyboardInterrupt:
        print("\nMove Interrupted!")

    await kos.close()
    print("\nMove Complete")

def main():
    parser = argparse.ArgumentParser(
        "Move Feetech to Position; default Zero"
    )
    parser.add_argument('--ip',type=str, default='127.0.0.1',
                        help="KOS Server IP (default 127)")
    parser.add_argument('--device', type=str, default='/dev/ttyAMA5',
                      help='Serial port device (default: /dev/ttyAMA5)')
    parser.add_argument('--baudrate', type=int, default=500000,
                      help='Baudrate (default: 500000)')
    parser.add_argument('--ids', type=str,
                      default='11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46', # Curreent Zbot Joint Layout default
                      help='Comma-separated list of actuator IDs to zero')
    parser.add_argument('--pos', type=str, default='0.0',
                      help='Command-seperated list of angles (deg) associated with actuator id list.\nIf blank, zeros. If only 1 value, will apply to all given ids.')
    parser.add_argument('--delay', type=float, default=0.0,
                      help="Delay time for staggered movements per given actuator.")

    args = parser.parse_args()

    try:
        # Parse actuator IDs
        actuator_ids = [int(id_str) for id_str in args.ids.split(',')]
        if not actuator_ids:
            print("Error: At least one actuator ID is required")
            sys.exit(1)
        # Parse positions
        positions = [float(position) for position in args.pos.split(',')]
        if not positions:
            print("Error: Unable to register position as float value")
            sys.exit(1)
    except ValueError as e:
        print(f"Error parsing actuator IDs: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Apply single value to all actuator ids
    if len(positions) == 1:
        [positions[0] for _ in range(len(actuator_ids))]

    print("HELLO **********************************")
    asyncio.run(run_move_group(
        actuator_ids = actuator_ids,
        actuator_moves = positions,
        kos_ip = args.ip,
        delay = args.delay
    ))

if __name__ == '__main__':
    main()







