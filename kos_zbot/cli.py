import click
import asyncio
from tabulate import tabulate
from pykos import KOS
from kos_zbot.utils.metadata import RobotMetadata
from kos_zbot.tools.status_display import show_status
from kos_zbot.tools.actuator_dump import actuator_dump
from kos_zbot.tools.actuator_move import actuator_move
from kos_zbot.tools.actuator_torque import actuator_torque
from kos_zbot.tools.actuator_zero import actuator_zero
from kos_zbot.tools.policy_run import policy_start, policy_stop, get_policy_state
from google.protobuf.json_format import MessageToDict



class PolicyGroup(click.Group):
    def list_commands(self, ctx):
        return ["start", "stop", "status"]


class ActuatorGroup(click.Group):
    def list_commands(self, ctx):
        return ["move", "torque", "zero", "dump"]

class MainGroup(click.Group):
    def format_help(self, ctx, formatter):
        # Customize the help output
        formatter.write("KOS Command Line Interface\n\n")
        formatter.write("Usage:\n")
        formatter.write("  kos <robot_name> service    Start service for a robot\n")
        formatter.write("  kos <robot_name> inference  Run inference for a robot\n\n")
        formatter.write("Built-in commands:\n")
        formatter.write("  kos policy                  Policy operations\n")
        formatter.write("  kos status                  Show system status\n")
        formatter.write("  kos actuator                Actuator operations\n")
        formatter.write("  kos test                    Run tests\n")
        
        # Add options section
        formatter.write("\nOptions:\n")
        formatter.write("  -h, --help                  Show this message and exit.\n")
    
    def get_help_option(self, ctx):
        # This is needed to prevent Click from showing default help
        # Return the help option object
        help_options = self.get_help_option_names(ctx)
        if not help_options or not self.add_help_option:
            return
        
        def show_help(ctx, param, value):
            if value and not ctx.resilient_parsing:
                # When help is triggered, use our custom formatter directly
                formatter = ctx.make_formatter()
                self.format_help(ctx, formatter)
                click.echo(formatter.getvalue().rstrip("\n"), color=ctx.color)
                ctx.exit()
        
        return click.Option(
            help_options,
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=show_help,
            help='Show this message and exit.',
        )
    
    def get_command(self, ctx, cmd_name):
        # First, try to get built-in commands
        cmd = super(MainGroup, self).get_command(ctx, cmd_name)
        if cmd is not None:
            return cmd
        
        # If not a built-in command, assume it's a robot name
        # Create a new command group for this robot
        @click.group(cmd_name, help=f"Commands for robot name: '{cmd_name}'")
        def robot_group():
            """Robot-specific commands."""
            # Load robot metadata
            metadata_manager = RobotMetadata.get_instance()
            metadata_manager.load_model_metadata(cmd_name)
        
        @robot_group.command("service")
        def robot_service():
            """Start the KOS service for this robot."""
            from kos_zbot.kos import main as service_main
            service_main()

        @robot_group.command("inference")
        @click.option(
            "--model", type=click.Path(exists=True), help="Path to the policy model file"
        )
        @click.option(
            "--action-scale",
            type=float,
            default=0.1,
            show_default=True,
            help="Scale factor for model outputs (0.0 to 1.0)",
        )
        @click.option(
            "--episode-length",
            type=float,
            default=30.0,
            show_default=True,
            help="Run episode length in seconds",
        )
        @click.option(
            "--device",
            type=str,
            default="/dev/ttyAMA5",
            show_default=True,
            help="Serial device for actuator controller",
        )
        @click.option(
            "--baudrate",
            type=int,
            default=1000000,
            show_default=True,
            help="Serial baudrate for actuator controller",
        )
        @click.option(
            "--rate", type=int, default=50, show_default=True, help="Control loop rate in Hz"
        )
        def robot_inference(model, action_scale, episode_length, device, baudrate, rate):
            """Run a dedicated inference loop for this robot."""
            from kos_zbot.inference import run_policy_loop
            asyncio.run(
                run_policy_loop(
                    model_file=model,
                    action_scale=action_scale,
                    episode_length=episode_length,
                    device=device,
                    baudrate=baudrate,
                    rate=rate,
                )
            )
        
        # Use the same custom help approach for robot group
        def show_robot_help(ctx, param, value):
            if value and not ctx.resilient_parsing:
                formatter = ctx.make_formatter()
                formatter.write(f"Robot: {cmd_name}\n\n")
                formatter.write("Commands:\n")
                formatter.write("  service     Start the KOS service for this robot\n")
                formatter.write("  inference   Run a dedicated inference loop for this robot\n\n")
                formatter.write("Examples:\n")
                formatter.write(f"  kos {cmd_name} service\n")
                formatter.write(f"  kos {cmd_name} inference --model=path/to/model --action-scale=0.1\n")
                
                formatter.write("\nOptions:\n")
                formatter.write("  -h, --help  Show this message and exit.\n")
                click.echo(formatter.getvalue().rstrip("\n"), color=ctx.color)
                ctx.exit()
        
        # Add custom help option to robot group
        help_option = click.Option(
            ['-h', '--help'],
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=show_robot_help,
            help='Show this message and exit.',
        )
        robot_group.params.append(help_option)
        
        return robot_group

@click.group(
    cls=MainGroup,
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]}
)
def cli():
    """KOS Command Line Interface."""
    pass



@cli.group("policy", cls=PolicyGroup, help="Policy deployment operations.")
def policy():
    """Commands for managing policy deployment."""
    pass


@policy.command()
@click.argument("policy_file", type=click.Path(exists=True))
@click.option(
    "--episode-length",
    type=float,
    default=30.0,
    show_default=True,
    help="Episode length in seconds",
)
@click.option(
    "--action-scale",
    type=float,
    default=0.1,
    show_default=True,
    help="Scale factor for model outputs (0.0 to 1.0)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Run policy in dry-run mode (no actuators will be moved)",
)
def start(policy_file, episode_length, action_scale, dry_run):
    """Start policy deployment."""
    asyncio.run(policy_start(policy_file, episode_length, action_scale, dry_run))


@policy.command()
def stop():
    """Stop policy deployment."""
    asyncio.run(policy_stop())


@policy.command()
def status():
    """Get current policy state."""
    state = asyncio.run(get_policy_state())
    if state is None:
        click.echo("Failed to get policy state")
        return

    # Format the state nicely
    if state.state:
        click.echo("Policy State:")
        for key, value in state.state.items():
            click.echo(f"  {key}: {value}")
    else:
        click.echo("No policy state available")


@cli.command()
@click.option(
    "--scale",
    type=float,
    default=50.0,
    show_default=True,
    metavar="DEG",
    help="Max |position| in degrees for bar scaling.",
)
@click.option(
    "--ip",
    type=str,
    default="127.0.0.1",
    show_default=True,
    metavar="IP",
    help="KOS service IP address.",
)
def status(scale, ip):
    """Show live system status"""
    asyncio.run(show_status(scale=scale, ip=ip))


@cli.group("actuator", cls=ActuatorGroup, help="Actuator-specific operations.")
def actuator():
    """Commands for querying and configuring actuators."""
    pass


cli.add_command(actuator)


@actuator.command()
@click.argument("ids", required=True)
@click.argument("target", required=True)
@click.option(
    "--velocity",
    "-v",
    type=float,
    default=None,
    help="Target velocity in degrees/second",
)
@click.option("--kp", type=float, default=None, help="Position gain (optional)")
@click.option("--kd", type=float, default=None, help="Velocity gain (optional)")
@click.option(
    "--acceleration", type=float, default=None, help="Acceleration (optional)"
)
@click.option(
    "--wait",
    type=float,
    default=3.0,
    show_default=True,
    help="Seconds to wait for actuators to reach target",
)
def move(ids, target, velocity, kp, kd, acceleration, wait):
    """Move actuators to target position with optional velocity control.

    Examples:
        # Move all actuators to 0 degrees
        kos actuator move all 0

        # Move actuators 11,12 to 90 degrees at 45 deg/s
        kos actuator move 11,12 90 -v 45

        # Move actuator 11 to -45 degrees with custom gains
        kos actuator move 11 -45 --kp 100 --kd 4
    """
    from kos_zbot.tools.actuator_move import actuator_move

    asyncio.run(actuator_move(ids, target, velocity, kp, kd, acceleration, wait))


@actuator.command()
@click.argument("action", type=click.Choice(["enable", "disable"]))
@click.argument("ids", required=True)
def torque(action, ids):
    """Enable or disable torque for given actuator IDs."""
    from kos_zbot.tools.actuator_torque import actuator_torque

    asyncio.run(actuator_torque(action, ids))


@actuator.command()
@click.argument("ids", required=True)
def zero(ids):
    """Zero the given actuator IDs (comma-separated or 'all')."""
    from kos_zbot.tools.actuator_zero import actuator_zero

    asyncio.run(actuator_zero(ids))


@actuator.command()
@click.argument("ids", required=True)
@click.option("--diff", is_flag=True, help="Only show parameters that differ.")
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

    ACTUATOR_IDS = [
        11,
        12,
        13,
        14,
        21,
        22,
        23,
        24,
        31,
        32,
        33,
        34,
        35,
        36,
        41,
        42,
        43,
        44,
        45,
        46,
    ]
    TEST_CONFIG = {
        "kos_ip": "127.0.0.1",
        "amplitude": 10.0,
        "frequency": 1.0,
        "duration": 3600.0,
        "sample_rate": 50.0,
        "start_pos": 0.0,
        "sync_all": False,
        "wave_patterns": {
            "group_1": {
                "actuators": [11, 12, 13, 14],
                "amplitude": 3.0,
                "frequency": 0.75,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 0.0,
                "position_offset": 0.0,
            },
            "group_2": {
                "actuators": [21, 22, 23, 24],
                "amplitude": 3.0,
                "frequency": 0.75,
                "phase_offset": 90.0,
                "freq_multiplier": 1.0,
                "start_pos": 0.0,
                "position_offset": 0.0,
            },
            "group_3": {
                "actuators": [31, 32, 33, 34, 35, 36],
                "amplitude": 3.0,
                "frequency": 0.75,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 0.0,
                "position_offset": 0.0,
            },
            "group_4": {
                "actuators": [41, 42, 43, 44, 45, 46],
                "amplitude": 3.0,
                "frequency": 0.75,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 0.0,
                "position_offset": 0.0,
            },
        },
        "kp": 12.0,
        "kd": 2.0,
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

    ACTUATOR_IDS = [
        11,
        12,
        13,
        14,
        21,
        22,
        23,
        24,
        31,
        32,
        33,
        34,
        35,
        36,
        41,
        42,
        43,
        44,
        45,
        46,
    ]
    TEST_CONFIG = {
        "kos_ip": "127.0.0.1",
        "step_size": 4.0,
        "step_hold_time": 0.2,
        "step_count": 100000,
        "start_pos": 0.0,
        "kp": 20.0,
        "kd": 5.0,
        "ki": 0.0,
        "max_torque": 100.0,
        "acceleration": 1000.0,
        "torque_enabled": True,
        "step_min": 3.0,
        "step_max": 10.0,
        "max_total": 15.0,
        "seed": 42,
    }
    asyncio.run(run_step_test(ACTUATOR_IDS, **TEST_CONFIG))

@test.command()
def imu():
    """Run the IMU test."""
    click.echo("Running IMU test...")
    
    import asyncio
    import time 
    import os
    from kos_zbot.tests.read_imu import run_imu_test

    log_dir = "./kos_zbot/tests/logs"

    datetime = time.strftime("%Y%m%d_%H%M%S", time.localtime())

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    TEST_CONFIG = {
        'kos_ip': '127.0.0.1',
        'sample_time': 20.0,
        'sample_rate': 50.0,
        'read_basic': True,
        'read_quaternion': True,
        'read_euler': False,
        'read_advanced': False,
        'print_stats': True,
        'output_csv': f'{log_dir}/imuTest_{datetime}.csv'
    }
    asyncio.run(run_imu_test(**TEST_CONFIG))


if __name__ == "__main__":
    cli()
