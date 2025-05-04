import click
from pykos import KOS
import asyncio
import time
from tabulate import tabulate

async def actuator_move(ids, positions, kp=None, kd=None, acceleration=None, wait=3.0):
    kos = KOS("127.0.0.1")
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

    # Parse positions
    if len(positions) == 1:
        pos_list = [positions[0]] * len(actuator_ids)
    elif len(positions) == len(actuator_ids):
        pos_list = positions
    else:
        click.echo("Error: Number of positions must be 1 or match number of actuator IDs")
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
        kwargs['torque_enabled'] = True  # Always enable torque
        if kwargs:
            await kos.actuator.configure_actuator(actuator_id=aid, **kwargs)

    await kos.actuator.command_actuators([
        {"actuator_id": aid, "position": pos} for aid, pos in zip(actuator_ids, pos_list)
    ])

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
        for aid, target in zip(actuator_ids, pos_list):
            state = id_to_state.get(aid)
            if state is None or getattr(state, "position", None) is None:
                all_reached = False
                continue
            actual = getattr(state, "position")
            diff = abs(actual - target)
            if diff <= tolerance:
                reached[aid] = True
            else:
                all_reached = False
        if all_reached:
            break
        await asyncio.sleep(poll_interval)

    # Prepare verification table
    verify_table = []
    for aid, target in zip(actuator_ids, pos_list):
        state = id_to_state.get(aid)
        if state is None or getattr(state, "position", None) is None:
            verify_table.append([aid, target, "N/A", "state/position not found!"])
            continue
        actual = getattr(state, "position")
        diff = abs(actual - target)
        status = "OK" if diff <= tolerance else "NOT REACHED"
        verify_table.append([aid, f"{target:.2f}", f"{actual:.2f}", f"{diff:.2f} ({status})"])

    click.echo("\n" + tabulate(
        verify_table,
        headers=["Actuator ID", "Target", "Actual", "Diff (Status)"],
        tablefmt="simple"
    ))