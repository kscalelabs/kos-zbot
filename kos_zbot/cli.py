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
from kos_zbot.tests.kos_connection import kos_ready

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
        formatter.write("  kos service                 Start KOS service without robot metadata\n")
        formatter.write("  kos <robot_name>            Start service for a robot\n")
        formatter.write("  kos <robot_name> infer      Run inference for a robot\n\n")
        formatter.write("Built-in commands:\n")
        formatter.write("  kos policy                  Policy operations\n")
        formatter.write("  kos status                  Show system status\n")
        formatter.write("  kos actuator                Actuator operations\n")
        formatter.write("  kos test                    Run tests\n")
        formatter.write("  kos demo                    Run demonstration sequences\n")
        
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
        @click.group(cmd_name, help=f"Commands for robot name: '{cmd_name}'", invoke_without_command=True)
        @click.pass_context
        def robot_group(ctx):
            """Robot-specific commands."""
            # If no subcommand is provided, run the service
            if ctx.invoked_subcommand is None:
                try:
                    # Load robot metadata
                    metadata_manager = RobotMetadata.get_instance()
                    metadata_manager.load_model_metadata(cmd_name)
                    
                    # Start the service
                    from kos_zbot.kos import main as service_main
                    service_main()
                except Exception as e:
                    # Check if it's a robot not found error
                    if "No metadata found for model" in str(e) or "404" in str(e):
                        click.echo(f"Error: Robot '{cmd_name}' not found.", err=True)
                        click.echo("Use 'kscale robot list' to view available robots.", err=True)
                        ctx.exit(1)
                    else:
                        # Re-raise other exceptions
                        raise

        @robot_group.command("infer")
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
            try:
                # Load robot metadata
                metadata_manager = RobotMetadata.get_instance()
                metadata_manager.load_model_metadata(cmd_name)
                
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
            except Exception as e:
                # Check if it's a robot not found error
                if "No metadata found for model" in str(e) or "404" in str(e):
                    click.echo(f"Error: Robot '{cmd_name}' not found.", err=True)
                    click.echo("Use 'kscale robot list' to view available robots.", err=True)
                    ctx.exit(1)
                else:
                    # Re-raise other exceptions
                    raise
        
        # Use the same custom help approach for robot group
        def show_robot_help(ctx, param, value):
            if value and not ctx.resilient_parsing:
                formatter = ctx.make_formatter()
                formatter.write(f"Robot: {cmd_name}\n\n")
                formatter.write("Commands:\n")
                formatter.write("  (no command)    Start the KOS service for this robot\n")
                formatter.write("  infer           Run a dedicated inference loop for this robot\n\n")
                formatter.write("Examples:\n")
                formatter.write(f"  kos {cmd_name}\n")
                formatter.write(f"  kos {cmd_name} infer --model=path/to/model --action-scale=0.1\n")
                
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


@cli.command()
def service():
    """Start the KOS service without robot metadata."""
    from kos_zbot.kos import main as service_main
    service_main()


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
@click.option(
    "--id",
    "--ids",
    "ids",
    required=True,
    help="Actuator IDs (comma-separated or 'all')",
)
@click.option(
    "--pos",
    "--position",
    "target",
    type=float,
    required=True,
    help="Target position in degrees",
)
@click.option(
    "--vel",
    "--velocity",
    "velocity",
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
        kos actuator move --id all --pos 0

        # Move actuators 11,12 to 90 degrees at 45 deg/s
        kos actuator move --id 11,12 --pos 90 --vel 45

        # Move actuator 11 to -45 degrees with custom gains
        kos actuator move --id 11 --pos -45 --kp 100 --kd 4
        
        # Your example: move actuators 11,12 to -10 degrees at 2 deg/s
        kos actuator move --pos -10 --vel 2 --id 11,12
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


@cli.group(cls=click.Group, help="Run demonstration sequences.")
def demo():
    """Demo commands."""
    pass

cli.add_command(demo)

@demo.command()
@click.option(
    "--ip",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="KOS service IP address",
)
@click.option(
    "--configure",
    type=bool,
    default=True,
    show_default=True,
    help="Configure the actuators prior to running the demo",
)
def conversation(ip, configure):
    """Run the conversation demo."""
    import asyncio
    from kos_zbot.conversation.main import run_voice_system
    from kos_zbot.tests.kos_connection import kos_ready_async
    if not kos_ready(ip): 
        print(f"KOS service not available at {ip}:50051")
        print("Please start the KOS service with 'kos service'")
        print("or specify a different IP address with '--ip <ip>'")
        return
   
    click.echo("Starting conversation demo...")
    asyncio.run(run_voice_system())

@demo.command()
@click.option(
    "--duration",
    type=float,
    default=5.0,
    show_default=True,
    help="Duration of the salute in seconds",
)
@click.option(
    "--amplitude",
    type=float,
    default=15.0,
    show_default=True,
    help="Salute amplitude in degrees",
)
@click.option(
    "--frequency",
    type=float,
    default=.75,
    show_default=True,
    help="Salute frequency in Hz",
)
@click.option(
    "--ip",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="KOS service IP address",
)
def salute(duration, amplitude, frequency, ip):
    """Salute Demo Sequence"""
    import asyncio
    from kos_zbot.scripts.salute import salute as salute_func

    HAND_ACTUATOR_IDS = [21,22,23,24]

    SALUTE_CONFIG = {
        "kos_ip": ip,
        "squeeze_duration": duration,
        "squeeze_amplitude": amplitude,
        "squeeze_freq": frequency,
        "kp": 15.0,
        "kd": 3.0,
        "ki": 0.0,
        "max_torque": 50.0,  # Lower torque for gentle hand waving
        "acceleration": 500.0,
        "torque_enabled": True,
    }

    click.echo(f"Starting salute demo for {duration} seconds...")
    click.echo(f"Amplitude: {amplitude}°, Frequency: {frequency} Hz")
    asyncio.run(salute_func(HAND_ACTUATOR_IDS, **SALUTE_CONFIG))

@demo.command()
@click.option(
    "--duration",
    type=float,
    default=5.0,
    show_default=True,
    help="Duration of the hand wave in seconds",
)
@click.option(
    "--amplitude",
    type=float,
    default=15.0,
    show_default=True,
    help="Wave amplitude in degrees",
)
@click.option(
    "--frequency",
    type=float,
    default=1.5,
    show_default=True,
    help="Wave frequency in Hz",
)
@click.option(
    "--ip",
    type=str,
    default="127.0.0.1",
    show_default=True,
    help="KOS service IP address",
)
def hand_wave(duration, amplitude, frequency, ip):
    """Run a hand waving demonstration."""
    import asyncio
    from kos_zbot.tests.hello_wave import run_sine_test

    # Hand actuator IDs (assuming these are the hand/arm actuators)
    HAND_ACTUATOR_IDS = [11,12,13]
    
    HAND_WAVE_CONFIG = {
        "kos_ip": ip,
        "amplitude": amplitude,
        "frequency": frequency,
        "duration": duration,  # Use the CLI parameter instead of hardcoded value
        "sample_rate": 50.0,
        "start_pos": 0.0,
        "sync_all": False,
        "wave_patterns": {
            "shoulder_pitch": {
                "actuators": [11],
                "amplitude": 5.0,
                "frequency": 0.25,
                "phase_offset": 0.0,
                "freq_multiplier": 1.0,
                "start_pos": 120.0,
                "position_offset": 0.0,
            },
             "shoulder_roll": {
                 "actuators": [12],
                 "amplitude": 10.0,
                 "frequency": 0.75,
                 "phase_offset": 0.0,
                 "freq_multiplier": 1.0,
                 "start_pos": 0.0,
                 "position_offset": 0.0,
             },
              "elbow_roll": {
                 "actuators": [13],
                 "amplitude": 10.0,
                 "frequency": 1,
                 "phase_offset": 90.0,
                 "freq_multiplier": 1.0,
                 "start_pos": 0.0,
                 "position_offset": 0.0,
             },
        },
        "kp": 15.0,
        "kd": 3.0,
        "ki": 0.0,
        "max_torque": 50.0,  # Lower torque for gentle hand waving
        "acceleration": 500.0,
        "torque_enabled": True,
    }
    
    click.echo(f"Starting hand wave demo for {duration} seconds...")
    click.echo(f"Amplitude: {amplitude}°, Frequency: {frequency} Hz")
    asyncio.run(run_sine_test(HAND_ACTUATOR_IDS, **HAND_WAVE_CONFIG))


@test.command()
def imu():
    """Run the IMU test."""
    click.echo("Running IMU test...")


if __name__ == "__main__":
    cli()