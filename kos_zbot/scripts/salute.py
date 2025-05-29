import asyncio
import numpy as np
import time

import signal
import logging

from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async

"""
Does a salute script.
Nat Friedman approved.
"""

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Or DEBUG for more verbosity
    return logger


# Freq in 1/s, Amplitude in degrees
async def salute(
    actuator_ids: list[int] = [11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46],
    kos_ip: str = "127.0.0.1",
    # Pattern configuration
    squeeze_duration:int=5, 
    squeeze_freq:float= 1, 
    squeeze_amplitude:float=15,
    squeeze_sample_rate:float=50.0,
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 0.0,
    torque_enabled: bool = True,
):
    
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

    valid_actuator_ids = [aid for aid in actuator_ids if aid in available_ids]
    missing_actuators = [aid for aid in actuator_ids if aid not in available_ids]
    if missing_actuators:
        log.warning(f"Skipping non-existent actuators: {missing_actuators}")
    if not valid_actuator_ids:
        log.error("No valid actuators to test. Exiting")
        return
    
    interrupted = False
    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True    
        log.info("sigint received")
    
    # Save the original signal handler
    original_handler = signal.signal(signal.SIGINT, handle_sigint)

    # Assume position
    log.info("zeroing actuators")

    zero_commands = []
    for aid in available_ids:
        zero_commands.append({"actuator_id": aid, "position": 0}) 
    
    await kos.actuator.command_actuators(zero_commands)

    await asyncio.sleep(0.5)
    
    await kos.actuator.command_actuators([
        {"actuator_id": 21, "position": -150},
        {"actuator_id": 22, "position": -20},
        {"actuator_id": 23, "position": -60}
    ])

   # Hand squeezing   
    t = np.arange(0, squeeze_duration, 1 / squeeze_sample_rate)

    start_time = time.time()

    try:
        for current_time in t:
            if interrupted:
                break
            
            angle = 2 * np.pi * squeeze_freq * current_time
            position = squeeze_amplitude * np.sin(angle)
            
            command = [{"actuator_id": 24, "position": position}]
            await kos.actuator.command_actuators(command)
        
            next_time = start_time + current_time
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
    except KeyboardInterrupt:
        pass
    finally:
        log.info("salute concluded, return to start position")
        await kos.actuator.command_actuators(zero_commands)
        
        # Always restore the original signal handler
        signal.signal(signal.SIGINT, original_handler)
        
        await kos.close()
        log.info("test complete")

    


if __name__ == "__main__":
    asyncio.run(salute())