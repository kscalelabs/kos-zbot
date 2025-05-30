from typing import Sequence, cast
import numpy as np
from kinfer.rust_bindings import ModelProviderABC
from kos_zbot.actuator import SCSMotorController
from kos_zbot.imu import BNO055Manager
from kos_zbot.utils.logging import get_logger
from kos_zbot.utils.quat import rotate_vector_by_quat
from kos_zbot.utils.metadata import RobotMetadata
import time


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
        self.action_scale = 0.05  # Default to 5% of model output
        self.log = get_logger(__name__)

        metadata_manager = RobotMetadata.get_instance()
        self.joint_to_actuator = metadata_manager.get_joint_to_actuator_mapping()
        self.log.info(f"Joint to actuator mapping: {self.joint_to_actuator}")

      
    def get_joint_angles(self, joint_names: Sequence[str]) -> np.ndarray:
        """Get current joint angles from actuators in radians."""
        angles = []
        positions_log = {}
        current_time = time.time()
        for name in joint_names:
            actuator_id = self.joint_to_actuator[name]
            position = self.actuator_controller.get_position(actuator_id)
            if position is None:
                position = 0.0
                self.log.error(f"Position for joint {name} is None")

            positions_log[name] = {
                "actuator_id": actuator_id,
                "position_degrees": float(position)
            }
            angles.append(self.degrees_to_radians(float(position)))

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
                #self.log.error(f"Velocity for joint {name} is None")
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
        position_commands = {}

        for i, name in enumerate(joint_names):
            if name not in self.joint_to_actuator:
                self.log.error(f"take_action: Invalid joint name: {name}")
                continue

            actuator_id = self.joint_to_actuator[name]
            scaled_position = self.radians_to_degrees(
                float(action[i]) * self.action_scale
            )

            if actuator_id in self.actuator_controller.actuator_ids:
                position_commands[actuator_id] = scaled_position
            else:
                self.log.error(
                    f"take_action: actuator_id: {actuator_id} for joint: {name} not available"
                )

        if position_commands:
            target_commands = {
                aid: {"position": pos, "velocity": 286}
                for aid, pos in position_commands.items()
            }
            self.actuator_controller.set_targets(target_commands)