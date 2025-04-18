import asyncio
import time
import numpy as np
from pykos import KOS

async def run_sine_test(
    actuator_ids: list[int],
    kos_ip: str = "127.0.0.1",
    # Sine wave parameters
    amplitude: float = 10.0,        # degrees
    frequency: float = 1.0,         # Hz
    duration: float = 10.0,         # seconds
    sample_rate: float = 50.0,      # Hz
    start_pos: float = 0.0,         # degrees
    # Pattern configuration
    sync_all: bool = True,          # If True, all actuators move in sync
    wave_patterns: dict = None,     # Dict of pattern configurations
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
        ... (previous args remain the same) ...
        wave_patterns: Dictionary of pattern configurations in the format:
            {
                'pattern_name': {
                    'actuators': [list of actuator IDs],
                    'amplitude': float (optional, overrides global),
                    'frequency': float (optional, overrides global),
                    'phase_offset': float (degrees),
                    'freq_multiplier': float,
                    'start_pos': float (optional, overrides global),
                    'position_offset': float (optional, shifts wave center)
                }
            }
    """
   # Initialize default pattern if none provided
    if wave_patterns is None:
        wave_patterns = {
            'default': {
                'actuators': actuator_ids,
                'amplitude': amplitude,
                'frequency': frequency,
                'phase_offset': 0.0,
                'freq_multiplier': 1.0,
                'start_pos': start_pos,
                'position_offset': 0.0
            }
        }

    # Connect to KOS
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
    
    # Move to start positions (now per pattern)
    print("\nMoving to start positions...")
    commands = []
    for pattern in wave_patterns.values():
        pattern_start_pos = pattern.get('start_pos', start_pos)
        for aid in pattern['actuators']:
            commands.append({
                'actuator_id': aid,
                'position': pattern_start_pos
            })
    await kos.actuator.command_actuators(commands)
    await asyncio.sleep(2.0)

    # Generate time points
    t = np.arange(0, duration, 1/sample_rate)
    
    print("\nStarting sine wave patterns...")
    start_time = time.time()
    
    try:
        for current_time in t:
            commands = []
            
            if sync_all:
                # All actuators follow base parameters
                for aid in actuator_ids:
                    angle = 2 * np.pi * frequency * current_time
                    position = start_pos + amplitude * np.sin(angle)
                    commands.append({
                        'actuator_id': aid,
                        'position': position
                    })
            else:
                # Apply specific pattern parameters
                for pattern_name, pattern in wave_patterns.items():
                    pattern_amp = pattern.get('amplitude', amplitude)
                    pattern_freq = pattern.get('frequency', frequency)
                    pattern_phase = pattern.get('phase_offset', 0.0)
                    pattern_freq_mult = pattern.get('freq_multiplier', 1.0)
                    pattern_start = pattern.get('start_pos', start_pos)
                    pattern_pos_offset = pattern.get('position_offset', 0.0)
                    
                    for aid in pattern['actuators']:
                        angle = (2 * np.pi * pattern_freq * pattern_freq_mult * current_time + 
                               np.deg2rad(pattern_phase))
                        position = (pattern_start + 
                                  pattern_amp * np.sin(angle) + 
                                  pattern_pos_offset)  # Add position offset
                        commands.append({
                            'actuator_id': aid,
                            'position': position
                        })
            
            await kos.actuator.command_actuators(commands)
            
            # Maintain timing
            next_time = start_time + current_time
            sleep_time = next_time - time.time()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
    
    except KeyboardInterrupt:
        print("\nTest interrupted!")
    
    # Return to start position
    print("\nReturning to start position...")
    commands = [
        {'actuator_id': aid, 'position': start_pos}
        for aid in actuator_ids
    ]
    await kos.actuator.command_actuators(commands)
    await asyncio.sleep(1.0)
    
    await kos.close()
    print("\nTest complete!")

if __name__ == "__main__":
    ACTUATOR_IDS = [11, 12, 13, 14, 21, 22, 23, 24,31,32,33,34,35,36,41,42,43,44,45,46]
    
    # Example configuration showing different pattern possibilities
    TEST_CONFIG = {
        # ... existing connection and global parameters ...
        
        # Pattern configuration
        "sync_all": False,
        "wave_patterns": {
            # Example: First two actuators in sync, offset upward
            "pair_1": {
                "actuators": [11, 12,13,14],
                "amplitude": 15.0,
                "frequency": 0.5,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 0.0,
                "position_offset": 10.0  # Shifts wave up by 10 degrees
            },
            # Example: Second pair with phase offset, offset downward
            "pair_2": {
                "actuators": [21, 22,23,24],
                "amplitude": 15.0,
                "frequency": 0.5,
                "phase_offset": 90.0,
                "freq_multiplier": 1.0,
                "start_pos": 10.0,
                "position_offset": -10.0  # Shifts wave down by 10 degrees
            },
            # Example: Third group with different frequency and diagonal offset
            "group_3": {
                "actuators": [31, 32, 33, 34, 35, 36],
                "amplitude": 10.0,
                "frequency": 0.5,
                "phase_offset": 180.0,
                "freq_multiplier": 2.0,
                "start_pos": 20.0,
                "position_offset": 15.0  # Shifts wave up by 15 degrees
            },
            "group_4": {
                "actuators": [41, 42, 43, 44, 45, 46],
                "amplitude": 10.0,
                "frequency": 0.5,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 30.0,
                "position_offset": 10.0  # Shifts wave up by 10 degrees
            }
        },
        
        # Motor parameters
        "kp": 20.0,
        "kd": 10.0,
        "ki": 0.0,
        "max_torque": 100.0,
        "acceleration": 1000.0,
        "torque_enabled": True,
    }
    
    asyncio.run(run_sine_test(ACTUATOR_IDS, **TEST_CONFIG))