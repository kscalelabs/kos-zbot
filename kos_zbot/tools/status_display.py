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
        console.print(
            "[yellow]Tip: Run with [bold]--freq 50[/bold] to see live updates at 50 Hz.[/yellow]"
        )
        return

    # shared stats
    fetch_count = 0
    fetch_start = asyncio.get_event_loop().time()
    render_count = 0
    render_start = fetch_start
    render_interval = 1 / 20  # 25 Hz render

    queue: asyncio.Queue[list] = asyncio.Queue(maxsize=1)

    async def reader():
        nonlocal fetch_count
        while True:
            resp = await kos.actuator.get_actuators_state()
            fetch_count += 1
            # keep only the newest snapshot
            if queue.full():
                _ = queue.get_nowait()
            await queue.put(resp.states)

    asyncio.create_task(reader())

    overrun_count = 0

    def make_status_text():
        now = asyncio.get_event_loop().time()

        # actual fetch rate
        fetch_elapsed = now - fetch_start
        actual_fetch = fetch_count / fetch_elapsed if fetch_elapsed > 0 else 0

        # actual render rate
        render_elapsed = now - render_start
        actual_render = render_count / render_elapsed if render_elapsed > 0 else 0

        return (
            f"[cyan]Data (Hz):[/] {actual_fetch:.1f}/{freq}    "
            f"[cyan]Render (Hz):[/] {actual_render:.1f}/20    "
            f"[red]Overruns:[/] {overrun_count}"
        )

    # initial renderable
    renderable = Group(title, make_table(states, scale), make_status_text())
    with Live(renderable, console=console, refresh_per_second=25, screen=True) as live:
        next_time = asyncio.get_event_loop().time()
        while True:
            now = asyncio.get_event_loop().time()
            if now > next_time:
                overrun_count += 1
                next_time = now
            else:
                await asyncio.sleep(next_time - now)
            next_time += render_interval

            # grab freshest data if available
            try:
                states = queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

            render_count += 1
            live.update(Group(title, make_table(states, scale), make_status_text()))
