from typing import Sequence, cast
import numpy as np
from kinfer.rust_bindings import ModelProviderABC, PyModelMetadata
from abc import ABC, abstractmethod
from kos_zbot.actuator import SCSMotorController
from kos_zbot.imu import BNO055Manager
from kos_zbot.utils.logging import get_logger
from kos_zbot.utils.quat import rotate_vector_by_quat
from kos_zbot.utils.metadata import RobotMetadata
import time


def quat_to_euler(quat: np.ndarray) -> np.ndarray:
    """Converts a quaternion to Euler angles.

    Args:
        quat: The quaternion to convert, shape (*, 4).

    Returns:
        The Euler angles, shape (*, 3).
    """
    eps: float = 1e-6  # small epsilon to avoid division by zero and NaNs

    # Ensure numpy array and normalize the quaternion to unit length
    quat = np.asarray(quat, dtype=np.float64)
    quat = quat / (np.linalg.norm(quat, axis=-1, keepdims=True) + eps)

    # Split into components (expects quaternion in (w, x, y, z) order)
    w, x, y, z = np.split(quat, 4, axis=-1)

    # Roll (x-axis rotation)
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = np.arctan2(sinr_cosp, cosr_cosp)

    # Pitch (y-axis rotation)
    sinp = 2.0 * (w * y - z * x)
    sinp = np.clip(sinp, -1.0 + eps, 1.0 - eps)  # numerical safety
    pitch = np.arcsin(sinp)

    # Yaw (z-axis rotation)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = np.arctan2(siny_cosp, cosy_cosp)

    # Concatenate along the last dimension to maintain input shape semantics
    euler = np.concatenate([roll, pitch, yaw], axis=-1)
    return euler.astype(np.float32)


class InputState(ABC):
    """Abstract base class for input state management."""

    value: list[float]

    @abstractmethod
    async def update(self, key: str) -> None:
        """Update the input state based on a key press."""
        pass


class JoystickInputState(InputState):
    """State to hold and modify commands based on joystick input."""

    value: list[float]

    def __init__(self) -> None:
        self.value = [1, 0, 0, 0, 0, 0, 0]

    async def update(self, key: str) -> None:
        if key == "w":
            self.value = [0, 1, 0, 0, 0, 0, 0]
        elif key == "s":
            self.value = [0, 0, 1, 0, 0, 0, 0]
        elif key == "a":
            self.value = [0, 0, 0, 0, 0, 1, 0]
        elif key == "d":
            self.value = [0, 0, 0, 0, 0, 0, 1]
        elif key == "q":
            self.value = [0, 0, 0, 1, 0, 0, 0]
        elif key == "e":
            self.value = [0, 0, 0, 0, 1, 0, 0]


class SimpleJoystickInputState(InputState):
    """State to hold and modify commands based on simple joystick input."""

    value: list[float]

    def __init__(self) -> None:
        self.value = [1, 0, 0, 0]

    async def update(self, key: str) -> None:
        if key == "w":
            self.value = [0, 1, 0, 0]
        elif key == "s":
            self.value = [0, 0, 1, 0]
        elif key == "a":
            self.value = [0, 0, 0, 1]
        elif key == "d":
            self.value = [1, 0, 0, 0]



class ControlVectorInputState(InputState):
    """State to hold and modify control vector commands based on keyboard input."""

    value: list[float]
    STEP_SIZE: float = 0.1

    def __init__(self) -> None:
        self.value = [0.0, 0.0, 0.0]  # x linear, y linear, z angular

    async def update(self, key: str) -> None:
        if key == "w":
            self.value[0] += self.STEP_SIZE
        elif key == "s":
            self.value[0] -= self.STEP_SIZE
        elif key == "a":
            self.value[1] -= self.STEP_SIZE
        elif key == "d":
            self.value[1] += self.STEP_SIZE
        elif key == "q":
            self.value[2] -= self.STEP_SIZE
        elif key == "e":
            self.value[2] += self.STEP_SIZE


class ExpandedControlVectorInputState(InputState):
    """State to hold and modify control vector commands based on keyboard input."""

    value: list[float]
    STEP_SIZE: float = 0.1

    def __init__(self) -> None:
        self.value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # x linear, y linear, yaw, base height, roll, pitch

    async def update(self, key: str) -> None:
        if key == "w":
            self.value[0] += self.STEP_SIZE
        elif key == "s":
            self.value[0] -= self.STEP_SIZE
        elif key == "a":
            self.value[1] -= self.STEP_SIZE
        elif key == "d":
            self.value[1] += self.STEP_SIZE
        elif key == "q":
            self.value[2] -= self.STEP_SIZE
        elif key == "e":
            self.value[2] += self.STEP_SIZE
        elif key == "r":
            self.value[4] += self.STEP_SIZE
        elif key == "f":
            self.value[4] -= self.STEP_SIZE
        elif key == "t":
            self.value[5] += self.STEP_SIZE
        elif key == "g":
            self.value[5] -= self.STEP_SIZE


class GenericOHEInputState(InputState):
    """State to hold and modify control vector commands based on keyboard input."""

    value: list[float]

    def __init__(self, num_actions: int) -> None:
        self.value = [0.0] * num_actions

    async def update(self, key: str) -> None:
        if key.isdigit() and int(key) < len(self.value):
            self.value = [0.0] * len(self.value)
            self.value[int(key)] = 1.0


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

         # Initialize initial_heading when IMU is available
        try:
            initial_quat = self.get_quaternion()
            self.initial_heading = quat_to_euler(initial_quat)[2]
        except Exception as e:
            self.log.warning(f"Could not get initial heading: {e}")
            self.initial_heading = 0.0


    def get_inputs(self, input_types: Sequence[str], metadata: PyModelMetadata) -> dict[str, np.ndarray]:
        """Get inputs for the model based on the requested input types.

        Args:
            input_types: List of input type names to retrieve
            metadata: Model metadata containing joint names and other info

        Returns:
            Dictionary mapping input type names to numpy arrays
        """
        inputs = {}

        for input_type in input_types:
            if input_type == "joint_angles":
                inputs[input_type] = self.get_joint_angles(metadata.joint_names)  # type: ignore[attr-defined]
            elif input_type == "joint_angular_velocities":
                inputs[input_type] = self.get_joint_angular_velocities(metadata.joint_names)  # type: ignore[attr-defined]
            elif input_type == "initial_heading":
                inputs[input_type] = np.array([self.initial_heading], dtype=np.float32)
            elif input_type == "quaternion":
                inputs[input_type] = self.get_quaternion()
            elif input_type == "projected_gravity":
                inputs[input_type] = self.get_projected_gravity()
            elif input_type == "accelerometer":
                inputs[input_type] = self.get_accelerometer()
            elif input_type == "gyroscope":
                inputs[input_type] = self.get_gyroscope()
            elif input_type == "command":
                inputs[input_type] = self.get_command()
            elif input_type == "time":
                inputs[input_type] = self.get_time()
            else:
                raise ValueError(f"Unknown input type: {input_type}")

        return inputs
      
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
        #proj_gravity = np.array([0, 0, -9.80], dtype=np.float32)
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

    def get_time(self) -> np.ndarray:
        time = time.time()
        time_array = np.array([time], dtype=np.float32)
        self.arrays["time"] = time_array
        return time_array

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

    #def get_command(self) -> np.ndarray:
        # Return default command values with current heading
        # Format: [x_linear, y_linear, yaw, base_height, roll, pitch]
    #    try:
    #        current_quat = self.get_quaternion()
    #        current_heading = quat_to_euler(current_quat)[2]
    #        # Return 6-dimensional command with heading - matching ExpandedControlVectorInputState format
    #        command_values = [2.0, 0.0, current_heading, 0.0, 0.0, 0.0]  # x, y, yaw(heading), base_height, roll, pitch
    #    except Exception as e:
    #        self.log.warning(f"Could not get current heading for command: {e}")
    #        command_values = [2.0, 0.0, self.initial_heading, 0.0, 0.0, 0.0]  # fallback to initial heading

    #    command_array = np.array(command_values, dtype=np.float32)
    #    self.arrays["command"] = command_array
    #    return command_array

    def get_command(self) -> np.ndarray:
        # Return 6-dimensional command with all zeros
        # Format: [x_linear, y_linear, yaw, base_height, roll, pitch]
        command_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

        
        #---------------------------------
        # Tilt Compensation Test
        # command = [cmd0, cmd1, cmd2, cmd3, cmd4, cmd5]  # 6 total commands

        # === TILT COMPENSATION GAIN CONTROL ===
        # command[0]: Pitch gain control
        #   - Maps [-1,1] to [0.5, 3.5] 
        #   - Default (-1) gives roll_gain = 2.0
        #   - Controls how much forward/backward tilt affects roll joints

        # command[1]: Roll gain control  
        #   - Maps [-1,1] to [0.5, 2.5]
        #   - Default (-1) gives pitch_gain = 1.5
        #   - Controls how much side-to-side tilt affects pitch joints

        # command[2]: hip pitch scale control
        #   - Maps [-1,1] to [0.2, 0.8]
        #   - Default (-1) gives hip_pitch_scale = 0.5
        #   - Scales how much hip pitch joints respond to roll tilt

        # command[3]: Ankle roll scale control
        #   - Maps [-1,1] to [0.2, 0.8]
        #   - Default (-1) gives ankle_roll_scale = 0.5
        #   - Scales how much ankle roll joints respond to pitch tilt

        # command[4]: Ankle pitch scale control  
        #   - Maps [-1,1] to [0.2, 0.8]
        #   - Default (-1) gives ankle_pitch_scale = 0.5
        #   - Scales how much ankle pitch joints respond to roll tilt

        # command[5]: Knee pitch scale control
        #   - Maps [-1,1] to [0.2, 0.8]
        #   - Default (-1) gives knee_pitch_scale = 0.5
        #   - Scales how much knee pitch joints respond to roll tilt

        # === ORIGINAL COMMAND MEANING (from NUM_COMMANDS comment) ===
        # NUM_COMMANDS = 6  # vx, vy, heading, bh, rx, ry
        # But these are hijacked for tilt control gains instead
        #command_values = [-0.85, 0.0, 0.3, 1.0, 6.0, 2.0]
        #---------------------------------

        # Interactive Pose
        #--------------------------------
        #command_values = [1.0, 1000.0, -1.0, 1.0, 0.5, 1.0, 1.0]
        #                 pose gain restore blend arms legs speed
        #--------------------------------
        command_array = np.array(command_values, dtype=np.float32)
        self.arrays["command"] = command_array
        return command_array

    def take_action(self, action: np.ndarray, metadata: PyModelMetadata) -> None:
        """Send scaled position commands to actuators."""
        joint_names = metadata.joint_names  # type: ignore[attr-defined]
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
                aid: {"position": pos, "velocity": 0}
                for aid, pos in position_commands.items()
            }
            self.actuator_controller.set_targets(target_commands)