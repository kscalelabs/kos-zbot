import multiprocessing as mp
import asyncio
import time
import queue
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.rule import Rule
from types import SimpleNamespace
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
    # Add a title for the actuator table
    tbl = Table(title="Actuator State", show_header=True, header_style="bold magenta")
    tbl.add_column("ID", justify="right", no_wrap=True)
    tbl.add_column("Pos °", justify="right")
    tbl.add_column(f"Position (±{scale}°)", no_wrap=True)
    tbl.add_column("Torque", justify="center")
    tbl.add_column("Last Fault", justify="left")
    tbl.add_column("Fault Count", justify="right")
    tbl.add_column("Last Fault Time", justify="left")

    for s in states:
        bar = format_bar(s.position, BAR_WIDTH, scale)
        torque = "[green]ON[/]" if s.online else "[red]OFF[/]"
        if s.faults and len(s.faults) == 3:
            last_fault, fault_count, t = s.faults
            try:
                last_fault_time = time.strftime(
                    '%Y-%m-%d %H:%M:%S', time.localtime(int(t)))
            except Exception:
                last_fault_time = t
        else:
            last_fault = ", ".join(s.faults) if s.faults else ""
            fault_count = str(len(s.faults)) if s.faults else "0"
            last_fault_time = ""
        tbl.add_row(
            str(s.actuator_id),
            f"{s.position:6.2f}",
            bar,
            torque,
            last_fault,
            fault_count,
            last_fault_time,
        )
    return tbl


def make_imu_table(values, quat) -> Table:
    """
    Build a Rich Table from IMU get_values and get_quaternion data.
    """
    tbl = Table(title="IMU Status", show_header=True, header_style="bold blue")
    tbl.add_column("Type", justify="left")
    tbl.add_column("X", justify="right")
    tbl.add_column("Y", justify="right")
    tbl.add_column("Z", justify="right")
    tbl.add_column("W", justify="right")

    if values:
        tbl.add_row(
            "Accel (m/s²)",
            f"{values.accel_x:.2f}", f"{values.accel_y:.2f}", f"{values.accel_z:.2f}", ""
        )
        tbl.add_row(
            "Gyro (°/s)",
            f"{values.gyro_x:.2f}", f"{values.gyro_y:.2f}", f"{values.gyro_z:.2f}", ""
        )
        tbl.add_row(
            "Mag (uT)",
            f"{values.mag_x:.2f}", f"{values.mag_y:.2f}", f"{values.mag_z:.2f}", ""
        )
    if quat:
        # Display quaternion components in X, Y, Z, W order
        tbl.add_row(
            "Quaternion",
            f"{quat.x:.3f}", f"{quat.y:.3f}", f"{quat.z:.3f}", f"{quat.w:.3f}"
        )
    return tbl


def actuator_worker(out_q: mp.Queue):
    """Run in separate process; poll actuators and send plain dicts."""
    async def poll():
        client = KOS("127.0.0.1")
        while True:
            try:
                resp = await client.actuator.get_actuators_state()
                serial_states = [
                    {
                        "actuator_id": s.actuator_id,
                        "position":    s.position,
                        "online":      s.online,
                        "faults":      list(s.faults),
                    }
                    for s in resp.states
                ]
                if out_q.full():
                    out_q.get_nowait()
                out_q.put(serial_states)
            except Exception:
                await asyncio.sleep(0.01)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())


def imu_worker(out_q: mp.Queue):
    """Run in separate process; poll IMU and send plain dicts."""
    async def poll():
        client = KOS("127.0.0.1")
        while True:
            try:
                v = await client.imu.get_imu_values()
                q = await client.imu.get_quaternion()
                serial_vals = {
                    "accel_x": v.accel_x, "accel_y": v.accel_y, "accel_z": v.accel_z,
                    "gyro_x":  v.gyro_x,  "gyro_y":  v.gyro_y,  "gyro_z":  v.gyro_z,
                    "mag_x":   v.mag_x,   "mag_y":   v.mag_y,   "mag_z":   v.mag_z,
                }
                serial_quat = {"w": q.w, "x": q.x, "y": q.y, "z": q.z}
                if out_q.full():
                    out_q.get_nowait()
                out_q.put((serial_vals, serial_quat))
            except Exception:
                await asyncio.sleep(0.01)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())

async def show_status(scale: float = 180.0):
    """Main coroutine: launch workers, display live tables."""
    if not await kos_ready_async("127.0.0.1"):
        print("KOS service not available at 127.0.0.1:50051")
        return

    console = Console()
    console.clear()
    title = Rule("[bold white]K-OS Zbot v0.1 Status[/]")

    act_q = mp.Queue(maxsize=1)
    imu_q = mp.Queue(maxsize=1)
    act_p = mp.Process(target=actuator_worker, args=(act_q,), daemon=True)
    imu_p = mp.Process(target=imu_worker, args=(imu_q,), daemon=True)
    act_p.start()
    imu_p.start()

    while act_q.empty() or imu_q.empty():
        await asyncio.sleep(0.01)
    raw_states = act_q.get()
    raw_imu, raw_quat = imu_q.get()
    last_imu = (raw_imu, raw_quat)

    render_interval = 1 / 20  # 20 Hz UI

    with Live(
        Group(
            title,
            (lambda grid: (grid.add_row(
                make_table([SimpleNamespace(**d) for d in raw_states], scale),
                make_imu_table(SimpleNamespace(**raw_imu), SimpleNamespace(**raw_quat))
            ), grid)[1])(Table.grid())
        ),
        console=console,
        refresh_per_second=30,
        screen=True
    ) as live:
        while True:
            try:
                raw_states = act_q.get_nowait()
            except queue.Empty:
                pass
            try:
                raw_imu, raw_quat = imu_q.get_nowait()
                last_imu = (raw_imu, raw_quat)
            except queue.Empty:
                raw_imu, raw_quat = last_imu

            new_grid = Table.grid()
            new_grid.add_row(
                make_table([SimpleNamespace(**d) for d in raw_states], scale),
                make_imu_table(SimpleNamespace(**raw_imu), SimpleNamespace(**raw_quat))
            )

            live.update(
                Group(
                    title,
                    new_grid
                )
            )
            await asyncio.sleep(render_interval)

if __name__ == "__main__":
    asyncio.run(show_status())
