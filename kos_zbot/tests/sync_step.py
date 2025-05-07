import asyncio
import time
import random
from pykos import KOS
import logging
import signal
from kos_zbot.tests.kos_connection import kos_ready_async

def get_logger(name):
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Or DEBUG for more verbosity
    return logger

async def run_step_test(
    actuator_ids: list[int],
    kos_ip: str = "127.0.0.1",
    # Basic step parameters
    step_size: float = 10.0,        # degrees
    step_hold_time: float = 0.02,    # seconds
    step_count: int = 5000,
    start_pos: float = 0.0,         # degrees
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 1000.0,
    torque_enabled: bool = True,
    # Random step parameters
    random_mode: bool = False,
    step_min: float = 1.0,         # degrees
    step_max: float = 5.0,        # degrees
    max_total: float = 30.0,       # degrees
    seed: int = None
):
    """Run a step response test on specified actuators.
    
    Args:
        actuator_ids: List of actuator IDs to test
        kos_ip: IP address of the KOS device
        step_size: Size of each step in degrees (used if random_mode=False)
        step_hold_time: How long to hold each step position
        step_count: Number of steps to perform
        start_pos: Starting position in degrees
        kp: Position gain
        kd: Velocity gain
        ki: Integral gain
        max_torque: Maximum torque limit
        acceleration: Acceleration limit (0 = unlimited)
        step_min: Minimum random step size in degrees
        step_max: Maximum random step size in degrees
        max_total: Maximum total deviation from start position
        seed: Random seed for reproducibility
    """
    log = get_logger(__name__)

    interrupted = False
    def handle_sigint(signum, frame):
        nonlocal interrupted
        interrupted = True
        log.info("sigint received")

    signal.signal(signal.SIGINT, handle_sigint)
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

    valid_actuator_ids = [aid for aid in actuator_ids if aid in available_ids]
    missing_actuators = [aid for aid in actuator_ids if aid not in available_ids]
    if missing_actuators:
        log.warning(f"Skipping non-existent actuators: {missing_actuators}")
    if not valid_actuator_ids:
        log.error("No valid actuators to test. Exiting.")
        return

    if seed is not None:
        random.seed(seed)

  
    
    # Configure each actuator
    log.info("configure actuators")
    for actuator_id in valid_actuator_ids:
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=kp,
            kd=kd,
            ki=ki,
            acceleration=acceleration,
            max_torque=max_torque,
            torque_enabled=torque_enabled
        )
    
    # Move to start position
    log.info(f"move to start position {start_pos}°")
    commands = [
        {
            'actuator_id': actuator_id,
            'position': start_pos,
        }
        for actuator_id in valid_actuator_ids
    ]
    await kos.actuator.command_actuators(commands)
    
    # Wait for settling
    await asyncio.sleep(1.0)
    
    log.info(f"compute sequence with seed {seed}")
    steps = []
    current_pos = start_pos
    
    for step_num in range(step_count):
        if interrupted:
            break
        # Generate random step size (magnitude only)
        step_size = random.uniform(step_min, step_max)
        
        # Determine valid directions based on bounds
        valid_directions = []
        
        # Check if we can move positive
        if (current_pos + step_size) <= (start_pos + max_total):
            valid_directions.append(1)
        
        # Check if we can move negative
        if (current_pos - step_size) >= (start_pos - max_total):
            valid_directions.append(-1)
        
        # If no valid directions (shouldn't happen with proper bounds), stay put
        if not valid_directions:
            direction = 0
        else:
            direction = random.choice(valid_directions)
        
        # Calculate next position
        target_pos = current_pos + (step_size * direction)
        steps.append(target_pos)
        current_pos = target_pos

    
    log.info("running")
    for i, target_pos in enumerate(steps, 1):
        if interrupted:
            break

        commands = [
            {
                'actuator_id': actuator_id,
                'position': target_pos,
            }
            for actuator_id in valid_actuator_ids
        ]
        await kos.actuator.command_actuators(commands)
        await asyncio.sleep(step_hold_time)
     
    log.info("return to start position")
    commands = [
        {'actuator_id': aid, 'position': start_pos}
        for aid in valid_actuator_ids
    ]
    await kos.actuator.command_actuators(commands)
    await asyncio.sleep(1.0)
    await kos.close()
    log.info("Test complete")