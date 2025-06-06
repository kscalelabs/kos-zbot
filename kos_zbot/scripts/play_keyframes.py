import asyncio
import logging
import json
import sys

from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async

kos_ip = "127.0.0.1"

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Or DEBUG for more verbosity
    return logger

async def play_keyframes(json_file):
    vel = 90
    threshold = 15
    kp = 11
    kd = 10
    accel = 100

    log = get_logger(__name__)

    if await kos_ready_async(kos_ip):
        kos = KOS(kos_ip)
    else:
        log.error("KOS service not available at %s:50051", kos_ip)
        return
    
    try:
        state_resp = await kos.actuator.get_actuators_state()
        available_ids = [s.actuator_id for s in state_resp.states]
    except Exception as e:
        log.error(f"No actuators available: {e}")

    with open(json_file, 'r') as f:
        data = json.load(f)

    for a_id in available_ids:
        await kos.actuator.configure_actuator(
                actuator_id = a_id,
                kp = kp,
                kd = kd,
                acceleration = accel,
                torque_enabled = True
        )


    frames = data['keyframes'].values()

    for name, frame in data['keyframes'].items():
        if name == "wait":
            await asyncio.sleep(frame)

        frame = {int(k): v for k, v in frame.items()}
        commands = [{"actuator_id": a_id,
                     "position": a_pos,
                     "velocity": vel} for a_id,
                a_pos in frame.items()]
        await kos.actuator.command_actuators(commands)

        there = False
        while not there:
            states = await kos.actuator.get_actuators_state([a_id for a_id
                in frame.keys()])
            there = all(abs(state.position - frame[state.actuator_id]) < threshold for
                    state in states.states)

json_file = sys.argv[1]

asyncio.run(play_keyframes(json_file))
