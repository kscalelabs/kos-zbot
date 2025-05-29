# minimal_motor_server.py
import asyncio
import grpc
from concurrent import futures
from google.protobuf import empty_pb2
from google.protobuf.struct_pb2 import Struct
from kos_protos import (
    actuator_pb2,
    actuator_pb2_grpc,
    common_pb2,
    imu_pb2,
    imu_pb2_grpc,
    policy_pb2,
    policy_pb2_grpc,
)
from kos_zbot.actuator import SCSMotorController, NoActuatorsFoundError
from kos_zbot.imu import BNO055Manager, IMUNotAvailableError
from kos_zbot.policy import PolicyManager
from kos_zbot.utils.metadata import RobotMetadata
import logging
import signal
from kos_zbot.utils.logging import KOSLoggerSetup, get_log_level, get_logger


import os
import sys
import fcntl
import termios
import time

class ActuatorService(actuator_pb2_grpc.ActuatorServiceServicer):
    def __init__(self, actuator_controller):
        super().__init__()
        self.actuator_controller = actuator_controller
        self.log = get_logger(__name__)
        self.temporal_lock = asyncio.Lock()

    async def ConfigureActuator(self, request, context):
        """Handle actuator configuration."""
        try:
            async with self.temporal_lock:
                config = {}
                if request.HasField("torque_enabled"):
                    config["torque_enabled"] = request.torque_enabled
                if request.HasField("zero_position"):
                    config["zero_position"] = request.zero_position
                if request.HasField("kp"):
                    config["kp"] = request.kp
                if request.HasField("kd"):
                    config["kd"] = request.kd
                if request.HasField("ki"):
                    config["ki"] = request.ki
                if request.HasField("max_torque"):
                    config["max_torque"] = request.max_torque
                if request.HasField("acceleration"):
                    config["acceleration"] = request.acceleration
                if request.HasField("new_actuator_id"):
                    config["new_actuator_id"] = request.new_actuator_id

                success = self.actuator_controller.configure_actuator(
                    request.actuator_id, config
                )
                if not success:
                    error_msg = f"failed to configure actuator {request.actuator_id}"
                    self.log.error(error_msg)
                    context.set_code(grpc.StatusCode.FAILED_PRECONDITION)
                    context.set_details(error_msg)
                    return common_pb2.ActionResponse(success=False)

                return common_pb2.ActionResponse(success=success)

        except RuntimeError:
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("another control operation is in progress")
            return common_pb2.ActionResponse(success=False)

        except Exception as e:
            error_msg = f"error configuring actuator {request.actuator_id}: {str(e)}"
            self.log.error(error_msg)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(error_msg)
            return common_pb2.ActionResponse(success=False)

    async def CommandActuators(self, request, context):
        """Handle multiple actuator commands atomically."""
        try:
            async with self.temporal_lock:
                commands = [
                    {
                        "actuator_id": cmd.actuator_id,
                        "position": cmd.position,
                        "velocity": cmd.velocity if cmd.HasField("velocity") else 0.0,
                    }
                    for cmd in request.commands
                ]
                servo_commands = {
                    cmd["actuator_id"]: {
                        "position": cmd["position"],
                        "velocity": cmd["velocity"],
                    }
                    for cmd in commands
                    if cmd["actuator_id"] in self.actuator_controller.actuator_ids
                }
                self.actuator_controller.set_targets(servo_commands)

                return actuator_pb2.CommandActuatorsResponse()

        except RuntimeError:
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("Another control operation is in progress.")
            return common_pb2.ActionResponse(success=False)

        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return actuator_pb2.CommandActuatorsResponse()

    async def ParameterDump(self, request, context):
        """Return parameter map for each actuator ID requested."""

        def dict_to_struct(d: dict) -> Struct:
            s = Struct()
            s.update(d)
            return s

        try:
            ids = request.actuator_ids or sorted(self.actuator_controller.actuator_ids)
            result = []
            self.log.info(f"ParameterDump request: {ids}")
            for aid in ids:
                if aid not in self.actuator_controller.actuator_ids:
                    self.log.warning(f"actuator {aid} not registered")
                    continue  # Skip unregistered actuators
                try:
                    param_dict = self.actuator_controller.read_all_servo_params(aid)
                    result.append(
                        actuator_pb2.ParameterDumpEntry(
                            actuator_id=aid, parameters=dict_to_struct(param_dict)
                        )
                    )
                except Exception as e:
                    self.log.warning(
                        f"failed to read parameters from actuator {aid}: {e}"
                    )
                    continue  # Skip on failure

            return actuator_pb2.ParameterDumpResponse(entries=result)

        except Exception as e:
            self.log.error(f"failed to handle GetParameters: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return actuator_pb2.ParameterDumpResponse()

    async def GetActuatorsState(self, request, context):
        """Handle actuator state requests."""
        try:
            # If no IDs or 0 is in the list, return all
            if not request.actuator_ids:
                ids = sorted(self.actuator_controller.actuator_ids)
            else:
                ids = request.actuator_ids

            states = []
            for actuator_id in ids:
                if actuator_id not in self.actuator_controller.actuator_ids:
                    state = actuator_pb2.ActuatorStateResponse(
                        actuator_id=actuator_id,
                        position=0.0,
                        velocity=0.0,
                        online=False,
                        torque_enabled=False,
                        faults=["servo not registered"],
                    )
                    states.append(state)
                    continue

                torque_enabled = self.actuator_controller.get_torque_enabled(actuator_id)
                state_dict = self.actuator_controller.get_state(actuator_id)
                fault_info = self.actuator_controller.get_faults(actuator_id)
                limits = self.actuator_controller.get_limits(actuator_id)
                if fault_info is None:
                    faults = []
                else:
                    faults = [
                        str(fault_info["last_fault_message"]),
                        str(fault_info["total_faults"]),
                        str(int(fault_info["last_fault_time"])),  # as integer timestamp
                    ]

                if state_dict is None:
                    state = actuator_pb2.ActuatorStateResponse(
                        actuator_id=actuator_id,
                        position=0.0,
                        velocity=0.0,
                        online=False,
                        faults=faults,
                    )
                else:
                    state_kwargs = {
                        "actuator_id": actuator_id,
                        "position": state_dict.get("position", 0.0),
                        "velocity": state_dict.get("velocity", 0.0),
                        "online": torque_enabled,
                        "torque_enabled": torque_enabled,
                        "faults": faults,
                    }
                    if limits:
                        if limits["min_position"] is not None:
                            state_kwargs["min_position"] = limits["min_position"]
                        if limits["max_position"] is not None:
                            state_kwargs["max_position"] = limits["max_position"]
                    
                    state = actuator_pb2.ActuatorStateResponse(**state_kwargs)

                states.append(state)
            return actuator_pb2.GetActuatorsStateResponse(states=states)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return actuator_pb2.GetActuatorsStateResponse()


class IMUService(imu_pb2_grpc.IMUServiceServicer):
    """Implementation of IMUService that wraps a BNO055 sensor."""

    def __init__(self, imu_manager):
        self.imu = imu_manager
        self.log = get_logger(__name__)

    def __del__(self):
        """Ensure cleanup of IMU manager."""
        if hasattr(self, "imu"):
            self.imu.stop()

    async def GetValues(
        self, request: empty_pb2.Empty, context: grpc.ServicerContext
    ) -> imu_pb2.IMUValuesResponse:
        """Implements GetValues by reading IMU sensor data."""
        try:
            accel, gyro, mag = self.imu.get_values()
            return imu_pb2.IMUValuesResponse(
                accel_x=float(accel[0]),
                accel_y=float(accel[1]),
                accel_z=float(accel[2]),
                gyro_x=float(gyro[0]),
                gyro_y=float(gyro[1]),
                gyro_z=float(gyro[2]),
                mag_x=float(mag[0]),
                mag_y=float(mag[1]),
                mag_z=float(mag[2]),
            )
        except IMUNotAvailableError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
            return imu_pb2.IMUValuesResponse(error=common_pb2.Error(message=str(e)))
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return imu_pb2.IMUValuesResponse(error=common_pb2.Error(message=str(e)))

    async def GetQuaternion(
        self, request: empty_pb2.Empty, context: grpc.ServicerContext
    ) -> imu_pb2.QuaternionResponse:
        """Implements GetQuaternion by reading orientation data."""
        try:
            w, x, y, z = self.imu.get_quaternion()
            return imu_pb2.QuaternionResponse(
                w=float(w), x=float(x), y=float(y), z=float(z)
            )
        except IMUNotAvailableError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
            return imu_pb2.QuaternionResponse(error=common_pb2.Error(message=str(e)))
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return imu_pb2.QuaternionResponse(error=common_pb2.Error(message=str(e)))

    async def GetEuler(
        self, request: empty_pb2.Empty, context: grpc.ServicerContext
    ) -> imu_pb2.EulerAnglesResponse:
        """Implements GetEuler by reading Euler angles directly from sensor."""
        try:
            roll, pitch, yaw = self.imu.get_euler()
            return imu_pb2.EulerAnglesResponse(
                roll=float(roll), pitch=float(pitch), yaw=float(yaw)
            )
        except IMUNotAvailableError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
            return imu_pb2.EulerAnglesResponse(error=common_pb2.Error(message=str(e)))
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return imu_pb2.EulerAnglesResponse(error=common_pb2.Error(message=str(e)))

    async def GetAdvancedValues(
        self, request: empty_pb2.Empty, context: grpc.ServicerContext
    ) -> imu_pb2.IMUAdvancedValuesResponse:
        """Implements GetAdvancedValues by reading extended sensor data."""
        try:
            lin_accel, gravity, temp = self.imu.get_advanced_values()
            return imu_pb2.IMUAdvancedValuesResponse(
                lin_acc_x=float(lin_accel[0]),
                lin_acc_y=float(lin_accel[1]),
                lin_acc_z=float(lin_accel[2]),
                grav_x=float(gravity[0]),
                grav_y=float(gravity[1]),
                grav_z=float(gravity[2]),
                temp=float(temp),
            )
        except IMUNotAvailableError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
            return imu_pb2.IMUAdvancedValuesResponse(
                error=common_pb2.Error(message=str(e))
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return imu_pb2.IMUAdvancedValuesResponse(
                error=common_pb2.Error(message=str(e))
            )

    async def GetCalibrationState(
        self, request: imu_pb2.GetCalibrationStateRequest, context: grpc.ServicerContext
    ) -> imu_pb2.GetCalibrationStateResponse:
        """Implements GetCalibrationState by reading calibration status from the IMU."""
        try:
            calib = self.imu.get_calibration_status()  # (sys, gyro, accel, mag)
            calib_map = {
                "sys": int(calib[0]),
                "gyro": int(calib[1]),
                "accel": int(calib[2]),
                "mag": int(calib[3]),
            }
            return imu_pb2.GetCalibrationStateResponse(state=calib_map)
        except IMUNotAvailableError as e:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details(str(e))
            return imu_pb2.GetCalibrationStateResponse(
                error=common_pb2.Error(message=str(e))
            )
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return imu_pb2.GetCalibrationStateResponse(
                error=common_pb2.Error(message=str(e))
            )

    async def Zero(
        self, request: imu_pb2.ZeroIMURequest, context: grpc.ServicerContext
    ) -> common_pb2.ActionResponse:
        """Implements Zero - Note: BNO055 handles calibration internally."""
        # The BNO055 handles its own zeroing/calibration, so this is a no-op
        return common_pb2.ActionResponse(success=True)


class PolicyService(policy_pb2_grpc.PolicyServiceServicer):
    def __init__(self, policy_manager: PolicyManager):
        super().__init__()
        self.policy_manager = policy_manager
        self.log = get_logger(__name__)

    async def StartPolicy(self, request: policy_pb2.StartPolicyRequest, context):
        """Start policy deployment."""
        try:
            success = await self.policy_manager.start_policy(
                policy_file=request.action,
                action_scale=request.action_scale,
                episode_length=request.episode_length,
                dry_run=request.dry_run,
            )
            return policy_pb2.StartPolicyResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return policy_pb2.StartPolicyResponse()

    async def StopPolicy(self, request: empty_pb2.Empty, context):
        """Stop policy deployment."""
        try:
            success = await self.policy_manager.stop_policy()
            return policy_pb2.StopPolicyResponse()
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return policy_pb2.StopPolicyResponse()

    async def GetState(self, request: empty_pb2.Empty, context):
        """Get current policy state."""
        try:
            state = await self.policy_manager.get_state()
            # Ensure all values are strings
            string_state = {k: str(v) for k, v in state.items()}
            return policy_pb2.GetStateResponse(state=string_state)
        except Exception as e:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return policy_pb2.GetStateResponse()


async def serve(host: str = "0.0.0.0", port: int = 50051):
    """Start the gRPC server."""
    log = get_logger(__name__)
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    metadata = None
    metadata_manager = RobotMetadata.get_instance()
    
    if metadata_manager.robot_name:
        # Try to load robot metadata from the API
        metadata = await metadata_manager.get_metadata_async()
        log.info(f"Successfully loaded metadata for robot: {metadata_manager.robot_name}")

    else:
        log.info("No robot name specified. Running KOS service without robot-specific configuration.")


    # Initialize hardware
    try:
        actuator_controller = SCSMotorController(
            device="/dev/ttyAMA5", baudrate=1000000, rate=50,robot_metadata=metadata
        )
        actuator_controller.start()
    except NoActuatorsFoundError as e:
        sys.exit(1)

    imu_manager = BNO055Manager(update_rate=100)
    imu_manager.start()

    # Initialize policy manager
    policy_manager = PolicyManager(actuator_controller, imu_manager)

    stop_event = asyncio.Event()

    def handle_signal():
        log.info("received shutdown signal")
        stop_event.set()

    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)

    try:
        actuator_service = ActuatorService(actuator_controller)
        actuator_pb2_grpc.add_ActuatorServiceServicer_to_server(
            actuator_service, server
        )

        imu_service = IMUService(imu_manager)
        imu_pb2_grpc.add_IMUServiceServicer_to_server(imu_service, server)

        policy_service = PolicyService(policy_manager)
        policy_pb2_grpc.add_PolicyServiceServicer_to_server(policy_service, server)

        server.add_insecure_port(f"{host}:{port}")
        await server.start()
        log.info(f"KOS ZBot service started on {host}:{port}")
        await stop_event.wait()
        await policy_manager.stop_policy()
        await server.stop(1)
        log.info("KOS ZBot service stopped")
    finally:
        actuator_controller.stop()
        imu_manager.stop()


def singleton_check(pidfile="/tmp/kos.pid"):
    """Ensure only one kos process runs at a time."""
    log = get_logger(__name__)
    pidfile_fd = os.open(pidfile, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.lockf(pidfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        # File is locked by another process
        with open(pidfile, "r") as f:
            existing_pid = f.read().strip()
        if existing_pid and existing_pid.isdigit():
            try:
                os.kill(int(existing_pid), 0)
                # Process is alive
                answer = input(
                    f"A kos process is already running (PID: {existing_pid}). Stop it? [y/N] "
                )
                if answer.lower() == "y":
                    os.kill(int(existing_pid), 15)  # SIGTERM
                    log.info("Sent SIGTERM, waiting for process to exit...")
                    import time

                    for _ in range(10):
                        try:
                            os.kill(int(existing_pid), 0)
                            time.sleep(0.5)
                        except OSError:
                            break
                    else:
                        log.info("Process did not exit, exiting.")
                        sys.exit(1)
                    # Try to acquire lock again
                    fcntl.lockf(pidfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    log.info("Exiting.")
                    sys.exit(1)
            except OSError:
                # Process not running, remove stale pidfile
                log.info("Stale PID file found, removing.")
                os.remove(pidfile)
                fcntl.lockf(pidfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:
            log.info("PID file exists but is invalid, removing.")
            os.remove(pidfile)
            fcntl.lockf(pidfile_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # Write our PID
    os.ftruncate(pidfile_fd, 0)
    os.write(pidfile_fd, str(os.getpid()).encode())
    # Keep the file descriptor open for the life of the process
    return pidfile_fd


def main():
    singleton_check()
    KOSLoggerSetup.setup(
        log_dir="logs", console_level=get_log_level(), file_level=logging.DEBUG
    )

    asyncio.run(serve())


if __name__ == "__main__":
    main()
