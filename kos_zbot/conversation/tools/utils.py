import os
import tempfile
import subprocess
from pykos import KOS

def capture_jpeg_cli(width: int = 640, height: int = 480, warmup_ms: int = 500) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        cmd = [
            "libcamera-jpeg",
            "-o", tmp.name,
            "-n",                # no preview, headless
            "--width", str(width),
            "--height", str(height),
            "-t", str(warmup_ms),
            "--nopreview",
            "--quality", "75"
        ]
        try:
            subprocess.run(cmd, check=True)
            tmp.seek(0)
            data = tmp.read()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Camera capture failed: {e}")
        finally:
            os.remove(tmp.name)
        return data


def get_wave_hand_config():
    """Get configuration for hand waving animation"""

    return {
        "actuator_ids": [11, 12, 13],
        "config": {
            "kos_ip": "127.0.0.1",
            "amplitude": 15.0,
            "frequency": 1.5,
            "duration": 3.0,
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
                    "start_pos": 0,
                    "position_offset": 0.0,
                },
                "shoulder_roll": {
                    "actuators": [12],
                    "amplitude": 10.0,
                    "frequency": 0.75,
                    "phase_offset": 0.0,
                    "freq_multiplier": 1.0,
                    "start_pos": 120,
                    "position_offset": 0.0,
                },
                "elbow_roll": {
                    "actuators": [13],
                    "amplitude": 20.0,
                    "frequency": 1,
                    "phase_offset": 90.0,
                    "freq_multiplier": 1.0,
                    "start_pos": -60,
                    "position_offset": 0.0,
                },
            },
            "kp": 15.0,
            "kd": 3.0,
            "ki": 0.0,
            "max_torque": 50.0,
            "acceleration": 500.0,
            "torque_enabled": True,
        }
    }


def get_salute_config():
    """Get configuration for saluting animation"""
    return {
        "actuator_ids": [21, 22, 23, 24],
        "config": {
            "kos_ip": "127.0.0.1",
            "squeeze_duration": 5.0,
        }
    }

async def get_robot_status(ip: str = "127.0.0.1"):
    """Get comprehensive robot status data for LLM to analyze and report"""
    client = KOS(ip)

    try:
        resp = await client.actuator.get_actuators_state()
        actuator_states = [
            {
                "actuator_id": s.actuator_id,
                "position": s.position,
                "velocity": s.velocity,
                "online": s.online,
                "faults": list(s.faults),
                "min_position": getattr(s, "min_position", None),
                "max_position": getattr(s, "max_position", None),
            }
            for s in resp.states
        ]
    except Exception as e:
        print("actuator error", e)
        actuator_states = None

    try:
        v = await client.imu.get_imu_values()
        q = await client.imu.get_quaternion()
        calib = await client.imu.get_calibration_state()

        imu_vals = {
            "accel_x": v.accel_x, "accel_y": v.accel_y, "accel_z": v.accel_z,
            "gyro_x": v.gyro_x, "gyro_y": v.gyro_y, "gyro_z": v.gyro_z,
            "mag_x": v.mag_x, "mag_y": v.mag_y, "mag_z": v.mag_z
        }
        imu_quat = {"w": q.w, "x": q.x, "y": q.y, "z": q.z}
        imu_calib = dict(calib.state) if hasattr(calib, "state") else {}
    except Exception as e:
        print("imu error", e)
        imu_vals = imu_quat = imu_calib = None

    status_parts = []

    if actuator_states:
        online_actuators = [s for s in actuator_states if s["online"]]
        offline_actuators = [s for s in actuator_states if not s["online"]]
        faulted_actuators = [s for s in actuator_states if s["faults"]]

        status_parts.append(f"ACTUATOR STATUS:")
        status_parts.append(f"- {len(online_actuators)} actuators online, {len(offline_actuators)} offline")

        if faulted_actuators:
            status_parts.append(f"- FAULTS DETECTED on {len(faulted_actuators)} actuators:")
            for actuator in faulted_actuators:
                faults_str = ", ".join(actuator["faults"])
                status_parts.append(f"  Actuator {actuator['actuator_id']}: {faults_str}")

        if online_actuators:
            status_parts.append("- Current positions:")
            for actuator in online_actuators:
                pos = actuator["position"]
                vel = actuator["velocity"]
                status_parts.append(f"  Actuator {actuator['actuator_id']}: {pos:.1f}° (velocity: {vel:.1f}°/s)")

    if imu_vals and imu_quat and imu_calib:
        status_parts.append(f"\nIMU STATUS:")

        sys_calib = imu_calib.get("sys", 0)
        accel_calib = imu_calib.get("accel", 0)
        gyro_calib = imu_calib.get("gyro", 0)
        mag_calib = imu_calib.get("mag", 0)

        status_parts.append(f"- Calibration: System={sys_calib}/3, Accelerometer={accel_calib}/3, Gyroscope={gyro_calib}/3, Magnetometer={mag_calib}/3")

        status_parts.append(f"- Accelerometer (m/s²): X={imu_vals['accel_x']:.2f}, Y={imu_vals['accel_y']:.2f}, Z={imu_vals['accel_z']:.2f}")
        status_parts.append(f"- Gyroscope (°/s): X={imu_vals['gyro_x']:.2f}, Y={imu_vals['gyro_y']:.2f}, Z={imu_vals['gyro_z']:.2f}")
        status_parts.append(f"- Magnetometer (µT): X={imu_vals['mag_x']:.2f}, Y={imu_vals['mag_y']:.2f}, Z={imu_vals['mag_z']:.2f}")

        w, x, y, z = imu_quat["w"], imu_quat["x"], imu_quat["y"], imu_quat["z"]
        status_parts.append(f"- Quaternion: w={w:.3f}, x={x:.3f}, y={y:.3f}, z={z:.3f}")

    if not status_parts:
        return "I'm operational but unable to get detailed status information right now."

    return "\n".join(status_parts)
