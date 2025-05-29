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


async def run_sine_test(
    actuator_ids: list[int],
    kos_ip: str = "127.0.0.1",
    # Sine wave parameters
    amplitude: float = 10.0,  # degrees
    frequency: float = 1.0,  # Hz
    duration: float = 20.0,  # seconds
    sample_rate: float = 50.0,  # Hz
    start_pos: float = 0.0,  # degrees
    # Pattern configuration
    sync_all: bool = True,  # If True, all actuators move in sync
    wave_patterns: dict = None,  # Dict of pattern configurations
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 0.0,
    torque_enabled: bool = True,
):
    """Run a sine wave test on specified actuators.

    Args:
        actuator_ids: List of actuator IDs to test
        kos_ip: IP address of the KOS device
        amplitude: Amplitude of the sine wave in degrees
        frequency: Frequency of the sine wave in Hz
        duration: Duration of the test in seconds
        sample_rate: Sample rate of the test in Hz
        start_pos: Starting position of the test in degrees
        sync_all: If True, all actuators move in sync
        wave_patterns: Dict of pattern configurations
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

    try:
        state_resp = await kos.actuator.get_actuators_state()
        available_ids = {s.actuator_id for s in state_resp.states}
    except Exception as e:
        log.error(f"No actuators available: {e}")
        return

    interrupted = False

    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        log.info("sigint received")

    original_handler = signal.signal(signal.SIGINT, handle_sigint)

    valid_actuator_ids = [aid for aid in actuator_ids if aid in available_ids]
    missing_actuators = [aid for aid in actuator_ids if aid not in available_ids]
    if missing_actuators:
        log.warning(f"Skipping non-existent actuators: {missing_actuators}")
    if not valid_actuator_ids:
        log.error("No valid actuators to test. Exiting.")
        return


    t = np.arange(0, duration, 1 / sample_rate)

    log.info("running")
    start_time = time.time()

    try:
        for current_time in t:
            if interrupted:
                break

            commands = []

            if sync_all:
                for aid in valid_actuator_ids:
                    angle = 2 * np.pi * frequency * current_time
                    position = start_pos + amplitude * np.sin(angle)
                    commands.append({"actuator_id": aid, "position": position})
            else:
                for pattern_name, pattern in wave_patterns.items():
                    pattern_amp = pattern.get("amplitude", amplitude)
                    pattern_freq = pattern.get("frequency", frequency)
                    pattern_phase = pattern.get("phase_offset", 0.0)
                    pattern_freq_mult = pattern.get("freq_multiplier", 1.0)
                    pattern_start = pattern.get("start_pos", start_pos)
                    pattern_pos_offset = pattern.get("position_offset", 0.0)

                    for aid in pattern["actuators"]:
                        if aid in valid_actuator_ids:
                            angle = (
                                2 * np.pi * pattern_freq * pattern_freq_mult * current_time
                                + np.deg2rad(pattern_phase)
                            )
                            position = (
                                pattern_start
                                + pattern_amp * np.sin(angle)
                                + pattern_pos_offset
                            )
                            commands.append({"actuator_id": aid, "position": position})

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

        # Always restore the original signal handler
        signal.signal(signal.SIGINT, original_handler)

        await kos.close()
        log.info("test complete")
