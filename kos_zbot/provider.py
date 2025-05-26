from typing import Sequence, cast
import numpy as np
from kinfer.rust_bindings import ModelProviderABC
from kos_zbot.actuator import SCSMotorController
from kos_zbot.imu import BNO055Manager
from kos_zbot.utils.logging import get_logger
from kos_zbot.utils.quat import rotate_vector_by_quat
import time
import json


class ModelProvider(ModelProviderABC):
    def __new__(cls, *args, **kwargs) -> "ModelProvider":
        self = cast(ModelProvider, super().__new__(cls))
        self.arrays = {}
        return self

    def __init__(
        self, actuator_controller: SCSMotorController, imu_manager: BNO055Manager
    ):
        self.actuator_controller = actuator_controller
        self.imu_manager = imu_manager
        self.action_scale = 0.05  # Default to 10% of model output
        self.log = get_logger(__name__)
        #self.policy_log = []

        # ----------------- THE FOLLOWING SECTION IS TEMPORARY, DO NOT JUDGE ME -----------------
        # TODO: Load this from metadata.json via kscale api

        # Map joint names to actuator IDs and metadata
        self.joint_to_actuator = {
            # Left arm
            "left_shoulder_pitch": 11,
            "left_shoulder_roll": 12,
            "left_elbow_roll": 13,
            "left_gripper_roll": 14,
            # Right arm
            "right_shoulder_pitch": 21,
            "right_shoulder_roll": 22,
            "right_elbow_roll": 23,
            "right_gripper_roll": 24,
            # Left leg
            "left_hip_yaw": 31,
            "left_hip_roll": 32,
            "left_hip_pitch": 33,
            "left_knee_pitch": 34,
            "left_ankle_roll": 35,
            "left_ankle_pitch": 36,
            # Right leg
            "right_hip_yaw": 41,
            "right_hip_roll": 42,
            "right_hip_pitch": 43,
            "right_knee_pitch": 44,
            "right_ankle_roll": 45,
            "right_ankle_pitch": 46,
        }

        # Store actuator metadata
        self.actuator_metadata = {
            # Left arm
            "left_shoulder_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -90.0,
                "max": 180.0,
            },
            "left_shoulder_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -18.0,
                "max": 180.0,
            },
            "left_elbow_roll": {
                "actuator_type": "feetech_sts3215_12v",
                "kp": 22.0,
                "kd": 12.0,
                "min": -80.0,
                "max": 90.0,
            },
            "left_gripper_roll": {
                "actuator_type": "feetech_sts3215_12v",
                "kp": 22.0,
                "kd": 12.0,
                "min": -28.0,
                "max": 38.0,
            },
            # Right arm
            "right_shoulder_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -180.0,
                "max": 90.0,
            },
            "right_shoulder_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -180.0,
                "max": 18.0,
            },
            "right_elbow_roll": {
                "actuator_type": "feetech_sts3215_12v",
                "kp": 22.0,
                "kd": 12.0,
                "min": -90.0,
                "max": 80.0,
            },
            "right_gripper_roll": {
                "actuator_type": "feetech_sts3215_12v",
                "kp": 22.0,
                "kd": 12.0,
                "min": -38.0,
                "max": 28.0,
            },
            # Left leg
            "left_hip_yaw": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -100.0,
                "max": 100.0,
            },
            "left_hip_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -35.0,
                "max": 35.0,
            },
            "left_hip_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -120.0,
                "max": 55.0,
            },
            "left_knee_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -130,
                "max": 100.0,
            },
            "left_ankle_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -35.0,
                "max": 35.0,
            },
            "left_ankle_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -90.0,
                "max": 35.0,
            },
            # Right leg
            "right_hip_yaw": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -100.0,
                "max": 100.0,
            },
            "right_hip_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -35.0,
                "max": 35.0,
            },
            "right_hip_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -120.0,
                "max": 55.0,
            },
            "right_knee_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -130,
                "max": 100.0,
            },
            "right_ankle_roll": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -35.0,
                "max": 35.0,
            },
            "right_ankle_pitch": {
                "actuator_type": "feetech_sts3250",
                "kp": 22.0,
                "kd": 12.0,
                "min": -90.0,
                "max": 35.0,
            },
        }

    def get_joint_angles(self, joint_names: Sequence[str]) -> np.ndarray:
        """Get current joint angles from actuators in radians."""
        angles = []
        positions_log = {}
        current_time = time.time()
        for name in joint_names:
            # self.log.info(f"Getting joint angle for {name}")
            actuator_id = self.joint_to_actuator[name]
            position = self.actuator_controller.get_position(actuator_id)
            if position is None:
                position = 0.0  # Default to 0 if position can't be read #TODO: Is this the right thing to do/
                self.log.error(f"Position for joint {name} is None")

            positions_log[name] = {
                "actuator_id": actuator_id,
                "position_degrees": float(position)
            }
            # Convert from degrees to radians
            angles.append(self.degrees_to_radians(float(position)))

        # Add to policy log
        #self.policy_log.append({
        #    "timestamp": current_time,
        #    "type": "joint_positions",
        #    "joint_data": positions_log
        #})

        angles_array = np.array(angles, dtype=np.float32)
        self.arrays["joint_angles"] = angles_array
        return angles_array

    def get_joint_angular_velocities(self, joint_names: Sequence[str]) -> np.ndarray:
        """Get current joint velocities from actuators."""
        velocities = []
        for name in joint_names:
            actuator_id = self.joint_to_actuator[name]
            velocity = self.actuator_controller.get_velocity(actuator_id)
            if velocity is None:
                velocity = 0.0  # Default to 0 if velocity can't be read #TODO: Is this the right thing to do/
                # self.log.error(f"Velocity for joint {name} is None")
            velocities.append(self.degrees_to_radians(float(velocity)))

        velocities_array = np.array(velocities, dtype=np.float32)
        self.arrays["joint_velocities"] = velocities_array
        return velocities_array

    def get_projected_gravity(self) -> np.ndarray:
        """Get gravity vector in body frame using IMU quaternion."""
        gravity = np.array([0, 0, -9.81], dtype=np.float32)  # Standard gravity vector
        quat = self.get_quaternion()
        proj_gravity = rotate_vector_by_quat(gravity, quat, inverse=True)
        #proj_gravity = np.array([0, 0, -9.81], dtype=np.float32)
        self.arrays["projected_gravity"] = proj_gravity

        # self.log.info(f"Projected gravity: {proj_gravity}")
        return proj_gravity

    def get_accelerometer(self) -> np.ndarray:
        """Get accelerometer data from IMU."""
        accel, _, _ = self.imu_manager.get_values()
        acc_array = np.array(accel, dtype=np.float32)
        self.arrays["accelerometer"] = acc_array
        return acc_array

    def get_gyroscope(self) -> np.ndarray:
        """Get gyroscope data from IMU."""
        _, gyro, _ = self.imu_manager.get_values()
        gyro_array = np.array(gyro, dtype=np.float32)
        self.arrays["gyroscope"] = gyro_array
        return gyro_array

    def get_quaternion(self) -> np.ndarray:
        """Get quaternion from IMU."""
        w, x, y, z = self.imu_manager.get_quaternion()
        quat = np.array([w, x, y, z], dtype=np.float32)
        self.arrays["quaternion"] = quat
        return quat

    def set_action_scale(self, scale: float):
        """Set the action scaling factor (0-1)."""
        self.action_scale = max(0.0, min(1.0, scale))

    @staticmethod
    def degrees_to_radians(degrees: float) -> float:
        """Convert degrees to radians."""
        return degrees * (np.pi / 180.0)

    @staticmethod
    def radians_to_degrees(radians: float) -> float:
        """Convert radians to degrees."""
        return radians * (180.0 / np.pi)

    def take_action(self, joint_names: Sequence[str], action: np.ndarray) -> None:
        """Send scaled position commands to actuators."""
        assert action.shape == (len(joint_names),)
        self.arrays["action"] = action
        current_time = time.time()
        # Create position commands for each actuator
        position_commands = {}
        action_log = {}

        for i, name in enumerate(joint_names):
            if name not in self.joint_to_actuator:
                self.log.error(f"take_action: Invalid joint name: {name}")
                continue

            actuator_id = self.joint_to_actuator[name]
            
            #raw_action_degrees = self.radians_to_degrees(float(action[i]))
          

            scaled_position = self.radians_to_degrees(
                float(action[i]) * self.action_scale
            )
            action_log[name] = {
                "actuator_id": actuator_id,
                "raw_action_degrees": scaled_position
            }

            # Only add command if actuator_id exists in controller
            if actuator_id in self.actuator_controller.actuator_ids:
                # Get limits from metadata
                metadata = self.actuator_metadata[name]

                if "min" in metadata and "max" in metadata:
                    # Clamp position to limits
                    scaled_position = max(
                        metadata["min"], min(metadata["max"], scaled_position)
                    )

                # if actuator_id > 15:
                # self.log.info(f"take_action: {name} scaled_position: {scaled_position}")
                position_commands[actuator_id] = scaled_position
            else:
                self.log.error(
                    f"take_action: actuator_id: {actuator_id} for joint: {name} not available"
                )

        # Send commands to actuators
        if position_commands:  # Only send if we have valid commands
            # Convert position commands to target commands with constant velocity
            target_commands = {
                aid: {"position": pos, "velocity": 286}
                for aid, pos in position_commands.items()
            }
            self.actuator_controller.set_targets(target_commands)
            # self.log.info(f"Sent target commands: {target_commands}")


    def save_logs(self, filename: str):
        pass
        #with open(filename, "w") as f:
        #    json.dump(self.policy_log, f)
