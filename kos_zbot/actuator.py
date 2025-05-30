import threading
import time
from kos_zbot.feetech import *
from typing import Dict, Optional
import os
import sched
import platform
from tabulate import tabulate  # Add this import at the top of the file
from kos_zbot.utils.logging import get_logger
from kos_zbot.utils.metadata import RobotMetadata

# from kos_zbot.utils.latency import get_tracker
from tqdm import tqdm
import gc


class NoActuatorsFoundError(Exception):
    pass


ADDR_KP = 21  # Speed loop P gain
ADDR_KD = 22  # Speed loop D gain


servoRegs = [
    {"name": "Model", "addr": SMS_STS_MODEL_L, "size": 2, "type": "uint16"},
    {"name": "ID", "addr": SMS_STS_ID, "size": 1, "type": "uint8"},
    {"name": "Baudrate", "addr": SMS_STS_BAUD_RATE, "size": 1, "type": "uint8"},
    {"name": "Return Delay", "addr": 7, "size": 1, "type": "uint8"},
    {"name": "Response Status Level", "addr": 8, "size": 1, "type": "uint8"},
    {
        "name": "Min Angle Limit",
        "addr": SMS_STS_MIN_ANGLE_LIMIT_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Max Angle Limit",
        "addr": SMS_STS_MAX_ANGLE_LIMIT_L,
        "size": 2,
        "type": "uint16",
    },
    {"name": "Max Temperature Limit", "addr": 13, "size": 1, "type": "uint8"},
    {"name": "Max Voltage Limit", "addr": 14, "size": 1, "type": "uint8"},
    {"name": "Min Voltage Limit", "addr": 15, "size": 1, "type": "uint8"},
    {"name": "Max Torque Limit", "addr": 16, "size": 2, "type": "uint16"},
    {"name": "Phase", "addr": 18, "size": 1, "type": "uint8"},
    {"name": "Unloading Condition", "addr": 19, "size": 1, "type": "uint8"},
    {"name": "LED Alarm Condition", "addr": 20, "size": 1, "type": "uint8"},
    {"name": "P Coefficient", "addr": 21, "size": 1, "type": "uint8"},
    {"name": "D Coefficient", "addr": 22, "size": 1, "type": "uint8"},
    {"name": "I Coefficient", "addr": 23, "size": 1, "type": "uint8"},
    {"name": "Minimum Startup Force", "addr": 24, "size": 2, "type": "uint16"},
    {"name": "CW Dead Zone", "addr": SMS_STS_CW_DEAD, "size": 1, "type": "uint8"},
    {"name": "CCW Dead Zone", "addr": SMS_STS_CCW_DEAD, "size": 1, "type": "uint8"},
    {"name": "Protection Current", "addr": 28, "size": 2, "type": "uint16"},
    {"name": "Angular Resolution", "addr": 30, "size": 1, "type": "uint8"},
    {"name": "Offset", "addr": SMS_STS_OFS_L, "size": 2, "type": "uint16"},
    {"name": "Mode", "addr": SMS_STS_MODE, "size": 1, "type": "uint8"},
    {"name": "Protective Torque", "addr": 34, "size": 1, "type": "uint8"},
    {"name": "Protection Time", "addr": 35, "size": 1, "type": "uint8"},
    {"name": "Overload Torque", "addr": 36, "size": 1, "type": "uint8"},
    {
        "name": "Speed closed loop P proportional coefficient",
        "addr": 37,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Over Current Protection Time", "addr": 38, "size": 1, "type": "uint8"},
    {
        "name": "Velocity closed loop I integral coefficient",
        "addr": 39,
        "size": 1,
        "type": "uint8",
    },
    {
        "name": "Torque Enable",
        "addr": SMS_STS_TORQUE_ENABLE,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Acceleration", "addr": SMS_STS_ACC, "size": 1, "type": "uint8"},
    {
        "name": "Goal Position",
        "addr": SMS_STS_GOAL_POSITION_L,
        "size": 2,
        "type": "uint16",
    },
    {"name": "Goal Time", "addr": SMS_STS_GOAL_TIME_L, "size": 2, "type": "uint16"},
    {"name": "Goal Speed", "addr": SMS_STS_GOAL_SPEED_L, "size": 2, "type": "int16"},
    {"name": "Lock", "addr": SMS_STS_LOCK, "size": 1, "type": "uint8"},
    {
        "name": "Present Position",
        "addr": SMS_STS_PRESENT_POSITION_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Present Speed",
        "addr": SMS_STS_PRESENT_SPEED_L,
        "size": 2,
        "type": "int16",
    },
    {
        "name": "Present Load",
        "addr": SMS_STS_PRESENT_LOAD_L,
        "size": 2,
        "type": "int16",
    },
    {
        "name": "Present Voltage",
        "addr": SMS_STS_PRESENT_VOLTAGE,
        "size": 1,
        "type": "uint8",
    },
    {
        "name": "Present Temperature",
        "addr": SMS_STS_PRESENT_TEMPERATURE,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Status", "addr": 65, "size": 1, "type": "uint8"},
    {"name": "Moving", "addr": SMS_STS_MOVING, "size": 1, "type": "uint8"},
    {
        "name": "Present Current",
        "addr": SMS_STS_PRESENT_CURRENT_L,
        "size": 2,
        "type": "uint16",
    },
    {
        "name": "Default Moving Threshold",
        "addr": SMS_STS_DEFAULT_MOVING_THRESHOLD,
        "size": 1,
        "type": "uint8",
    },
    {"name": "Default DTS", "addr": SMS_STS_DEFAULT_DTS_MS, "size": 1, "type": "uint8"},
    {"name": "Default VK", "addr": SMS_STS_DEFAULT_VK_MS, "size": 1, "type": "uint8"},
    {"name": "Default VMIN", "addr": SMS_STS_DEFAULT_VMIN, "size": 1, "type": "uint8"},
    {"name": "Default VMAX", "addr": SMS_STS_DEFAULT_VMAX, "size": 1, "type": "uint8"},
    {"name": "Default AMAX", "addr": SMS_STS_DEFAULT_AMAX, "size": 1, "type": "uint8"},
    {"name": "Default KACC", "addr": SMS_STS_DEFAULT_KACC, "size": 1, "type": "uint8"},
]


class SCSMotorController:
    def __init__(
        self, device="/dev/ttyAMA5", baudrate=500000, rate=50, actuator_ids=None, robot_metadata=None
    ):
        """Initialize the motor controller with minimal setup"""

        self.log = get_logger(__name__)
        self.rate = rate
        self.period = 1.0 / rate
        self.scheduler = sched.scheduler(time.time, time.sleep)

        self.last_config_time = 0
        self.CONFIG_GRACE_PERIOD = 2.0  # Wait 1 second after configs

        self.torque_enabled_ids = set()
        self.commanded_ids: Set[int] = set()

        self.actuator_ids = (
            set()
        )  # Use set instead of list for efficient membership testing
        self.last_commanded_positions = {}
        self.next_position_batch = None  # Atomic batch update
        self.last_commanded_velocities = {}
        self.next_velocity_batch = None

        self.port_handler = PortHandler(device)
        self.packet_handler = sms_sts(self.port_handler)

        self.port_handler.setBaudRate(baudrate)
        if not self.port_handler.openPort():
            raise RuntimeError("failed to open the port")
        self.log.info(f"port opened at {self.port_handler.getBaudRate()} baud")

        self.group_sync_read = GroupSyncRead(
            self.packet_handler, SMS_STS_PRESENT_POSITION_L, 4
        )
        self.group_sync_write = GroupSyncWrite(
            self.packet_handler, SMS_STS_GOAL_POSITION_L, 2
        )

        # State variables
        self.running = False

        # Double buffer for positions
        self._positions_a = {}
        self._positions_b = {}
        self._active_positions = self._positions_a
        self._velocities_a = {}
        self._velocities_b = {}
        self._active_velocities = self._velocities_a

        # Locks
        self._control_lock = threading.Lock()
        self._positions_lock = threading.Lock()
        self._target_positions_lock = threading.Lock()

        self.read_error_counts = {}  # Track read errors per servo
        self.error_reset_period = 5.0  # Reset error counts after 5 seconds of success
        self.last_error_time = {}  # Track when error count was last incremented
        self.fault_history = {}  # Track fault history

        self._max_servo_cnt = 20  # worst‑case number of IDs you’ll ever have
        self._tx_buf = bytearray(
            self._max_servo_cnt * 7
        )  # id, pos_lo, pos_hi, time_lo, time_hi, vel_lo, vel_hi
        self._last_sent_pos = {}  # id → counts  (keeps GC stable)

        # self.latency_tracker = get_tracker("actuator_loop")
        time.sleep(1)

        available_actuators = self.scan_servos(range(0, 254))
        self.log.info(f"{len(available_actuators)} actuators found")

        if not available_actuators:
            self.log.error("no actuators found")
            raise NoActuatorsFoundError("no actuators found")

        self.metadata = robot_metadata
        self.actuator_limits = {}
        self.actuator_gains= {}
        # Set default gains for all discovered actuators
        for actuator in available_actuators:
            actuator_id = actuator["id"]
            self.actuator_gains[actuator_id] = {
                'kp': 22,
                'kd': 2,
                'joint_name': f'actuator_{actuator_id}'  # fallback name
            }
            
        if self.metadata is not None:
            # Check for metadata/hardware mismatches before applying settings
            metadata_actuator_ids = set()
            for joint_name, joint_metadata in self.metadata.joint_name_to_metadata.items():
                if joint_metadata.id is not None:
                    metadata_actuator_ids.add(joint_metadata.id)
            
            discovered_actuator_ids = {actuator["id"] for actuator in available_actuators}
            
            # Check for actuators in metadata but not found on bus
            missing_actuators = metadata_actuator_ids - discovered_actuator_ids
            if missing_actuators:
                missing_list = sorted(missing_actuators)
                self.log.error(f"Robot metadata specifies actuator IDs {missing_list} but they were not found on the bus")
                self.log.error(f"Found actuators: {sorted(discovered_actuator_ids)}")
                self.log.error("Please check your hardware connections or update your robot metadata")
                raise NoActuatorsFoundError(f"Metadata/hardware mismatch: actuators {missing_list} not found on bus")
            
            # Check for extra actuators on bus not in metadata (warning only)
            extra_actuators = discovered_actuator_ids - metadata_actuator_ids
            if extra_actuators:
                extra_list = sorted(extra_actuators)
                self.log.warning(f"Found actuators {extra_list} on bus but they are not in robot metadata")
            
            # Now safely apply metadata settings
            for joint_name, joint_metadata in self.metadata.joint_name_to_metadata.items():
                actuator_id = joint_metadata.id
                if actuator_id is not None and actuator_id in self.actuator_gains:
                    self.actuator_limits[actuator_id] = {
                        'min_angle_deg': float(joint_metadata.min_angle_deg) if joint_metadata.min_angle_deg is not None else None,
                        'max_angle_deg': float(joint_metadata.max_angle_deg) if joint_metadata.max_angle_deg is not None else None,
                        'joint_name': joint_name
                    }
                    if joint_metadata.kp is not None:
                        self.actuator_gains[actuator_id]['kp'] = float(joint_metadata.kp)
                    if joint_metadata.kd is not None:
                        self.actuator_gains[actuator_id]['kd'] = float(joint_metadata.kd)
                    # Update joint name from metadata
                    self.actuator_gains[actuator_id]['joint_name'] = joint_name

            self.log.info(f"Loaded angle limits for {len(self.actuator_limits)} actuators")
            self.log.info(f"Loaded gains for {len(self.actuator_gains)} actuators")
        else:
            self.log.warning("No robot metadata available. Running without limit enforcement.")

        with self._control_lock:
            for actuator in available_actuators:
                self._add_actuator(actuator["id"])

        self._apply_default_gains()

        # Initialize thread
        self.thread = threading.Thread(target=self._update_loop, daemon=True)

    def _apply_default_gains(self, actuator_id: int = None) -> bool:
        """Apply default/metadata gains to specific actuator or all actuators"""
        if actuator_id is not None:
            # Apply to specific actuator
            if actuator_id not in self.actuator_gains:
                self.log.warning(f"No gains configured for actuator {actuator_id}")
                return False
                
            gains = self.actuator_gains[actuator_id]
            config = {
                'kp': gains['kp'],
                'kd': gains['kd'],
                'torque_enabled': True,
                'acceleration': 1000
            }
            return self.configure_actuator(actuator_id, config)
        else:
            # Apply to all actuators
            success = True
            for aid in self.actuator_ids:
                if not self._apply_default_gains(aid):
                    success = False
            return success

    def _add_actuator(self, actuator_id: int) -> bool:
        """Add a new actuator to the controller"""
        if actuator_id in self.actuator_ids:
            return True

        if not self.group_sync_read.addParam(actuator_id):
            self.log.error(f"[id:{actuator_id:03d}] groupsyncread addparam failed")
            return False

        # Initialize position tracking
        self.actuator_ids.add(actuator_id)
        self.last_commanded_positions[actuator_id] = 0
        self.last_commanded_velocities[actuator_id] = 0

        # Double-buffered positions: initialize both buffers
        self._positions_a[actuator_id] = 0
        self._positions_b[actuator_id] = 0
        return True

    def _remove_actuator(
        self, actuator_id: int
    ):  # TODO: It's not clear that we really need this
        """Remove an actuator from the controller"""
        if actuator_id in self.actuator_ids:
            self.torque_enabled_ids.discard(actuator_id)
            self.commanded_ids.discard(actuator_id)
            self.actuator_ids.remove(actuator_id)
            self.last_commanded_positions.pop(actuator_id, None)

            # Double-buffered positions: cleanup both buffers
            self._positions_a.pop(actuator_id, None)
            self._positions_b.pop(actuator_id, None)

            # Cleanup error tracking
            self.read_error_counts.pop(actuator_id, None)
            self.last_error_time.pop(actuator_id, None)

    def _record_fault(self, actuator_id: int, message: str):
        """Record a fault for the given actuator."""
        now = time.time()
        if actuator_id not in self.fault_history:
            self.fault_history[actuator_id] = {
                "last_fault_message": message,
                "total_faults": 1,
                "last_fault_time": now,
            }
        else:
            fh = self.fault_history[actuator_id]
            fh["last_fault_message"] = message
            fh["total_faults"] += 1
            fh["last_fault_time"] = now

    def get_faults(self, actuator_id: int):
        """Retrieve fault history for a given actuator."""
        return self.fault_history.get(actuator_id)

    def get_limits(self, actuator_id: int) -> Optional[dict]:
        """Get current min/max position limits for a specific actuator"""
        if actuator_id not in self.actuator_ids:
            return None
        
        # Get limits from metadata if available
        if actuator_id in self.actuator_limits:
            limits = self.actuator_limits[actuator_id]
            return {
                "min_position": limits['min_angle_deg'],
                "max_position": limits['max_angle_deg']
            }
        
        return None

    def configure_actuator(self, actuator_id: int, config: dict):
        """Configure actuator parameters. Only parameters present in config are written."""
        try:
            self.last_config_time = time.monotonic()
            changes = []

            with self._control_lock:
                time.sleep(0.002)

                # Only configure if actuator is already registered
                if actuator_id not in self.actuator_ids:
                    self.log.error(
                        f"cannot configure unregistered actuator {actuator_id}"
                    )
                    return False

                success = True

                # KP
                if "kp" in config:
                    kp = int(config["kp"])
                    if not (0 <= kp <= 255):
                        self.log.error(f"kp out of range: {kp}")
                        return False
                    success &= self.writeReg_Verify(actuator_id, ADDR_KP, kp)
                    changes.append(f"kp={kp}")

                # KD
                if "kd" in config:
                    kd = int(config["kd"])
                    if not (0 <= kd <= 255):
                        self.log.error(f"kd out of range: {kd}")
                        return False
                    success &= self.writeReg_Verify(actuator_id, ADDR_KD, kd)
                    changes.append(f"kd={kd}")

                # Acceleration
                if "acceleration" in config:
                    acceleration = config["acceleration"]
                    # Convert if needed
                    if acceleration != 0:
                        acceleration = (
                            self._degrees_to_counts(acceleration, offset=0.0) / 100.0
                        )
                    acceleration = int(acceleration)
                    if not (0 <= acceleration <= 255):
                        self.log.error(f"acceleration out of range: {acceleration}")
                        return False
                    success &= self.writeReg_Verify(
                        actuator_id, SMS_STS_ACC, acceleration
                    )
                    changes.append(f"acc={acceleration}")

                # Torque enable
                if "torque_enabled" in config:
                    torque_enabled = bool(config["torque_enabled"])
                    was_enabled = actuator_id in self.torque_enabled_ids
                    success &= self.writeReg_Verify(
                        actuator_id, SMS_STS_TORQUE_ENABLE, 1 if torque_enabled else 0
                    )
                    if torque_enabled:
                        if not was_enabled:
                            # Read current position and set as target to prevent jump
                            with self._positions_lock:
                                positions = self._active_positions
                                current_counts = positions.get(actuator_id)
                            self.last_commanded_positions[actuator_id] = current_counts
                        self.torque_enabled_ids.add(actuator_id)
                    else:
                        self.torque_enabled_ids.discard(actuator_id)
                    changes.append(f"torque={'on' if torque_enabled else 'off'}")

                # Zero position
                if config.get("zero_position", False):
                    self.set_zero_position(actuator_id)
                    changes.append("zeroed")

            if success:
                self.log.info(
                    f"actuator {actuator_id} configured: " + ", ".join(changes)
                )
            else:
                self.log.error(
                    f"actuator {actuator_id} configuration failed: "
                    + ", ".join(changes)
                )
            return success

        except Exception as e:
            self.log.error(f"error configuring actuator {actuator_id}: {str(e)}")
            return False

    # TODO: Make this comprehensive and put into use
    async def _verify_config(self, actuator_id: int, config: dict):
        """Verify that configuration was applied correctly."""
        try:
            if "acceleration" in config:
                # Read back acceleration value
                actual_acc = packet_handler.read1ByteTxRx(actuator_id, SMS_STS_ACC)
                if actual_acc != config["acceleration"]:
                    self.log.error(
                        f"acceleration mismatch: expected {config['acceleration']}, got {actual_acc}"
                    )
                    return False

            # Add other configuration verifications here
            return True

        except Exception as e:
            self.log.error(f"verification error: {str(e)}")
            return False

    def start(self):
        """Start the motor controller update loop with real-time priority"""
        self.running = True

        # Set real-time priority if possible
        if platform.system() == "Linux":
            try:
                os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(99))
            except PermissionError:
                self.log.warning("could not set real-time priority")
        self.thread.start()

    def stop(self):
        """Stop the motor controller update loop"""
        self.running = False
        if self.thread.is_alive():
            self.thread.join()
        self.port_handler.closePort()

    def _update_loop(self):
        """
        Main update loop running at `self.rate` Hz with a sleep‑then‑spin scheduler.
        Uses a single monotonic‑ns timeline so one overrun never skews the cadence.
        """
        PERIOD_NS = int(self.period * 1e9)  # e.g. 20 000 000 ns
        SPIN_US = 100  # busy‑wait window (µs) – tune on your CPU
        SPIN_NS = SPIN_US * 1_000

        # self.latency_tracker.set_period(PERIOD_NS)

        # pin to core 1
        os.sched_setaffinity(0, {1})
        allowed = os.sched_getaffinity(0)
        self.log.info(f"feetech _update_loop running on CPUs: {sorted(allowed)}")
        gc.set_threshold(
            700, 10, 5
        )  # Increase the gen-2 frequency to mitigate pileup ? TODO: investigate

        init_time = time.monotonic_ns()
        while self.running:
            # self.latency_tracker.record_iteration()
            now_ns = time.monotonic_ns()

            if now_ns - init_time < 1_000_000_000:  # Wait 1 second after init
                self._read_states(ignore_errors=True)
                time.sleep(0.01)
                next_time = time.monotonic_ns()
                continue

            # ── CONFIG‑GRACE CHECK ──────────────────────────────
            in_grace = (now_ns - self.last_config_time * 1e9) < (
                self.CONFIG_GRACE_PERIOD * 1e9
            )

            if not in_grace and self._control_lock.acquire(blocking=False):
                try:
                    if self.actuator_ids:
                        self._write_commands()
                        time.sleep(0.002)
                        self._read_states()
                except Exception as e:
                    self.log.error(f"error in update loop: {e}")
                finally:
                    self._control_lock.release()
            elif not self._control_lock.locked():
                self._read_states(ignore_errors=True)
            
            # else:
            #    self.latency_tracker.reset()

            # -- Schedule Next Tick --
            next_time += PERIOD_NS
            now_ns = time.monotonic_ns()  # refresh after work
            sleep_ns = next_time - now_ns - SPIN_NS  # leave SPIN_NS to spin

            if sleep_ns > 0:
                # coarse sleep (GIL released)
                time.sleep(sleep_ns / 1e9)

            # fine spin – last ≤ SPIN_US
            while time.monotonic_ns() < next_time:
                pass  # CPU‑bound for ≤ 100 µs

            over_ns = time.monotonic_ns() - next_time
            if over_ns > 0:
                next_time = time.monotonic_ns()

            if not in_grace:
                over_us = over_ns / 1_000  # ns → µs
                if over_us > 5_000:
                    self.log.error(f"hard overrun {over_us/1000:.2f} ms")
                elif over_us > 2_000:
                    self.log.warning(f"overrun      {over_us/1000:.2f} ms")
                elif over_us > 500:
                    self.log.debug(f"minor jitter {over_us/1000:.2f} ms")

    def _get_params(self, actuator_id: int) -> dict:
        """Read current KP, KD, and acceleration parameters from a servo

        Args:
            actuator_id: ID of the servo to read from

        Returns:
            Dictionary containing the current parameters, or None if read fails
        """
        try:
            # Read KP
            kp_result, kp_error, kp = self.packet_handler.read1ByteTxRx(
                actuator_id, ADDR_KP
            )
            if kp_result != 0:
                self.log.error(f"failed to read kp from actuator {actuator_id}")
                return None

            # Read KD
            kd_result, kd_error, kd = self.packet_handler.read1ByteTxRx(
                actuator_id, ADDR_KD
            )
            if kd_result != 0:
                self.log.error(f"failed to read kd from actuator {actuator_id}")
                return None

            # Read Acceleration
            acc_result, acc_error, acc = self.packet_handler.read1ByteTxRx(
                actuator_id, SMS_STS_ACC
            )
            if acc_result != 0:
                self.log.error(f"failed to read acc from actuator {actuator_id}")
                return None

            # Read torque enable state
            torque_result, torque_error, torque = self.packet_handler.read1ByteTxRx(
                actuator_id, SMS_STS_TORQUE_ENABLE
            )
            if torque_result != 0:
                self.log.error(
                    f"failed to read torque enable from actuator {actuator_id}"
                )
                return None

            params = {
                "kp": kp,
                "kd": kd,
                "acceleration": acc * 100,  # Convert back to percentage
                "torque_enabled": bool(torque),
            }
            self.log.info(
                f"actuator {actuator_id} parameters: kp: {params['kp']}, kd: {params['kd']}, acceleration: {params['acceleration']}%, torque enabled: {params['torque_enabled']}"
            )

            return params

        except Exception as e:
            self.log.error(
                f"error reading parameters from actuator {actuator_id}: {str(e)}"
            )
            return None

    def get_all_params(self):
        """Read and display parameters for all configured actuators"""
        self.log.info("reading parameters for all actuators")
        for actuator_id in sorted(self.actuator_ids):
            self._get_params(actuator_id)

    def _read_states(self, ignore_errors: bool = False):
        """Read current positions and velocities from all servos"""
        current_time = time.monotonic()
        new_positions = {}
        new_velocities = {}

        # Attempt group sync read
        scs_comm_result = self.group_sync_read.txRxPacket()
        if scs_comm_result != 0:
            if not ignore_errors:
                self.log.error(
                    f"GroupSyncRead: {self.packet_handler.getTxRxResult(scs_comm_result)}"
                )
                for actuator_id in list(self.actuator_ids):
                    self._record_fault(
                        actuator_id,
                        f"{self.packet_handler.getTxRxResult(scs_comm_result)}",
                    )
            return

        # If group sync read succeeded, check individual servos
        for actuator_id in list(self.actuator_ids):  # Create copy to allow modification
            data_result, error = self.group_sync_read.isAvailable(
                actuator_id, SMS_STS_PRESENT_POSITION_L, 4
            )
            if data_result:
                if error == 0:
                    data = self.group_sync_read.getData(
                        actuator_id, SMS_STS_PRESENT_POSITION_L, 4
                    )
                    position = self.packet_handler.scs_tohost(data & 0xFFFF, 15)
                    velocity = self.packet_handler.scs_tohost((data >> 16) & 0xFFFF, 15)
                    new_positions[actuator_id] = position
                    new_velocities[actuator_id] = velocity
                else:
                    # Data received, but servo reported an error
                    self._record_fault(actuator_id, f"servo error code: {error}")
                    self.log.error(
                        f"Servo {actuator_id} responded with error code: {error:#04x}"
                    )
            else:
                # No data received for this actuator
                self.read_error_counts[actuator_id] = (
                    self.read_error_counts.get(actuator_id, 0) + 1
                )
                self.last_error_time[actuator_id] = current_time
                self._record_fault(actuator_id, "no data received")
                self.log.error(
                    f"No data received from actuator {actuator_id} (error count: {self.read_error_counts[actuator_id]})"
                )

            # Write to the inactive buffer
            inactive_positions = (
                self._positions_b
                if self._active_positions is self._positions_a
                else self._positions_a
            )
            inactive_velocities = (
                self._velocities_b
                if self._active_velocities is self._velocities_a
                else self._velocities_a
            )
            inactive_positions.clear()
            inactive_positions.update(new_positions)
            inactive_velocities.clear()
            inactive_velocities.update(new_velocities)

            # Swap the active buffer
            with self._positions_lock:
                self._active_positions = inactive_positions
                self._active_velocities = inactive_velocities

    def _write_commands(self):
        """
        Allocation‑free Sync‑WRITE.
        • Builds the payload in a pre‑allocated bytearray (`self._tx_buf`)
        • Sends a packet only if at least one position changed since the last TX
        """
        if not self.torque_enabled_ids:
            return

        # 1) Merge any newly queued target batch -------------------------------
        with self._target_positions_lock:
            if self.next_position_batch is not None:
                self.last_commanded_positions.update(self.next_position_batch)
                self.last_commanded_velocities.update(self.next_velocity_batch)
                self.next_position_batch = None
                self.next_velocity_batch = None

        write_ids = self.torque_enabled_ids & self.commanded_ids
        if not write_ids:
            return

        # 2) Serialise {id → counts} into the shared bytearray -----------------
        buf_idx = 0
        changed = False
        for aid in sorted(write_ids):
            counts = self.last_commanded_positions.get(aid)
            velocity = self.last_commanded_velocities.get(aid, 0)
            if counts is None:
                continue

            # Detect duplicates so we can skip an unnecessary bus packet
            if self._last_sent_pos.get(aid) != counts:
                changed = True
                self._last_sent_pos[aid] = counts

            # Position (2 bytes)
            self._tx_buf[buf_idx] = aid
            self._tx_buf[buf_idx + 1] = counts & 0xFF
            self._tx_buf[buf_idx + 2] = (counts >> 8) & 0xFF

            # Time (2 bytes) - dummy value of 0
            self._tx_buf[buf_idx + 3] = 0
            self._tx_buf[buf_idx + 4] = 0

            # Velocity (2 bytes)
            self._tx_buf[buf_idx + 5] = velocity & 0xFF
            self._tx_buf[buf_idx + 6] = (velocity >> 8) & 0xFF

            buf_idx += 7

        if not changed:
            return  # nothing new → no TX

        # 3) Fire a Sync‑WRITE with *zero* extra allocations -------------------
        #    param_length == number_of_bytes we’re sending (buf_idx)
        self.packet_handler.syncWriteTxOnly(
            SMS_STS_GOAL_POSITION_L,  # start address
            6,  # bytes per servo (2 for position, 2 for time, 2 for velocity)
            memoryview(self._tx_buf)[:buf_idx],
            buf_idx,  # param_length
        )

    def _counts_to_degrees(self, counts: float, offset: float = 180.0) -> float:
        """Convert raw counts to degrees with optional offset"""
        return (counts * 360 / 4096) - offset

    def _degrees_to_counts(self, degrees: float, offset: float = 180.0) -> int:
        """Convert degrees to raw counts with optional offset"""
        return int((degrees + offset) * (4096 / 360))

    def set_targets(self, target_dict: Dict[int, Dict[str, float]]):
        """Set target positions and velocities for multiple actuators atomically.
        Args:
        target_dict: Dictionary mapping actuator IDs to dictionaries containing:
            - 'position': Target position in degrees
            - 'velocity': Target velocity in degrees/second
        """
        with self._target_positions_lock:
            if self.next_position_batch is None:
                self.next_position_batch = {}
                self.next_velocity_batch = {}

            for actuator_id, targets in target_dict.items():
                position = targets["position"]

                # Apply angle limits if available for this actuator
                if actuator_id in self.actuator_limits:
                    limits = self.actuator_limits[actuator_id]
                    original_position = position
                    
                    if limits['min_angle_deg'] is not None and position < limits['min_angle_deg']:
                        position = limits['min_angle_deg']
                        self.log.warn(f"Clipped position for actuator {actuator_id} ({limits['joint_name']}) from {original_position:.2f}° to {position:.2f}° (min limit)")
                    
                    if limits['max_angle_deg'] is not None and position > limits['max_angle_deg']:
                        position = limits['max_angle_deg']
                        self.log.warn(f"Clipped position for actuator {actuator_id} ({limits['joint_name']}) from {original_position:.2f}° to {position:.2f}° (max limit)")

                self.next_position_batch[actuator_id] = self._degrees_to_counts(position, offset=180.0)
                self.next_velocity_batch[actuator_id] = self._degrees_to_counts(targets["velocity"], offset=0.0)
                self.commanded_ids.add(actuator_id)

    def get_position(self, actuator_id: int) -> Optional[float]:
        """Get current position of a specific actuator"""
        with self._positions_lock:
            positions = self._active_positions
        value = positions.get(actuator_id)
        return (
            self._counts_to_degrees(value, offset=180.0) if value is not None else None
        )

    def get_velocity(self, actuator_id: int) -> Optional[float]:
        """Get current velocity of a specific actuator"""
        with self._positions_lock:
            velocities = self._active_velocities
        value = velocities.get(actuator_id)
        return self._counts_to_degrees(value, offset=0.0) if value is not None else None

    def get_state(self, actuator_id: int) -> Optional[dict]:
        """Get current position and velocity of a specific actuator"""
        with self._positions_lock:
            positions = self._active_positions
            velocities = self._active_velocities
        pos = positions.get(actuator_id)
        vel = velocities.get(actuator_id)
        if pos is None or vel is None:
            return None
        return {
            "position": self._counts_to_degrees(pos, offset=180.0),
            "velocity": self._counts_to_degrees(vel, offset=0.0),
        }

    def get_torque_enabled(self, actuator_id: int) -> bool:
        return actuator_id in self.torque_enabled_ids

    def _unlockEEPROM(self, actuator_id):
        self.packet_handler.unLockEprom(actuator_id)
        self.log.debug("eeprom unlocked")

    def _lockEEPROM(self, actuator_id):
        self.packet_handler.LockEprom(actuator_id)
        self.log.debug("eeprom locked")

    def writeReg_Verify(self, actuator_id, regAddr, value):
        """Write to a register with retries. Returns True if successful, False otherwise."""
        reg = None
        for r in servoRegs:
            if r["addr"] == regAddr:
                reg = r
                break

        if reg == None:
            self.log.error("unknown register: " + str(regAddr))
            return False  # Return False instead of None

        if reg["size"] == 2:
            value = [
                self.packet_handler.scs_lobyte(value),
                self.packet_handler.scs_hibyte(value),
            ]
        else:
            value = [value]

        retries = 3
        while retries > 0:
            comm_result, error = self.packet_handler.writeTxRx(
                actuator_id, regAddr, reg["size"], value
            )
            if comm_result == 0:
                # print(f"Register {regAddr} written")
                return True
            else:
                self.log.error(
                    f"Write to ID: {actuator_id} Register: {regAddr} - {self.packet_handler.getTxRxResult(comm_result)} - retrying {retries} times: "
                )
                retries -= 1

        # self.log.error(f"failed to write register {regAddr} after all retries")
        return False  # Return False after all retries fail

    def writeReg(self, actuator_id, regAddr, value):
        """Write to a register with retries. Returns True if successful, False otherwise."""
        reg = None
        for r in servoRegs:
            if r["addr"] == regAddr:
                reg = r
                break

        if reg == None:
            self.log.error("unknown register: " + str(regAddr))
            return False

        if reg["size"] == 2:
            value = [
                self.packet_handler.scs_lobyte(value),
                self.packet_handler.scs_hibyte(value),
            ]
        else:
            value = [value]

        comm_result = self.packet_handler.writeTxOnly(
            actuator_id, regAddr, reg["size"], value
        )
        if comm_result == 0:
            return True

        self.log.error(
            f"Write to ID: {actuator_id} Register: {regAddr} - {self.packet_handler.getTxRxResult(comm_result)}"
        )
        return False

    def _get_model_name(self, model_number):
        """Translate model number to human-readable name"""
        model_map = {777: "STS3215", 2825: "STS3250"}  # 0x0309  # 0x0B09
        return model_map.get(model_number, f"Unknown Model {model_number}")

    def read_all_servo_params(self, actuator_id: int):
        """Read and display all relevant parameters for a servo"""
        try:
            with self._control_lock:
                params = {}
                for reg in servoRegs:
                    try:
                        value, comm_result, error = self.packet_handler.readTxRx(
                            actuator_id, reg["addr"], reg["size"]
                        )

                        if comm_result == COMM_SUCCESS:
                            if reg["size"] == 2:
                                value = self.packet_handler.scs_tohost(
                                    self.packet_handler.scs_makeword(
                                        value[0], value[1]
                                    ),
                                    15,
                                )
                            else:
                                value = value[0]

                            # Special handling for Model - store the name instead of the number
                            if reg["name"] == "Model":
                                value = self._get_model_name(value)

                            params[reg["name"]] = {"value": value, "addr": reg["addr"]}
                        else:
                            self.log.error(
                                f"Read ID: {actuator_id} Register: {reg['addr']} - {self.packet_handler.getTxRxResult(comm_result)}"
                            )

                    except Exception as e:
                        self.log.error(
                            f"error reading {reg['name']} (addr: {reg['addr']}): {str(e)}"
                        )
                        continue
                return params

        except Exception as e:
            self.log.error(
                f"error reading parameters from actuator {actuator_id}: {str(e)}"
            )
            return None

    def compare_actuator_params(self, actuator_ids=None, params_to_compare=None):
        """Compare specific parameters across multiple actuators and show differences."""
        # Use all servoRegs by default, creating display names with register addresses
        default_params = [reg["name"] for reg in servoRegs]

        params_to_compare = params_to_compare or default_params
        actuator_ids = sorted(actuator_ids or self.actuator_ids)

        if len(actuator_ids) < 2:
            print("need at least 2 actuators to compare")
            return

        # Read all parameters for specified actuators
        actuator_params = {}
        for aid in actuator_ids:
            actuator_params[aid] = self.read_all_servo_params(aid)
            time.sleep(0.1)

        # Create a mapping of parameter names to their register addresses
        reg_addresses = {reg["name"]: reg["addr"] for reg in servoRegs}

        # Prepare table data
        headers = ["Parameter [Reg]"] + [f"ID {aid}" for aid in actuator_ids]
        table_data = []
        differences_found = False

        for param in params_to_compare:
            # Create parameter name with register address
            param_with_reg = f"{param} [{reg_addresses[param]}]"
            row = [param_with_reg]
            base_value = None
            row_has_diff = False

            # Collect values for this parameter
            for aid in actuator_ids:
                if actuator_params[aid] and param in actuator_params[aid]:
                    value = actuator_params[aid][param]
                    value_str = str(value)

                    if base_value is None:
                        base_value = value
                        base_value_str = value_str
                    elif value != base_value:
                        row_has_diff = True
                    row.append(value_str)
                else:
                    row.append("N/A")
                    row_has_diff = True

            if row_has_diff:
                differences_found = True
                row = [row[0]] + [
                    f"\033[91m{v}\033[0m" if v != base_value_str else v for v in row[1:]
                ]
            table_data.append(row)

        print("\n=== Parameter Comparison ===")
        print(f"Comparing actuators: {actuator_ids}")
        print(
            tabulate(
                table_data,
                headers=headers,
                tablefmt="grid",
                numalign="right",
                stralign="left",
            )
        )

        if not differences_found:
            print("\nAll compared parameters are identical across actuators.")

        return actuator_params

    def set_zero_position(self, actuator_id: int):
        self._unlockEEPROM(actuator_id)
        time.sleep(0.01)

        # Set min angle to 0
        self.writeReg_Verify(actuator_id, SMS_STS_MIN_ANGLE_LIMIT_L, 0x0000)
        time.sleep(0.01)

        # Set max angle to 4095
        self.writeReg_Verify(actuator_id, SMS_STS_MAX_ANGLE_LIMIT_L, 0x0FFF)
        time.sleep(0.01)

        # Set position control mode
        self.writeReg_Verify(actuator_id, SMS_STS_MODE, 0)
        time.sleep(0.01)

        # Enable torque with special flag
        self.writeReg_Verify(actuator_id, SMS_STS_TORQUE_ENABLE, 0x80)
        time.sleep(0.01)

        self._lockEEPROM(actuator_id)

        # Set the target and buffers to zero
        self.last_commanded_positions[actuator_id] = self._degrees_to_counts(
            0, offset=180.0
        )
        self.last_commanded_velocities[actuator_id] = 0
        self._positions_a[actuator_id] = 0
        self._positions_b[actuator_id] = 0

    def scan_servos(self, id_range: range) -> list:
        found_servos = []
        found_strings = []
        with tqdm(id_range, desc="Scanning servos", unit="ID") as pbar:
            for servo_id in pbar:
                model_number, result, error = self.packet_handler.ping(servo_id)
                if result == 0:
                    model_name = self._get_model_name(model_number)
                    found_servos.append({"id": servo_id, "model": model_name})
                    found_strings.append(f"[{servo_id} {model_name}]")
        if found_strings:
            self.log.info("Found servos: " + ", ".join(found_strings))
        else:
            self.log.info("No servos found.")
        return found_servos

    def change_baudrate(self, raw_baud: int) -> bool:
        """
        Set bus speed by passing the actual baud rate.

        Args:
            raw_baud: one of 1_000_000, 500_000, or 250_000
            verify: if True, read back each servo’s baud‐rate register to confirm
        Returns:
            True if all writes (and host port update) succeeded
        """
        # map actual baud → register index
        baud_to_index = {
            1_000_000: 0,  # index 0 => 1 Mbps
            500_000: 1,  # index 1 => 500 kbps
            250_000: 2,  # index 2 => 250 kbps
        }
        if raw_baud not in baud_to_index:
            self.log.error(f"Unsupported baud rate: {raw_baud}")
            return False

        idx = baud_to_index[raw_baud]
        self.log.info(f"idx: {idx}")
        success = True

        with self._control_lock:
            for aid in sorted(self.actuator_ids):
                self.log.info(f"Changing baudrate for actuator {aid} to {raw_baud}")
                # unlock EEPROM
                self._unlockEEPROM(aid)
                time.sleep(0.01)

                # write index into the baud‐rate register
                if not self.writeReg(aid, SMS_STS_BAUD_RATE, idx):
                    # self.log.error(f"[id:{aid:03d}] failed to write baud index {idx}")
                    success = False

                time.sleep(0.01)
                # lock EEPROM again
                self._lockEEPROM(aid)
                time.sleep(0.01)

        return success

    def change_id(self, current_id: int, new_id: int) -> bool:
        """
        Change the ID of a servo on the bus.

        Args:
            current_id: Current ID of the servo (0-253)
            new_id: New ID to set for the servo (0-253)
        Returns:
            True if the ID change was successful
        """
        if not (0 <= current_id <= 253 and 0 <= new_id <= 253):
            self.log.error("IDs must be between 0 and 253")
            return False

        self.log.info(f"Changing servo ID from {current_id} to {new_id}")
        success = True

        with self._control_lock:
            # unlock EEPROM
            self._unlockEEPROM(current_id)
            time.sleep(0.01)

            # write new ID
            if not self.writeReg_Verify(current_id, SMS_STS_ID, new_id):
                self.log.error(f"Failed to write new ID {new_id} to servo {current_id}")
                success = False

            time.sleep(0.01)
            # lock EEPROM again
            self._lockEEPROM(current_id)
            time.sleep(0.01)

        return success
