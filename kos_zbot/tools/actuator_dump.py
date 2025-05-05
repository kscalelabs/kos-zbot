import click
import asyncio
from pykos import KOS
from tabulate import tabulate
from google.protobuf.json_format import MessageToDict
from kos_zbot.tests.kos_connection import kos_ready_async

async def actuator_dump(ids, diff):
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
    resp = await kos.actuator.parameter_dump(actuator_ids)
    param_map = {
        entry.actuator_id: MessageToDict(entry.parameters, preserving_proto_field_name=True)
        for entry in resp.entries
    }
    if not param_map:
        click.echo("No parameters found.")
        return
    first = next(iter(param_map))
    names = sorted(
        param_map[first].keys(),
        key=lambda k: int(param_map[first][k]['addr'])
    )
    rows = []
    for name in names:
        vals = [
            str(param_map.get(aid, {}).get(name, {}).get('value', 'N/A'))
            for aid in actuator_ids
        ]
        if diff and len(set(vals)) == 1:
            continue
        rows.append([name] + vals)
    if not rows:
        click.echo("No differing parameters found." if diff else "No parameters found.")
        return
    headers = ["Parameter"] + [str(a) for a in actuator_ids]
    click.echo(tabulate(rows, headers=headers, tablefmt="simple"))
    if not diff:
        click.secho(
            "\nTip: Use '--diff' to only show parameters that differ between actuators.",
            fg="yellow"
        )