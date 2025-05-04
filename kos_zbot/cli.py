import click
import asyncio
from tabulate import tabulate
from pykos import KOS
from kos_zbot.tools.status_display import show_status
from google.protobuf.json_format import MessageToDict


class MainGroup(click.Group):
    def list_commands(self, ctx):
        return ['service', 'status', 'actuator', 'test']


class ActuatorGroup(click.Group):
    def list_commands(self, ctx):
        return ['move', 'scan', 'torque', 'zero', 'dump']


@click.group(
    cls=MainGroup,
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={'help_option_names': ['-h', '--help']},
    help="KOS ZBot Command Line Interface."
)
def cli():
    """Main entry point for the KOS ZBot CLI."""
    pass


@cli.command()
def service():
    """Start the KOS service."""
    from kos_zbot.kos import main as service_main
    service_main()


@cli.command()
@click.option(
    "--scale", type=float, default=50.0, show_default=True, metavar="DEG",
    help="Max |position| in degrees for bar scaling."
)
def status(scale):
    """Show live system status"""
    asyncio.run(show_status(scale=scale))


@cli.group(
    'actuator',
    cls=ActuatorGroup,
    help="Actuator-specific operations."
)
def actuator():
    """Commands for querying and configuring actuators."""
    pass


cli.add_command(actuator)


@actuator.command()
@click.argument('ids', nargs=-1, type=int)
@click.argument('positions', nargs=-1, type=float)
def move(ids, positions):
    """Move actuators to specified positions."""
    click.echo(f"Moving IDs {ids} to positions {positions}")


@actuator.command()
def scan():
    """Scan for available actuators."""
    click.echo("Scanning for actuators...")


@actuator.command()
@click.argument('action', type=click.Choice(['enable', 'disable']))
@click.argument('ids', required=True)
def torque(action, ids):
    """Enable or disable torque for given actuator IDs."""
    async def _torque():
        kos = KOS("127.0.0.1")
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
    asyncio.run(_torque())


@actuator.command()
@click.argument('ids', required=True)
def zero(ids):
    """Zero the given actuator IDs (comma-separated or 'all')."""
    async def _zero():
        kos = KOS("127.0.0.1")
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
    asyncio.run(_zero())


@actuator.command()
@click.argument('ids', required=True)
@click.option('--diff', is_flag=True, help="Only show parameters that differ.")
def dump(ids, diff):
    """Dump parameters from actuator IDs."""
    async def _dump():
        kos = KOS("127.0.0.1")
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
    asyncio.run(_dump())


@cli.group(cls=click.Group, help="Run built-in tests.")
def test():
    """Test commands."""
    pass


@test.command()
def sync_wave():
    """Run the sync_wave test."""
    import asyncio
    from kos_zbot.tests.sync_wave import run_sine_test
    ACTUATOR_IDS = [11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46]
    TEST_CONFIG = {
        "kos_ip": "192.168.42.1",
        "amplitude": 10.0,
        "frequency": 0.5,
        "duration": 3600.0,
        "sample_rate": 50.0,
        "start_pos": 0.0,
        "sync_all": False,
        "wave_patterns": {
            "pair_1": {"actuators": [11,12,13,14], "amplitude": 15.0, "frequency": 0.5, "phase_offset": 0.0, "freq_multiplier": 1.0, "start_pos": 0.0, "position_offset": 10.0},
            "pair_2": {"actuators": [21,22,23,24], "amplitude": 15.0, "frequency": 1.0, "phase_offset": 90.0, "freq_multiplier": 1.0, "start_pos": 10.0, "position_offset": -10.0},
            "group_3": {"actuators": [31,32,33,34,35,36], "amplitude": 10.0, "frequency": 0.5, "phase_offset": 180.0, "freq_multiplier": 2.0, "start_pos": 20.0, "position_offset": 15.0},
            "group_4": {"actuators": [41,42,43,44,45,46], "amplitude": 10.0, "frequency": 0.5, "phase_offset": 0.0, "freq_multiplier": 1.0, "start_pos": 30.0, "position_offset": 10.0},
        },
        "kp": 20.0,
        "kd": 10.0,
        "ki": 0.0,
        "max_torque": 100.0,
        "acceleration": 1000.0,
        "torque_enabled": True,
    }
    asyncio.run(run_sine_test(ACTUATOR_IDS, **TEST_CONFIG))


@test.command()
def sync_step():
    """Run the sync_step test."""
    import asyncio
    from kos_zbot.tests.sync_step import run_step_test
    ACTUATOR_IDS = [11,12,13,14,21,22,23,24,31,32,33,34,35,36,41,42,43,44,45,46]
    TEST_CONFIG = {
        "kos_ip": "127.0.0.1",
        "step_size": 4.0,
        "step_hold_time": 0.02,
        "step_count": 100000,
        "start_pos": 0.0,
        "kp": 20.0,
        "kd": 10.0,
        "ki": 0.0,
        "max_torque": 100.0,
        "acceleration": 1000.0,
        "torque_enabled": True,
        "step_min": 1.0,
        "step_max": 10.0,
        "max_total": 30.0,
        "seed": 42
    }
    asyncio.run(run_step_test(ACTUATOR_IDS, **TEST_CONFIG))


@test.command()
def imu():
    """Run the IMU test."""
    click.echo("Running IMU test...")


if __name__ == '__main__':
    cli()