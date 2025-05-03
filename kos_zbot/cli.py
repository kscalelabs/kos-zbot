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

@cli.command()
@click.argument('ids', required=True)
@click.option('--diff', is_flag=True, help="Only show parameters that differ between actuators.")
def dump(ids, diff):
    """Dump parameters from actuator IDs (comma-separated or 'all')."""
    import asyncio
    from google.protobuf.json_format import MessageToDict

    async def _dump():
        kos = KOS("127.0.0.1")

        # Determine actuator IDs
        if ids.lower() == "all":
            status = await kos.actuator.get_actuators_state()
            actuator_ids = [s.actuator_id for s in status.states]
        else:
            try:
                actuator_ids = [int(i.strip()) for i in ids.split(",")]
            except ValueError:
                click.echo("Error: IDs must be comma-separated integers or 'all'")
                return

        # Call the GetParameters gRPC endpoint
        response = await kos.actuator.parameter_dump(actuator_ids)

        # Convert to dictionary: {actuator_id: {param: value}}
        param_map = {}
        for entry in response.entries:
            struct_dict = MessageToDict(entry.parameters, preserving_proto_field_name=True)
            param_map[entry.actuator_id] = struct_dict

        all_param_names = set(
            k for params in param_map.values() for k in params.keys()
        )

        # Build a mapping from param name to address (using the first actuator as reference)
        param_addr_map = {name: param_map[actuator_ids[0]][name]["addr"] for name in all_param_names if name in param_map[actuator_ids[0]]}

        sorted_param_names = sorted(
            all_param_names,
            key=lambda name: int(param_addr_map.get(name, 9999))
        )

    
        # Build table data
        headers = ["Parameter"] + [str(aid) for aid in actuator_ids]
        rows = []

        for param in sorted_param_names:
            values = []
            unique_values = set()
            for aid in actuator_ids:
                val = param_map.get(aid, {}).get(param, {}).get("value", "N/A")
                unique_values.add(str(val))
                values.append(str(val))
            
            if diff and len(unique_values) <= 1:
                continue  # Skip if no difference
            
            row = [param] + values
            rows.append(row)

        if not rows:
            click.echo("No differing parameters found." if diff else "No parameters found.")
            return

        click.echo(tabulate(rows, headers=headers, tablefmt="simple"))

    asyncio.run(_dump())


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