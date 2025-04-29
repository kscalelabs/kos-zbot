import asyncio
from pykos import KOS
import argparse
import sys

async def run_torque_off(
    # Selection
    actuator_ids: list[int],
    kos_ip: str = "127.0.0.1",
    torque_enabled: bool = False,
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 0.0,
):
    print(f"kos_ip: {kos_ip}")
    kos = KOS(kos_ip)

    for actuator_id in actuator_ids:
        try:
            await kos.actuator.configure_actuator(
                actuator_id=actuator_id,
                kp=kp, kd=kd, ki=ki,
                acceleration=acceleration,
                max_torque=max_torque,
                torque_enabled=torque_enabled
            )
        except KeyboardInterrupt:
            print("\nTest interrupted!")
        except Exception as e:
            print(f"Error for actuator {actuator_id}: {e}")

    await kos.close()


def main():
    parser = argparse.ArgumentParser(
        "Disable torque to all motors; brute force thru all possible IDs"
    )
    parser.add_argument('--ip',type=str, default='127.0.0.1',
                        help="KOS Server IP (default 127)")
    parser.add_argument('--lock', type=bool, default='false',
                        help="Make it lock instead of slack")
    parser.add_argument('--ids', type=str,
                        default="11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46",
                        help="Comma-separated list of actuator IDs to zero")
    args = parser.parse_args()

    try:
        actuator_ids = [int(id_str) for id_str in args.ids.split(',')]
        if not actuator_ids:
            print("Error: At least one actuator ID is required")
            sys.exit(1)
    except ValueError as e:
        print(f"Error parsing actuator IDs: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    asyncio.run(run_torque_off(
        kos_ip=args.ip,
        torque_enabled=args.lock,
        actuator_ids=actuator_ids,
    ))


if __name__ == "__main__":
    main()


