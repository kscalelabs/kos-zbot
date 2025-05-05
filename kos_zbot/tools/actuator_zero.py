import click
import asyncio
from pykos import KOS
from tabulate import tabulate
from kos_zbot.tests.kos_connection import kos_ready_async

async def actuator_zero(ids):
    kos_ip = "127.0.0.1"
    if await kos_ready_async(kos_ip):
        kos = KOS(kos_ip)
    else:
        print(f"KOS service not available at {kos_ip}:50051")
        return

    click.echo(f"Zeroing actuators: {ids}")
    if ids.lower() == 'all':
        resp = await kos.actuator.get_actuators_state()
        actuator_ids = [s.actuator_id for s in resp.states]
    else:
        try:
            actuator_ids = [int(i.strip()) for i in ids.split(',')]
        except ValueError:
            click.echo("Error: IDs must be comma-separated integers or 'all'")
            return
    orig = await kos.actuator.get_actuators_state(actuator_ids)
    orig_pos = {s.actuator_id: s.position for s in orig.states}
    for aid in actuator_ids:
        await kos.actuator.configure_actuator(actuator_id=aid, zero_position=True)
        await asyncio.sleep(0.2)
    await asyncio.sleep(3)
    new = await kos.actuator.get_actuators_state(actuator_ids)
    new_pos = {s.actuator_id: s.position for s in new.states}
    headers = ["ID", "Original (°)", "New (°)"]
    rows = [
        [aid, f"{orig_pos.get(aid, 'N/A'):.2f}", f"{new_pos.get(aid, 'N/A'):.2f}"]
        for aid in actuator_ids
    ]
    click.echo(tabulate(rows, headers=headers, tablefmt="simple"))