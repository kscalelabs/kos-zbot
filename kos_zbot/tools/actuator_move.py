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

    # Get actuator IDs
    if ids.lower() == 'all':
        resp = await kos.actuator.get_actuators_state()
        actuator_ids = [s.actuator_id for s in resp.states]
    else:
        try:
            actuator_ids = [int(i.strip()) for i in ids.split(',')]
        except ValueError:
            click.echo("Error: IDs must be comma-separated integers or 'all'")
            return

    # Parse target position
    try:
        target_pos = float(target)
    except ValueError:
        click.echo("Error: Target must be a valid number")
        return

    # Configure actuators if needed
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
    tolerance = 0.5
    poll_interval = 0.2
    start_time = time.time()
    reached = {aid: False for aid in actuator_ids}
    id_to_state = {}

    while time.time() - start_time < wait:
        resp = await kos.actuator.get_actuators_state()
        id_to_state = {s.actuator_id: s for s in resp.states}
        all_reached = True
        for aid in actuator_ids:
            state = id_to_state.get(aid)
            if state is None or getattr(state, "position", None) is None:
                all_reached = False
                continue
            actual = getattr(state, "position")
            diff = abs(actual - target_pos)
            if diff <= tolerance:
                reached[aid] = True
            else:
                all_reached = False
        if all_reached:
            break
        await asyncio.sleep(poll_interval)

    # Prepare verification table
    verify_table = []
    for aid in actuator_ids:
        state = id_to_state.get(aid)
        if state is None or getattr(state, "position", None) is None:
            verify_table.append([aid, target_pos, "N/A", "state/position not found!"])
            continue
        actual = getattr(state, "position")
        diff = abs(actual - target_pos)
        status = "OK" if diff <= tolerance else "NOT REACHED"
        verify_table.append([aid, f"{target_pos:.2f}", f"{actual:.2f}", f"{diff:.2f} ({status})"])

    click.echo("\n" + tabulate(
        verify_table,
        headers=["Actuator ID", "Target", "Actual", "Diff (Status)"],
        tablefmt="simple"
    ))