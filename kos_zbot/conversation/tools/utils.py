import os
import tempfile
import subprocess

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