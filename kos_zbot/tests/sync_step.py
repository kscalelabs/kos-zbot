import asyncio
import time
import random
from pykos import KOS

async def run_step_test(
    actuator_ids: list[int],
    kos_ip: str = "127.0.0.1",
    # Basic step parameters
    step_size: float = 10.0,        # degrees
    step_hold_time: float = 2.0,    # seconds
    step_count: int = 3,
    start_pos: float = 0.0,         # degrees
    # Motor parameters
    kp: float = 20.0,
    kd: float = 5.0,
    ki: float = 0.0,
    max_torque: float = 100.0,
    acceleration: float = 0.0,
    torque_enabled: bool = True,
    # Random step parameters
    random_mode: bool = False,
    step_min: float = 5.0,         # degrees
    step_max: float = 15.0,        # degrees
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
        random_mode: If True, use random step sizes
        step_min: Minimum random step size in degrees
        step_max: Maximum random step size in degrees
        max_total: Maximum total deviation from start position
        seed: Random seed for reproducibility
    """
    # Set random seed if provided
    if seed is not None:
        random.seed(seed)
        print(f"Using random seed: {seed}")

    # Connect to KOS
    kos = KOS(kos_ip)
    
    # Configure each actuator
    print("\nConfiguring actuators...")
    for actuator_id in actuator_ids:
        await kos.actuator.configure_actuator(
            actuator_id=actuator_id,
            kp=kp,
            kd=kd,
            ki=ki,
            acceleration=acceleration,
            max_torque=max_torque,
            torque_enabled=torque_enabled
        )
        print(f"Actuator {actuator_id} configured with torque_enabled={torque_enabled}")
    
    # Move to start position
    print(f"\nMoving to start position: {start_pos}°")
    for actuator_id in actuator_ids:
        await kos.actuator.command_actuators([{
            'actuator_id': actuator_id,
            'position': start_pos,
        }])
    
    # Wait for settling
    await asyncio.sleep(2.0)
    
    if random_mode:
        print("\nGenerating random step sequence:")
        steps = []
        current_pos = start_pos
        
        for step_num in range(step_count):
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
            
            #print(f"Step {step_num + 1}: to {target_pos:.2f}° (delta={step_size * direction:.2f}°, total offset={target_pos - start_pos:.2f}°)")
        
        print("\nExecuting step sequence...")
        for i, target_pos in enumerate(steps, 1):
            for actuator_id in actuator_ids:
                await kos.actuator.command_actuators([{
                    'actuator_id': actuator_id,
                    'position': target_pos,
                }])
            await asyncio.sleep(step_hold_time)
    
    else:
        # Run fixed step sequence
        print("\nStarting fixed step test...")
        for step in range(step_count):
            # Step up
            target_pos = start_pos + step_size
            print(f"\nStep {step + 1}/{step_count} UP to {target_pos}°")
            for actuator_id in actuator_ids:
                await kos.actuator.command_actuators([{
                    'actuator_id': actuator_id,
                    'position': target_pos,
                }])
            await asyncio.sleep(step_hold_time)
            
            # Step down
            print(f"Step {step + 1}/{step_count} DOWN to {start_pos}°")
            for actuator_id in actuator_ids:
                await kos.actuator.command_actuators([{
                    'actuator_id': actuator_id,
                    'position': start_pos,
                }])
            await asyncio.sleep(step_hold_time)
    
    await kos.close()
    print("\nTest complete!")


if __name__ == "__main__":
    ACTUATOR_IDS = [11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46]
    
    # Test parameters
    TEST_CONFIG = {
        # Connection settings
        "kos_ip": "127.0.0.1",  # Replace with your KOS IP
        
        # Basic step parameters
        "step_size": 4.0,         # degrees
        "step_hold_time": 0.01,     # seconds
        "step_count": 300,
        "start_pos": 0.0,          # degrees
        
        # Motor parameters
        "kp": 20.0,
        "kd": 10.0,
        "ki": 0.0,
        "max_torque": 100.0,
        "acceleration": 1000.0,
        "torque_enabled": True,
        
        # Random step parameters
        "random_mode": True,        # Set to True to use random steps
        "step_min": 1.0,            # degrees
        "step_max": 5.0,           # degrees
        "max_total": 30.0,          # +- max position from start position
        "seed": 43                  # Random seed (None for true random)
    }
    
    asyncio.run(run_step_test(ACTUATOR_IDS, **TEST_CONFIG))