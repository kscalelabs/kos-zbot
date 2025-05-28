import click
from pykos import KOS
import asyncio
import time
from tabulate import tabulate
from kos_zbot.tests.kos_connection import kos_ready_async
async def actuator_move(ids, target, velocity=None, kp=None, kd=None, acceleration=None, wait=3.0):
    kos_ip = "127.0.0.1"
    if await kos_ready_async(kos_ip):
        kos = KOS(kos_ip)
    else:
        print(f"KOS service not available at {kos_ip}:50051")
        return

    if ids.lower() == 'all':
        resp = await kos.actuator.get_actuators_state()
        actuator_ids = [s.actuator_id for s in resp.states]
    else:
        try:
            actuator_ids = [int(i.strip()) for i in ids.split(',')]
        except ValueError:
            click.echo("Error: IDs must be comma-separated integers or 'all'")
            return

    try:
        target_pos = float(target)
    except ValueError:
        click.echo("Error: Target must be a valid number")
        return

    for aid in actuator_ids:
        kwargs = {}
        if kp is not None:
            kwargs['kp'] = kp
        if kd is not None:
            kwargs['kd'] = kd
        if acceleration is not None:
            kwargs['acceleration'] = acceleration
        else:
            kwargs['acceleration'] = 1000
        kwargs['torque_enabled'] = True  # Always enable torque
        if kwargs:
            await kos.actuator.configure_actuator(actuator_id=aid, **kwargs)

    # Create commands with optional velocity
    commands = []
    for aid in actuator_ids:
        cmd = {"actuator_id": aid, "position": target_pos}
        if velocity is not None:
            cmd["velocity"] = velocity
        commands.append(cmd)

    await kos.actuator.command_actuators(commands)

    # Poll actuator state to verify movement    
    tolerance = 0.1             # deg  
    velocity_threshold = 1.0    # deg/s
    poll_interval = 0.1         # seconds
    settle_time = 0.3           # seconds to wait after reaching target
    start_time = time.time()
    settle_start = None
    id_to_state = {}
    timed_out = False

    while time.time() - start_time < wait:
        resp = await kos.actuator.get_actuators_state()
        id_to_state = {s.actuator_id: s for s in resp.states}
        
        all_settled = True
        for aid in actuator_ids:
            state = id_to_state.get(aid)
            if state is None or getattr(state, "position", None) is None:
                all_settled = False
                continue
                
            position_error = abs(getattr(state, "position") - target_pos)
            velocity = abs(getattr(state, "velocity", 0.0) or 0.0)
            if position_error > tolerance or velocity > velocity_threshold:
                all_settled = False
                
        if all_settled:
            if settle_start is None:
                settle_start = time.time()
            elif time.time() - settle_start >= settle_time:
                break
        else:
            settle_start = None
            
        await asyncio.sleep(poll_interval)
    else:
        timed_out = True

    if timed_out:
        click.echo(f"⚠ Warning: Movement timed out after {wait:.1f}s")

    verify_table = []
    for aid in actuator_ids:
        state = id_to_state.get(aid)
        if state is None or getattr(state, "position", None) is None:
            verify_table.append([aid, target_pos, "N/A", "state/position not found!"])
            continue
        actual = getattr(state, "position")
        diff = abs(actual - target_pos)
        verify_table.append([aid, f"{target_pos:.2f}", f"{actual:.2f}", f"{diff:.2f}"])

    click.echo("\n" + tabulate(
        verify_table,
        headers=["Actuator ID", "Target", "Actual", "Diff"],
        tablefmt="simple"
    ))