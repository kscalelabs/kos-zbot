import click
import asyncio
from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async

async def actuator_torque(action, ids):
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
    enable = (action == 'enable')
    for aid in actuator_ids:
        await kos.actuator.configure_actuator(actuator_id=aid, torque_enabled=enable)
    click.echo(f"Torque {'enabled' if enable else 'disabled'} for: {actuator_ids}")