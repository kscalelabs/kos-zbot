import click
import asyncio
from tabulate import tabulate
from pykos import KOS
from kos_zbot.tools.status_display import show_status
from kos_zbot.tools.actuator_dump import actuator_dump
from kos_zbot.tools.actuator_move import actuator_move
from kos_zbot.tools.actuator_torque import actuator_torque
from kos_zbot.tools.actuator_zero import actuator_zero
from google.protobuf.json_format import MessageToDict


class MainGroup(click.Group):
    def list_commands(self, ctx):
        return ['service', 'status', 'actuator', 'test']


class ActuatorGroup(click.Group):
    def list_commands(self, ctx):
        return ['move', 'torque', 'zero', 'dump']


@click.group(
    cls=MainGroup,
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={'help_option_names': ['-h', '--help']},
    help=(
        "KOS ZBot Command Line Interface.\n\n"
        "IMPORTANT: You must run 'kos service' before using any other commands."
    )
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
@click.argument('ids', required=True)
@click.argument('positions', nargs=-1, type=float, required=True)
@click.option('--kp', type=float, default=None, help="Position gain (optional)")
@click.option('--kd', type=float, default=None, help="Velocity gain (optional)")
@click.option('--acceleration', type=float, default=None, help="Acceleration (optional)")
@click.option('--wait', type=float, default=3.0, show_default=True, help="Seconds to wait for actuators to reach target")
def move(ids, positions, kp, kd, acceleration, wait):
    from kos_zbot.tools.actuator_move import actuator_move
    asyncio.run(actuator_move(ids, positions, kp, kd, acceleration, wait))


@actuator.command()
@click.argument('action', type=click.Choice(['enable', 'disable']))
@click.argument('ids', required=True)
def torque(action, ids):
    """Enable or disable torque for given actuator IDs."""
    from kos_zbot.tools.actuator_torque import actuator_torque
    asyncio.run(actuator_torque(action, ids))


@actuator.command()
@click.argument('ids', required=True)
def zero(ids):
    """Zero the given actuator IDs (comma-separated or 'all')."""
    from kos_zbot.tools.actuator_zero import actuator_zero
    asyncio.run(actuator_zero(ids))


@actuator.command()
@click.argument('ids', required=True)
@click.option('--diff', is_flag=True, help="Only show parameters that differ.")
def dump(ids, diff):
    """Dump parameters from actuator IDs."""
    from kos_zbot.tools.actuator_dump import actuator_dump
    asyncio.run(actuator_dump(ids, diff))


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
        "kos_ip": "127.0.0.1",
        "amplitude": 10.0,
        "frequency": 0.5,
        "duration": 3600.0,
        "sample_rate": 50.0,
        "start_pos": 0.0,
        "sync_all": False,
        "wave_patterns": {
            "pair_1": {"actuators": [11,12,13,14], "amplitude": 10.0, "frequency": 0.25, "phase_offset": 0.0, "freq_multiplier": 1.0, "start_pos": 0.0, "position_offset": 0.0},
            "pair_2": {"actuators": [21,22,23,24], "amplitude": 10.0, "frequency": 0.25, "phase_offset": 90.0, "freq_multiplier": 1.0, "start_pos": 0.0, "position_offset": 0.0},
            "group_3": {"actuators": [31,32,33,34,35,36], "amplitude": 10.0, "frequency": 0.25, "phase_offset": 0.0, "freq_multiplier": 1.0, "start_pos": 0.0, "position_offset": 0.0},
            "group_4": {"actuators": [41,42,43,44,45,46], "amplitude": 10.0, "frequency": 0.25, "phase_offset": 0.0, "freq_multiplier": 1.0, "start_pos": 0.0, "position_offset": 0.0},
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