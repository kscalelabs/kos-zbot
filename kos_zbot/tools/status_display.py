import multiprocessing as mp
import asyncio
import time
import queue
import argparse
from rich.console import Console, Group
from rich.columns import Columns
from rich.table import Table
from rich.live import Live
from rich.rule import Rule
from types import SimpleNamespace
from pykos import KOS
from kos_zbot.tests.kos_connection import kos_ready_async


import numpy as np
from kos_zbot.utils.quat import rotate_vector_by_quat, GRAVITY_CARTESIAN

BAR_WIDTH = 30

import logging
import os

# Add this at the top of the file, after the imports
def setup_debug_logging():
    """Setup debug logging to a file"""
    log_file = "/tmp/status_display_debug.log"
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, mode='w'),  # Overwrite each time
        ]
    )
    return logging.getLogger(__name__)
debug_logger = setup_debug_logging()

def format_bar(pos: float, width: int = BAR_WIDTH, scale: float = 180.0) -> str:
    """
    Render an ASCII bar of `width` characters,
    centered at zero, clamped to ±scale, colored cyan.
    """
    center = width // 2
    clamped = max(min(pos, scale), -scale)
    scaled = int(round((clamped / scale) * center))
    bar = [" "] * width
    if 0 <= center < width:
        bar[center] = "|"
    if scaled > 0:
        for i in range(1, scaled + 1):
            idx = center + i
            if 0 <= idx < width:
                bar[idx] = "="
    elif scaled < 0:
        for i in range(1, -scaled + 1):
            idx = center - i
            if 0 <= idx < width:
                bar[idx] = "="
    return f"[cyan]{''.join(bar)}[/]"


def make_table(states: list, scale: float = 180.0) -> Table:
    tbl = Table(title="Actuator State", show_header=True, header_style="bold magenta")
    tbl.add_column("ID", justify="right", no_wrap=True)
    tbl.add_column("Min", justify="right")
    tbl.add_column("Max", justify="right")
    tbl.add_column("Pos °", justify="right")
    tbl.add_column("Vel °/s", justify="right")
    tbl.add_column(f"Position (±{scale}°)", no_wrap=True)
    tbl.add_column("Torque", justify="center")
    tbl.add_column("Last Fault", justify="left")
    tbl.add_column("Fault Count", justify="right")
    tbl.add_column("Last Fault Time", justify="left")

    for s in states:
        bar = format_bar(s.position, BAR_WIDTH, scale)
        torque = "[green]ON[/]" if s.online else "[red]OFF[/]"
        min_pos = getattr(s, "min_position", None)
        max_pos = getattr(s, "max_position", None)
        min_str = f"{min_pos:6.1f}" if min_pos is not None else "N/A"
        max_str = f"{max_pos:6.1f}" if max_pos is not None else "N/A"

        if s.faults and len(s.faults) == 3:
            last_fault, fault_count, t = s.faults
            try:
                last_fault_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(t)))
            except Exception:
                last_fault_time = t
        else:
            last_fault = ", ".join(s.faults) if s.faults else ""
            fault_count = str(len(s.faults)) if s.faults else "0"
            last_fault_time = ""
        # Add velocity to the row (default to 0.0 if not present)
        velocity = getattr(s, "velocity", 0.0)
        tbl.add_row(
            str(s.actuator_id),
            min_str,
            max_str,
            f"{s.position:6.2f}",
            f"{velocity:6.2f}",  # <-- Velocity value
            bar,
            torque,
            last_fault,
            fault_count,
            last_fault_time,
        )
    return tbl


def make_imu_table(values, quat, calib_state=None) -> Table:
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
        # TODO: Replace with call from imu getAdvancedValues rather than redundant calc here
        quat_array = np.array([quat.w, quat.x, quat.y, quat.z])
        projgrav = rotate_vector_by_quat(
            GRAVITY_CARTESIAN, quat_array, inverse=True
        )

        tbl.add_row(
            "Quaternion",
            f"{quat.x:.3f}", f"{quat.y:.3f}", f"{quat.z:.3f}", f"{quat.w:.3f}"
        )
        tbl.add_row(
            "Proj Grav (m/s²)",
            f"{projgrav[0]:.3f}", f"{projgrav[1]:.3f}",f"{projgrav[2]:.3f}", ""
        )
    return tbl

def make_latency_table(stats: dict) -> Table:
    """Create a table showing latency statistics for all trackers."""
    tbl = Table(title="Latency Statistics", show_header=True, header_style="bold yellow")
    tbl.add_column("Loop", justify="left")
    tbl.add_column("Mean (ms)", justify="right")
    tbl.add_column("Std (ms)", justify="right")
    tbl.add_column("Min (ms)", justify="right")
    tbl.add_column("Max (ms)", justify="right")
    tbl.add_column("Period (ms)", justify="right")
    tbl.add_column("Samples", justify="right")

    for name, stat in stats.items():
        # Format the statistics with appropriate precision
        tbl.add_row(
            name,
            f"{stat['mean']:.2f}",
            f"{stat['std']:.2f}",
            f"{stat['min']:.2f}",
            f"{stat['max']:.2f}",
            f"{stat['period']:.1f}",
            str(stat['samples'])
        )
    return tbl

def make_calib_table(calib_state) -> Table:
    tbl = Table(title="IMU Calibration", show_header=True, header_style="bold blue")
    tbl.add_column("Component", justify="left")
    tbl.add_column("Value", justify="right")
    if calib_state:
        order = ["sys", "accel", "gyro", "mag"]
        for key in order:
            if key in calib_state:
                tbl.add_row(str(key), str(calib_state[key]))
    return tbl

def init_grid(states, imu_vals, imu_quat, imu_calib, scale: float, latency_stats: dict) -> Table:
    grid = Table.grid()
    imu_group = Columns([
        make_imu_table(SimpleNamespace(**imu_vals), SimpleNamespace(**imu_quat)),
        make_calib_table(imu_calib)
    ])
    latency_table = make_latency_table(latency_stats)

    grid.add_row(imu_group)
    grid.add_row(make_table([SimpleNamespace(**d) for d in states], scale),)
    grid.add_row(latency_table)
    return grid


def actuator_worker(out_q: mp.Queue, freq: float = 30.0, ip: str = "127.0.0.1"):
    async def poll():
        client = KOS(ip)
        period = 1.0 / freq
        while True:
            try:
                resp = await client.actuator.get_actuators_state()
                serial_states = [{
                    "actuator_id": s.actuator_id,
                    "position":    s.position,
                    "velocity":    s.velocity,
                    "online":      s.online,
                    "faults":      list(s.faults),
                    "min_position": getattr(s, "min_position", None),
                    "max_position": getattr(s, "max_position", None),
                } for s in resp.states]
                if out_q.full(): out_q.get_nowait()
                out_q.put(serial_states)
            except Exception as e:
                await asyncio.sleep(period)
            else:
                await asyncio.sleep(period)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())


def imu_worker(out_q: mp.Queue, freq: float = 30.0, ip: str = "127.0.0.1"):
    async def poll():
        client = KOS(ip)
        period = 1.0 / freq
        while True:
            try:
                v = await client.imu.get_imu_values()
                q = await client.imu.get_quaternion()
                calib = await client.imu.get_calibration_state()
                serial_vals = {"accel_x": v.accel_x, "accel_y": v.accel_y, "accel_z": v.accel_z,
                               "gyro_x":  v.gyro_x,  "gyro_y":  v.gyro_y,  "gyro_z":  v.gyro_z,
                               "mag_x":   v.mag_x,   "mag_y":   v.mag_y,   "mag_z":   v.mag_z}
                serial_quat = {"w": q.w, "x": q.x, "y": q.y, "z": q.z}
                serial_calib = dict(calib.state) if hasattr(calib, "state") else {}
                if out_q.full(): out_q.get_nowait()
                out_q.put((serial_vals, serial_quat, serial_calib))
            except Exception:
                await asyncio.sleep(period)
            else:
                await asyncio.sleep(period)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())


def latency_worker(out_q: mp.Queue, freq: float = 30.0, ip: str = "127.0.0.1"):
    async def poll():
        client = KOS(ip)
        period = 1.0 / freq
        while True:
            try:
                # Get latency stats from KOS service
                resp = await client.policy.get_latency_stats()
                if out_q.full(): out_q.get_nowait()
                out_q.put(dict(resp.stats))
            except Exception:
                await asyncio.sleep(period)
            else:
                await asyncio.sleep(period)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll())

async def show_status(scale: float = 180.0,
                      act_freq: float = 20.0,
                      imu_freq: float = 20.0,
                      ip: str = "127.0.0.1"):
    if not await kos_ready_async(ip): 
        print(f"KOS service not available at {ip}:50051")
        print("Please start the KOS service with 'kos service'")
        print("or specify a different IP address with '--ip <ip>'")
        return
    console = Console()
    console.clear()
    title = Rule("[bold white]K-OS Zbot v0.1 Status[/]")

    act_q = mp.Queue(maxsize=1)
    imu_q = mp.Queue(maxsize=1)
    latency_q = mp.Queue(maxsize=1)
    act_p = mp.Process(target=actuator_worker, args=(act_q, act_freq, ip), daemon=True)
    imu_p = mp.Process(target=imu_worker, args=(imu_q, imu_freq, ip), daemon=True)
    latency_p = mp.Process(target=latency_worker, args=(latency_q, act_freq, ip), daemon=True)
    act_p.start() 
    imu_p.start()
    latency_p.start()

    # Default zero IMU values
    zero_states = []
    zero_imu_vals = {
        "accel_x": 0.0, "accel_y": 0.0, "accel_z": 0.0,
        "gyro_x": 0.0, "gyro_y": 0.0, "gyro_z": 0.0,
        "mag_x": 0.0, "mag_y": 0.0, "mag_z": 0.0
    }
    zero_imu_quat = {"w": 1.0, "x": 0.0, "y": 0.0, "z": 0.0}
    zero_imu_calib = {"sys": 0, "gyro": 0, "accel": 0, "mag": 0}
    zero_latency_stats = {}

    # Start with all zeros
    states = zero_states
    imu_vals, imu_quat, imu_calib = zero_imu_vals, zero_imu_quat, zero_imu_calib
    latency_stats = zero_latency_stats

    render_rate = 30
    render_interval = 1.0 / render_rate

    # build initial grid once
    initial_grid = init_grid(states, imu_vals, imu_quat, imu_calib, scale, latency_stats)

    with Live(Group(title, initial_grid), console=console,
              refresh_per_second=render_rate, screen=True) as live:

        last_states = states
        while True:
            updated = False
            try:
                states = act_q.get_nowait() 
                updated = True
            except queue.Empty:
                pass

            try:
                imu_vals, imu_quat, imu_calib = imu_q.get_nowait();
                if imu_vals is None: imu_vals = zero_imu_vals
                if imu_quat is None: imu_quat = zero_imu_quat
                if imu_calib is None: imu_calib = zero_imu_calib
                updated = True
            except queue.Empty: 
                pass

            try:
                latency_stats = latency_q.get_nowait()
                updated = True
            except queue.Empty:
                pass

            if updated:
                new_grid = init_grid(states, imu_vals, imu_quat, imu_calib, scale, latency_stats)
                live.update(Group(title, new_grid))
                last_states = states

            await asyncio.sleep(render_interval)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale",    type=float, default=180.0)
    parser.add_argument("--act-freq", type=float, default=30.0)
    parser.add_argument("--imu-freq", type=float, default=30.0)
    parser.add_argument("--ip",       type=str,   default="127.0.0.1")
    args = parser.parse_args()
    asyncio.run(show_status(args.scale, args.act_freq, args.imu_freq, args.ip))
