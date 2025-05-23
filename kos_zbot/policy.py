import logging
import os
import sys
from kos_zbot.provider import ModelProvider
from kinfer.rust_bindings import PyModelRunner
from kos_zbot.utils.logging import get_logger
from kos_zbot.actuator import SCSMotorController
from kos_zbot.imu import BNO055Manager
#from kos_zbot.utils.latency import get_tracker
import threading
import time


class PolicyManager:
    def __init__(
        self, actuator_controller: SCSMotorController, imu_manager: BNO055Manager
    ):
        self.log = get_logger(__name__)
        self.running = False
        self.actuator_controller = actuator_controller
        self.imu_manager = imu_manager
        self.model_provider = ModelProvider(actuator_controller, imu_manager)
        self.model_runner = None
        self.carry = None

        self.episode_length = (
            30.0  # Default episode length in seconds TODO: Move elsewhere, config file?
        )
        self.action_scale = 0.1  # Default action scale

        #self.latency_tracker = get_tracker("policy_loop")
        self.stop_event = False
        self.task = None
        # TODO: Work on state feedback (this is a placeholder)
        self.state = {
            "status": "idle",
            "policy_file": "none",
            "action_scale": str(self.action_scale),
            "episode_length": str(self.episode_length),
            "dry_run": "false",
        }

    def _zero_all_joints(self):
        """Move all joints back to zero position."""
        try:
            # Create position commands for all actuators
            position_commands = {}
            for (
                joint_name,
                actuator_id,
            ) in self.model_provider.joint_to_actuator.items():
                if actuator_id in self.actuator_controller.actuator_ids:
                    position_commands[actuator_id] = {
                        "position": 0.0,  # Move to 0 degrees
                        "velocity": 0.0,  # Disable vmax
                    }

            # Send commands to actuators
            if position_commands:
                self.log.info("Moving all joints to zero position")
                self.actuator_controller.set_targets(position_commands)
                # Wait a bit for the movement to complete
                time.sleep(1.0)
        except Exception as e:
            self.log.error(f"Error zeroing joints: {e}")

    async def start_policy(
        self, policy_file: str, action_scale: float, episode_length: int, dry_run: bool
    ):
        """Start policy execution with the given parameters."""
        if self.running:
            self.log.warning("Policy already running")
            return False

        if not os.path.exists(policy_file):
            self.log.error(f"Policy file not found: {policy_file}")
            return False

        self.state = {
            "policy_file": policy_file,
            "action_scale": str(action_scale),
            "episode_length": str(episode_length),
            "dry_run": str(dry_run).lower(),
            "status": "running",
        }

        try:
            self.episode_length = episode_length
            self.action_scale = action_scale

            # Configure actuators
            for joint_name, metadata in self.model_provider.actuator_metadata.items():
                actuator_id = self.model_provider.joint_to_actuator[joint_name]
                config = {
                    "kp": metadata["kp"],
                    "kd": metadata["kd"],
                    "torque_enabled": True,
                    "acceleration": 1000,
                }
                success = self.actuator_controller.configure_actuator(
                    actuator_id, config
                )
                if success:
                    self.log.info(
                        f"Configured actuator {actuator_id} ({joint_name}) with kp={metadata['kp']}, kd={metadata['kd']}"
                    )
                else:
                    self.log.error(
                        f"Failed to configure actuator {actuator_id} ({joint_name})"
                    )
                    return False

            self.model_provider.set_action_scale(self.action_scale)
            self.model_runner = PyModelRunner(policy_file, self.model_provider)
            self.carry = self.model_runner.init()

            self.stop_event = False
            self.running = True

            # Run the policy in a separate thread to not block the event loop
            self.thread = threading.Thread(target=self._run_policy)
            self.thread.start()

            #self.latency_tracker.reset()
            return True

        except Exception as e:
            self.log.error(f"Failed to start policy: {e}")
            self.model_runner = None
            self.carry = None
            return False

    async def stop_policy(self):
        """Stop policy deployment."""
        if not self.running:
            return True

        self.stop_event = True
        if hasattr(self, "thread"):
            self.thread.join()  # Wait for the policy thread to finish

        self._zero_all_joints()
        self.running = False
        self.model_runner = None
        self.carry = None

        return True

    async def get_state(self):
        """Get the current policy state."""
        if not self.running:
            return {
                "status": "stopped",
                "policy_file": "none",
                "action_scale": str(self.action_scale),
                "episode_length": str(self.episode_length),
                "dry_run": "false",
            }
        return self.state

    def _run_policy(self):
        """Main policy execution loop with precise timing."""
        try:
            import time

            start_time = time.monotonic()  # Use monotonic time
            period = 0.02  # 50Hz = 20ms period
            next_deadline = start_time + period  # Initial deadline
            period_ns = int(period * 1e9)
            #self.latency_tracker.set_period(period_ns)
            while not self.stop_event:
                #self.latency_tracker.record_iteration()
                # Check episode length
                if time.monotonic() - start_time >= self.episode_length:
                    self.log.info(
                        f"Episode length ({self.episode_length}s) reached, stopping policy"
                    )
                    self.stop_event = True
                    self._zero_all_joints()
                    break

                # Clear arrays for this iteration
                self.model_provider.arrays.clear()

                # Run one step of the model
                output, self.carry = self.model_runner.step(self.carry)

                # Apply the output to the actuators
                self.model_runner.take_action(output)

                # Sleep until close to deadline
                time.sleep(
                    max(0, next_deadline - time.monotonic() - 0.001)
                )  # Sleep until 1ms before deadline

                # Busy wait for the final millisecond
                while time.monotonic() < next_deadline:
                    pass

                # Update deadline for next iteration
                next_deadline += period

        except Exception as e:
            self.log.error(f"Policy execution error: {e}")
            raise
        finally:
            self.running = False
            self.model_runner = None
            self.carry = None
