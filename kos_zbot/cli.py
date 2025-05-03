import click

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
    click.echo("Showing status...")

@cli.command()
@click.argument('action', type=click.Choice(['enable', 'disable']))
@click.argument('ids', nargs=-1, type=int)
def torque(action, ids):
    """Enable or disable torque for given actuator IDs."""
    click.echo(f"Torque {action} for IDs: {ids}")

@cli.command()
@click.argument('ids', nargs=-1, type=int)
def zero(ids):
    """Zero the given actuator IDs."""
    click.echo(f"Zeroing IDs: {ids}")

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