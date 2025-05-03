import click
from tabulate import tabulate
from pykos import KOS
import asyncio

@click.group()
def cli():
    """KOS ZBot Command Line Interface."""
    pass

@cli.command()
def service():
    """Start the KOS service."""
    # Import and run your service logic here
    from kos_zbot.kos import main as service_main
    service_main()

@cli.command()
def scan():
    """Scan for available actuators."""
    # Call your scan logic here
    click.echo("Scanning for actuators...")

@cli.command()
def status():
    """Show status of actuators."""
    from pykos import KOS
    from tabulate import tabulate

    async def _status():
        kos = KOS("127.0.0.1")
        response = await kos.actuator.get_actuators_state()
        headers = ["ID", "Position (°)", "Torque", "Faults"]
        table = []
        for state in response.states:
            table.append([
                state.actuator_id,
                f"{state.position:.2f}",
                "ON" if state.online else "OFF",
                ", ".join(state.faults) if state.faults else ""
            ])
        click.echo(tabulate(table, headers=headers, tablefmt="simple"))

    asyncio.run(_status())

@cli.command()
@click.argument('action', type=click.Choice(['enable', 'disable']))
@click.argument('ids', required=True)
def torque(action, ids):
    """Enable or disable torque for given actuator IDs (comma-separated or 'all')."""
    import asyncio

    async def _torque():
        kos = KOS("127.0.0.1")
        # Get all actuator IDs if 'all' is specified
        if ids.lower() == "all":
            status = await kos.actuator.get_actuators_state()
            actuator_ids = [state.actuator_id for state in status.states]
        else:
            try:
                actuator_ids = [int(id.strip()) for id in ids.split(",")]
            except ValueError:
                click.echo("Error: IDs must be comma-separated integers or 'all'")
                return

        enable = action == "enable"
        print(enable)
        for actuator_id in actuator_ids:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, torque_enabled=enable)
        click.echo(f"Torque {'enabled' if enable else 'disabled'} for: {actuator_ids}")

    asyncio.run(_torque())

@cli.command()
@click.argument('ids', required=True)
def zero(ids):
    """Zero the given actuator IDs (comma-separated or 'all')."""
    import asyncio

    async def _zero():
        kos = KOS("127.0.0.1")
        # Get all actuator IDs if 'all' is specified
        if ids.lower() == "all":
            status = await kos.actuator.get_actuators_state()
            actuator_ids = [state.actuator_id for state in status.states]
        else:
            try:
                actuator_ids = [int(id.strip()) for id in ids.split(",")]
            except ValueError:
                click.echo("Error: IDs must be comma-separated integers or 'all'")
                return
        print(f"Zeroing actuators: {actuator_ids}")
        # Get original positions
        orig_status = await kos.actuator.get_actuators_state(actuator_ids)
        orig_positions = {state.actuator_id: state.position for state in orig_status.states}

        # Zero each actuator
        for actuator_id in actuator_ids:
            await kos.actuator.configure_actuator(actuator_id=actuator_id, zero_position=True)
            await asyncio.sleep(0.2)  # Give hardware time

        await asyncio.sleep(3)
        # Get new positions
        new_status = await kos.actuator.get_actuators_state(actuator_ids)
        new_positions = {state.actuator_id: state.position for state in new_status.states}

        # Prepare table
        headers = ["ID", "Original Position (°)", "New Position (°)"]
        table = []
        for actuator_id in actuator_ids:
            table.append([
                actuator_id,
                f"{orig_positions.get(actuator_id, 'N/A'):.2f}",
                f"{new_positions.get(actuator_id, 'N/A'):.2f}"
            ])
        click.echo(tabulate(table, headers=headers, tablefmt="simple"))

    asyncio.run(_zero())

@cli.group()
def test():
    """Test commands."""
    pass

@test.command()
def sync_wave():
    click.echo("Running sync_wave test...")

@test.command()
def sync_step():
    click.echo("Running sync_step test...")

@test.command()
def imu():
    click.echo("Running IMU test...")

@cli.command()
@click.argument('ids', nargs=-1, type=int)
@click.argument('positions', nargs=-1, type=float)
def move(ids, positions):
    """Move actuators to specified positions."""
    click.echo(f"Moving IDs {ids} to positions {positions}")

if __name__ == '__main__':
    cli()