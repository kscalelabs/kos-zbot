from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.rule import Rule
from pykos import KOS
import asyncio

BAR_WIDTH = 30


def format_bar(pos: float, width: int = BAR_WIDTH, scale: float = 180.0) -> str:
    """
    Render an ASCII bar of `width` characters,
    centered at zero, clamped to ±scale, colored cyan.
    """
    center = width // 2
    # clamp into [-scale, +scale]
    clamped = max(min(pos, scale), -scale)
    # map [-scale..+scale] -> [-center..+center]
    scaled = int((clamped / scale) * center)

    bar = [" "] * width
    bar[center] = "|"
    if scaled > 0:
        for i in range(1, scaled + 1):
            bar[center + i] = "="
    elif scaled < 0:
        for i in range(1, -scaled + 1):
            bar[center - i] = "="

    return f"[cyan]{''.join(bar)}[/]"


def make_table(states: list, scale: float = 180.0) -> Table:
    """
    Build a Rich Table from a list of actuator states,
    using `scale` for the bar graph.
    """
    tbl = Table(show_header=True, header_style="bold magenta")
    tbl.add_column("ID", justify="right", no_wrap=True)
    tbl.add_column("Pos °", justify="right")
    tbl.add_column(f"Position (Scaled: ±{scale}°)", no_wrap=True)
    tbl.add_column("Torque", justify="center")
    tbl.add_column("Faults", justify="left")

    for s in states:
        bar = format_bar(s.position, BAR_WIDTH, scale)
        torque = "[green]ON[/]" if s.online else "[red]OFF[/]"
        faults = ", ".join(s.faults) if s.faults else ""
        tbl.add_row(str(s.actuator_id), f"{s.position:6.2f}", bar, torque, faults)

    return tbl


async def show_status(freq: int = None, scale: float = 180.0):
    """
    If freq is None: print one snapshot and exit.
    Otherwise: live-update at `freq` Hz, scaling bars to ±scale.
    """
    console = Console()
    console.clear()

    title = Rule("[bold white]K-OS Zbot v0.1 Status[/]", style="bold white")

    kos = KOS("127.0.0.1")
    resp = await kos.actuator.get_actuators_state()
    states = resp.states

    # one-shot
    if freq is None:
        console.print(title)
        console.print(make_table(states, scale))
        return

    # live mode in alternate screen (auto-clears on resize)
    renderable = Group(title, make_table(states, scale))
    with Live(
        renderable, console=console, refresh_per_second=freq, screen=True
    ) as live:
        while True:
            resp = await kos.actuator.get_actuators_state()
            live.update(Group(title, make_table(resp.states, scale)))
            await asyncio.sleep(1 / freq)
