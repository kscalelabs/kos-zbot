import time
import queue
import logging
import threading
from multiprocessing import Process, Queue

import board
import busio
import adafruit_bno055
from kos_zbot.utils.logging import get_logger


class IMUNotAvailableError(Exception):
    """Raised when the IMU sensor is not available."""

    pass


def _sensor_proc(q: Queue, rate_hz: int):
    """
    Child process: read the BNO055 at rate_hz using a deadline-based loop,
    keep only the latest sample in the queue, and log timing overruns.
    """
    log = get_logger("sensor_proc")
    period = 1.0 / rate_hz
    next_deadline = time.monotonic()

    # Initialize latency tracker
    period_ns = int(period * 1e9)
    # latency_tracker = get_tracker("imu_loop")
    # latency_tracker.set_period(period_ns)

    # Initialize I2C inside the child process
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        sensor = adafruit_bno055.BNO055_I2C(i2c)
    except Exception as e:
        q.put_nowait({"error": f"IMU initialization failed: {e}"})
        return

    while True:
        # latency_tracker.record_iteration()
        now = time.monotonic()
        if now > next_deadline:
            overrun_ms = (now - next_deadline) * 1000.0
            # if overrun_ms > 0.5:
            #    log.warning(
            #        f"Timing overrun: {overrun_ms:.2f}ms (target: {period*1000:.2f}ms)"
            #    )
            next_deadline = now
        next_deadline += period

        # Read sensor data and push to queue
        try:
            data = (
                sensor.acceleration,
                sensor.gyro,
                sensor.magnetic,
                sensor.quaternion,
                sensor.calibration_status,
            )
        except Exception:
            # If sensor failure, log full traceback and skip
            log.exception("Failed to read sensor values")
            data = None

        if data:
            try:
                if q.full():
                    # drop oldest sample
                    try:
                        q.get_nowait()
                    except queue.Empty:
                        pass
                q.put_nowait(data)
            except queue.Full:
                # race condition: queue filled since check, safe to ignore
                pass
            except Exception:
                log.exception("Unexpected queue error in sensor process")

        sleep_time = next_deadline - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)


class BNO055Manager:
    def __init__(self, update_rate=100):
        self.log = get_logger(__name__)
        self._imu_available = True
        self._imu_error_msg = None

        self.update_rate = update_rate
        # IPC queue (size=1) holds latest sample
        self._queue: Queue = Queue(maxsize=1)
        self._process: Process | None = None
        # Thread for draining queue into buffer
        self._reader_thread: threading.Thread | None = None
        self._stop_reader = threading.Event()
        # Buffer holds last valid readings
        self._buffer = {
            "accel": (0.0, 0.0, 0.0),
            "gyro": (0.0, 0.0, 0.0),
            "mag": (0.0, 0.0, 0.0),
            "quat": (0.0, 0.0, 0.0, 0.0),
            "calib": (0, 0, 0, 0),  # sys, gyro, accel, mag
        }
        self._lock = threading.Lock()

    def start(self):
        """Start sensor process and reader thread."""
        if not (self._process and self._process.is_alive()):
            self._process = Process(
                target=_sensor_proc, args=(self._queue, self.update_rate), daemon=True
            )
            self._process.start()
            # Wait briefly for error or first data
            try:
                msg = self._queue.get(timeout=2.0)
                if isinstance(msg, dict) and "error" in msg:
                    self._imu_available = False
                    self._imu_error_msg = msg["error"]
                    self.log.error(f"IMU unavailable: {self._imu_error_msg}")
                    return
                else:
                    # Put back the first data for the reader thread
                    self._queue.put_nowait(msg)
                    self._imu_available = True
            except queue.Empty:
                self._imu_available = False
                self._imu_error_msg = "IMU did not respond in time"
                self.log.error("IMU did not respond in time")
                return
            self.log.info("IMU process started")


        if not (self._reader_thread and self._reader_thread.is_alive()):
            self._stop_reader.clear()
            self._reader_thread = threading.Thread(
                target=self._reader_loop, daemon=True
            )
            self._reader_thread.start()

    def stop(self):
        """Stop sensor process and reader thread."""
        if self._process:
            self._process.terminate()
            self._process.join()
            self._process = None

        if self._reader_thread:
            self._stop_reader.set()
            self._reader_thread.join()
            self._reader_thread = None

    def _reader_loop(self):
        """Continuously drain queue; update buffer only with fully valid readings."""
        while not self._stop_reader.is_set():
            try:
                accel, gyro, mag, quat, calib = self._queue.get(timeout=0.1)
                with self._lock:
                    if accel is not None and all(v is not None for v in accel):
                        self._buffer["accel"] = accel
                    if gyro is not None and all(v is not None for v in gyro):
                        self._buffer["gyro"] = gyro
                    if mag is not None and all(v is not None for v in mag):
                        self._buffer["mag"] = mag
                    if quat is not None and all(v is not None for v in quat):
                        self._buffer["quat"] = quat
                    if calib is not None and all(v is not None for v in calib):
                        self._buffer["calib"] = calib
            except queue.Empty:
                continue
            except Exception:
                self.log.error("Error in reader thread")

    def get_values(self):
        """Get latest accel, gyro, mag."""
        if not self._imu_available:
            raise IMUNotAvailableError(self._imu_error_msg or "IMU not available")
        with self._lock:
            return (
                self._buffer["accel"],
                self._buffer["gyro"],
                self._buffer["mag"],
            )

    def get_latest_values(self):
        """Get latest accel, gyro, mag."""
        if not self._imu_available:
            raise IMUNotAvailableError(self._imu_error_msg or "IMU not available")
        with self._lock:
            return (
                self._buffer["accel"],
                self._buffer["gyro"],
                self._buffer["mag"],
                self._buffer["quat"],
                self._buffer["calib"],
            )

    def get_quaternion(self):
        """Get latest quaternion."""
        if not self._imu_available:
            raise IMUNotAvailableError(self._imu_error_msg or "IMU not available")
        with self._lock:
            return self._buffer["quat"]

    def get_calibration_status(self):
        """Get latest calibration status tuple (sys, gyro, accel, mag)."""
        if not self._imu_available:
            raise IMUNotAvailableError(self._imu_error_msg or "IMU not available")
        with self._lock:
            return self._buffer["calib"]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    imu = BNO055Manager(update_rate=100)
    imu.start()
    try:
        while True:
            accel, gyro, mag = imu.get_values()
            quat = imu.get_quaternion()
            calib = imu.get_calibration_status()
            print("\033[H\033[J", end="")
            print(f"Accelerometer (m/s^2): {accel}")
            print(f"Gyroscope    (rad/s):   {gyro}")
            print(f"Magnetometer (uT):      {mag}")
            print(f"Quaternion (w,x,y,z):   {quat}")
            print(f"Calibration: (sys,gyro,accel,mag): {calib}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        imu.stop()
