import threading
import queue
import asyncio
import time
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.rule import Rule
from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async

BAR_WIDTH = 30

def format_bar(pos: float, width: int = BAR_WIDTH, scale: float = 180.0) -> str:
    """
    Render an ASCII bar of `width` characters,
    centered at zero, clamped to ±scale, colored cyan.
    """
    center = width // 2
    clamped = max(min(pos, scale), -scale)
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
    tbl.add_column(f"Position (±{scale}°)", no_wrap=True)
    tbl.add_column("Torque", justify="center")
    tbl.add_column("Faults", justify="left")

    for s in states:
        bar = format_bar(s.position, BAR_WIDTH, scale)
        torque = "[green]ON[/]" if s.online else "[red]OFF[/]"
        faults = ", ".join(s.faults) if s.faults else ""
        tbl.add_row(str(s.actuator_id), f"{s.position:6.2f}", bar, torque, faults)

    return tbl

class PollerThread(threading.Thread):
    """
    Polls an async RPC at maximum rate in its own loop/thread,
    and keeps only the latest result in a size-1 queue.
    """
    def __init__(self, rpc_coro_fn, out_queue: queue.Queue):
        super().__init__(daemon=True)
        self.rpc_coro_fn = rpc_coro_fn
        self.out_queue = out_queue

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        client = KOS("127.0.0.1")

        while True:
            try:
                resp = loop.run_until_complete(self.rpc_coro_fn(client))
            except Exception:
                # ignore and retry
                continue

            data = getattr(resp, "states", resp)
            if self.out_queue.full():
                try:
                    self.out_queue.get_nowait()
                except queue.Empty:
                    pass
            self.out_queue.put(data)
            # no explicit sleep: poll as fast as the RPC allows

async def show_status(scale: float = 180.0):
    kos_ip = "127.0.0.1"
    if not await kos_ready_async(kos_ip):
        print(f"KOS service not available at {kos_ip}:50051")
        return

    console = Console()
    console.clear()
    title = Rule("[bold white]K-OS Zbot v0.1 Status[/]")

    # set up the actuator poller
    actuator_q: queue.Queue = queue.Queue(maxsize=1)
    actuator_poller = PollerThread(
        rpc_coro_fn=lambda client: client.actuator.get_actuators_state(),
        out_queue=actuator_q,
    )
    actuator_poller.start()

    # wait for first snapshot
    while actuator_q.empty():
        await asyncio.sleep(0.001)
    states = actuator_q.get_nowait()

    render_interval = 1 / 20  # UI at 20 Hz

    with Live(Group(title, make_table(states, scale)), console=console, refresh_per_second=30, screen=True) as live:
        while True:
            try:
                states = actuator_q.get_nowait()
            except queue.Empty:
                pass

            live.update(Group(title, make_table(states, scale)))
            await asyncio.sleep(render_interval)