import threading
import os
import gc
import sched
import platform
import time
from typing import Dict, Optional

from kos_zbot.feetech import *
from kos_zbot.feetech.servo import ServoInterface
from kos_zbot.utils.logging import get_logger
from kos_zbot.utils.metadata import RobotMetadata


class NoActuatorsFoundError(Exception):
    pass


class ActuatorController:
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
        self.servo = ServoInterface(self.port_handler)

        self.port_handler.setBaudRate(baudrate)
        if not self.port_handler.openPort():
            raise RuntimeError("failed to open the port")
        self.log.info(f"port opened at {self.port_handler.getBaudRate()} baud")

        self.group_sync_read = GroupSyncRead(
            self.servo, SMS_STS_PRESENT_POSITION_L, 4
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

        available_actuators = self.servo.scan_servos(range(0, 254))
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

    

    def zero_position(self, actuator_id: int):
        with self._control_lock:
            self.servo.set_zero_position(actuator_id)

    def change_id(self, actuator_id: int, new_id: int):
        with self._control_lock:
            return self.servo.change_id(actuator_id, new_id)

    def change_baudrate(self, actuator_id: int, new_baudrate: int):
        with self._control_lock:
            return self.servo.change_baudrate(actuator_id, new_baudrate, self.actuator_ids)

    def read_all_servo_params(self, actuator_id: int):
        with self._control_lock:
            return self.servo.read_all_servo_params(actuator_id)

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
                    f"GroupSyncRead: {self.servo.getTxRxResult(scs_comm_result)}"
                )
                for actuator_id in list(self.actuator_ids):
                    self._record_fault(
                        actuator_id,
                        f"{self.servo.getTxRxResult(scs_comm_result)}",
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
                    position = self.servo.scs_tohost(data & 0xFFFF, 15)
                    velocity = self.servo.scs_tohost((data >> 16) & 0xFFFF, 15)
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
        self.servo.syncWriteTxOnly(
            SMS_STS_GOAL_POSITION_L,  # start address
            6,  # bytes per servo (2 for position, 2 for time, 2 for velocity)
            memoryview(self._tx_buf)[:buf_idx],
            buf_idx,  # param_length
        )


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

                self.next_position_batch[actuator_id] = self.servo.degrees_to_counts(position, offset=180.0)
                self.next_velocity_batch[actuator_id] = self.servo.degrees_to_counts(targets["velocity"], offset=0.0)
                self.commanded_ids.add(actuator_id)

    def get_position(self, actuator_id: int) -> Optional[float]:
        """Get current position of a specific actuator"""
        with self._positions_lock:
            positions = self._active_positions
        value = positions.get(actuator_id)
        return (
            self.servo.counts_to_degrees(value, offset=180.0) if value is not None else None
        )

    def get_velocity(self, actuator_id: int) -> Optional[float]:
        """Get current velocity of a specific actuator"""
        with self._positions_lock:
            velocities = self._active_velocities
        value = velocities.get(actuator_id)
        return self.servo.counts_to_degrees(value, offset=0.0) if value is not None else None

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
            "position": self.servo.counts_to_degrees(pos, offset=180.0),
            "velocity": self.servo.counts_to_degrees(vel, offset=0.0),
        }

    def get_torque_enabled(self, actuator_id: int) -> bool:
        return actuator_id in self.torque_enabled_ids


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
                    success &= self.servo.writeReg_Verify(actuator_id, SMS_STS_KP, kp)
                    changes.append(f"kp={kp}")

                # KD
                if "kd" in config:
                    kd = int(config["kd"])
                    if not (0 <= kd <= 255):
                        self.log.error(f"kd out of range: {kd}")
                        return False
                    success &= self.servo.writeReg_Verify(actuator_id, SMS_STS_KD, kd)
                    changes.append(f"kd={kd}")

                # Acceleration
                if "acceleration" in config:
                    acceleration = config["acceleration"]
                    # Convert if needed
                    if acceleration != 0:
                        acceleration = (
                            self.servo.degrees_to_counts(acceleration, offset=0.0) / 100.0
                        )
                    acceleration = int(acceleration)
                    if not (0 <= acceleration <= 255):
                        self.log.error(f"acceleration out of range: {acceleration}")
                        return False
                    success &= self.servo.writeReg_Verify(
                        actuator_id, SMS_STS_ACC, acceleration
                    )
                    changes.append(f"acc={acceleration}")

                # Torque enable
                if "torque_enabled" in config:
                    torque_enabled = bool(config["torque_enabled"])
                    was_enabled = actuator_id in self.torque_enabled_ids
                    success &= self.servo.writeReg_Verify(
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
                    self.servo.set_zero_position(actuator_id)
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