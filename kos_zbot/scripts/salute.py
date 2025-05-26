import asyncio
import numpy as np
import time

import signal

from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async
from kos_zbot.tools.actuator_move import actuator_move as move
from kos_zbot.tests.sync_wave import get_logger

"""
Does a salute script.
!!! Currently assumes the robot is in "spread out" position for sync wave. Arms ~ 20 degrees abducted.
Nat Friedman approved.
"""


# Freq in 1/s, Amplitude in degrees
async def salute(kos_ip = "127.0.0.1",
    squeeze_duration:int=5, 
    squeeze_freq:float= 1, 
    squeeze_amplitude:float=15,
    sample_rate:float=50.0,
):
    COMMAND_ACTUATOR_IDS=(21,23,24)
    ALL = (11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46)

    zero_commands = []
    for aid in ALL:
        zero_commands.append({"actuator_id": aid, "position": 0})

    # Startup, copied from sync_wave.py
    if await kos_ready_async(kos_ip):
        kos = KOS(kos_ip)
    else:
        return
    
    interrupted = False
    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True    
    signal.signal(signal.SIGINT, handle_sigint)

    try:
        state_resp = await kos.actuator.get_actuators_state()
        available_ids = {s.actuator_id for s in state_resp.states}
    except Exception as e:
        return
    
    # Assume position

    await kos.actuator.command_actuators(zero_commands)

    await asyncio.sleep(0.5)
    
    await kos.actuator.command_actuators([
        {"actuator_id": 21, "position": -150},
        {"actuator_id": 23, "position": -60}
    ])

   # Hand squeezing   
    t = np.arange(0, squeeze_duration, 1 / sample_rate)

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

    # Conclude
    await kos.actuator.command_actuators(zero_commands)


if __name__ == "__main__":
    asyncio.run(salute())