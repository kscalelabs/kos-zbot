""" Overload test for testing wires, motor performance in overload scenario
Straightforward "got-to-position" and hold. Check that soft limits do not prevent.
Caution on orientations of motors.
"""

import asyncio
import time
import numpy as np
import signal
from pykos import KOS
import logging
from kos_zbot.tests.kos_connection import kos_ready_async

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Or DEBUG for more verbosity
    return logger


async def overload(
    actuator_ids: list[int] = [12,13,14],
    actuator_pos: list[float] = [30], # degrees
    kos_ip: str = "127.0.0.1",
    # Duration and Amplitude of test
    duration: float = 3600.0,  # seconds
    sample_rate: float = 50.0,  # Hz
    start_pos: float = 0.0,  # degrees
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 0.0,
    torque_enabled: bool = True,
):
    """Run motors to a given position for extended prior of time.

    Args:
        actuator_ids: List of actuator IDs to test
        actuator_pos: Positions of actuators, corresponding to actuator_ids; if only one value given, apply to all.
        kos_ip: IP address of the KOS device
        duration: Duration of the test in seconds
        sample_rate: Sample rate of the test in Hz
        start_pos: Starting position of the test in degrees
        kp: Position gain
        kd: Velocity gain
        ki: Integral gain
        max_torque: Maximum torque limit
        acceleration: Acceleration limit (0 = unlimited)
        torque_enabled: If True, torque is enabled
    """

    log = get_logger(__name__)
    if await kos_ready_async(kos_ip):
        kos = KOS(kos_ip)
    else:
        log.error("KOS service not available at %s:50051", kos_ip)
        return

    # Interpret actuator positions
    if len(actuator_pos) == 1:
        actuator_pos = [actuator_pos[0] for _ in range(len(actuator_ids))]
    elif len(actuator_pos) != len(actuator_ids):
        log.error("Incorrect number of indices on actuator positions; Must be 1 or Correspond to ID count %s, not given %s", len(actuator_ids), len(actuator_pos))
        return

    interrupted = False

    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        log.info("sigint received")

    signal.signal(signal.SIGINT, handle_sigint)

    try:
        state_resp = await kos.actuator.get_actuators_state()
        available_ids = {s.actuator_id for s in state_resp.states}
    except Exception as e:
        log.error(f"No actuators available: {e}")
        return

    # Validating Actuators and Positions
    valid = [(aid,apos) for aid, apos in zip(actuator_ids, actuator_pos) if aid in available_ids]
    valid_actuator_ids = [v[0] for v in valid]
    valid_actuator_pos = [v[1] for v in valid]

    missing_actuators = [aid for aid in actuator_ids if aid not in available_ids]

    if missing_actuators:
        log.warning(f"Skipping non-existent actuators: {missing_actuators}")
    if not valid_actuator_ids:
        log.error("No valid actuators to test. Exiting.")
        return

    log.info("configure actuators")
    for actuator_id in valid_actuator_ids:
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=kp,
            kd=kd,
            ki=ki,
            acceleration=acceleration,
            max_torque=max_torque,
            torque_enabled=torque_enabled,
        )

    log.info("move to start position")
    commands = []
    for aid in valid_actuator_ids:
        commands.append({"actuator_id": aid, "position": start_pos})
    await kos.actuator.command_actuators(commands)
    await asyncio.sleep(2.0)

    t = np.arange(0, duration, 1 / sample_rate)

    log.info("running")
    start_time = time.time()

    try:
        for current_time in t:
            if interrupted:
                break

            commands = []

            for aid, apos in zip(valid_actuator_ids, valid_actuator_pos):
                commands.append({"actuator_id": aid, "position": apos})

            await kos.actuator.command_actuators(commands)

            next_time = start_time + current_time
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except Exception as e:
        log.error(f"exception during test: {e}")
    finally:
        log.info("return to start position")
        commands = [{"actuator_id": aid, "position": start_pos} for aid in valid_actuator_ids]
        await kos.actuator.command_actuators(commands)
        await asyncio.sleep(1.0)

        await kos.close()
        log.info("test complete")

async def main():
    await overload()

if __name__ == "__main__":
    asyncio.run(main())
