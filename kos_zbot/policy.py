import asyncio
import logging
import os
import sys
from kos_zbot.provider import ModelProvider
from kinfer.rust_bindings import PyModelRunner
from kos_zbot.utils.logging import get_logger
from kos_zbot.actuator import SCSMotorController
from kos_zbot.imu import BNO055Manager

class PolicyManager:
    def __init__(self, actuator_controller: SCSMotorController, imu_manager: BNO055Manager):
        self.log = get_logger(__name__)
        self.running = False
        self.actuator_controller = actuator_controller
        self.imu_manager = imu_manager
        self.model_provider = ModelProvider(actuator_controller, imu_manager)
        self.model_runner = None
        self.carry = None

        self.episode_length = 30.0  # Default episode length in seconds TODO: Move elsewhere, config file?
        self.action_scale = 0.1     # Default action scale
     
        self.stop_event = asyncio.Event()
        self.task = None
       #TODO: Work on state feedback (this is a placeholder)
        self.state = {
            "status": "idle",
            "policy_file": "none",
            "action_scale": str(self.action_scale),
            "episode_length": str(self.episode_length),
            "dry_run": "false"
        }

    async def start_policy(self, policy_file: str, action_scale: float, episode_length: int, dry_run: bool):
        """Start policy execution with the given parameters."""
        if self.running:
            self.log.warning("Policy already running")
            return False

        if not os.path.exists(policy_file):
            self.log.error(f"Policy file not found: {policy_file}")
            return False

        #TODO: Work on state feedback (this is a placeholder)
        # Update state with policy parameters
        self.state = {
            "policy_file": policy_file,
            "action_scale": str(action_scale),
            "episode_length": str(episode_length),
            "dry_run": str(dry_run).lower(),
            "status": "running"
        }
        
        try:
            # Store parameters
            self.episode_length = episode_length
            self.action_scale = action_scale

            # Configure actuators with kp, kd values and enable torque
            for joint_name, metadata in self.model_provider.actuator_metadata.items():
                actuator_id = self.model_provider.joint_to_actuator[joint_name]
                config = {
                    "kp": metadata["kp"],
                    "kd": metadata["kd"],
                    "torque_enabled": True,
                    "acceleration": 1000
                }
                success = self.actuator_controller.configure_actuator(actuator_id, config)
                if success:
                    self.log.info(f"Configured actuator {actuator_id} ({joint_name}) with kp={metadata['kp']}, kd={metadata['kd']}")
                else:
                    self.log.error(f"Failed to configure actuator {actuator_id} ({joint_name})")
                    return False

            # Initialize model runner with custom action scale
            self.model_provider.set_action_scale(self.action_scale)
            self.model_runner = PyModelRunner(policy_file, self.model_provider)
            self.carry = self.model_runner.init()

            # Start policy execution
            self.stop_event.clear()
            self.running = True
            self.task = asyncio.create_task(self._run_policy())
            return True

        except Exception as e:
            self.log.error(f"Failed to start policy: {e}")
            # Cleanup on failure
            self.model_runner = None
            self.carry = None
            return False

    async def _zero_all_joints(self):
        """Move all joints back to zero position."""
        try:
            # Create position commands for all actuators
            position_commands = {}
            for joint_name, actuator_id in self.model_provider.joint_to_actuator.items():
                if actuator_id in self.actuator_controller.actuator_ids:
                    position_commands[actuator_id] = {
                        "position": 0.0,  # Move to 0 degrees
                        "velocity": 0.0   # Disable vmax
                    }
            
            # Send commands to actuators
            if position_commands:
                self.log.info("Moving all joints to zero position")
                self.actuator_controller.set_targets(position_commands)
                # Wait a bit for the movement to complete
                await asyncio.sleep(1.0)
        except Exception as e:
            self.log.error(f"Error zeroing joints: {e}")

    async def stop_policy(self):
        """Stop policy deployment."""
        if not self.running:
            return True

        self.stop_event.set()
        if self.task:
            await self.task

        # Move all joints to zero position
        await self._zero_all_joints()

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
                "dry_run": "false"
            }
        return self.state

    async def _run_policy(self):
        """Main policy execution loop with deadline-based timing."""
        try:
            loop = asyncio.get_event_loop()
            # Initialize deadline for 50Hz control loop (20ms period)
            deadline = loop.time() + 0.02
            start_time = loop.time()
            
            while not self.stop_event.is_set():
                # Check episode length
                if loop.time() - start_time >= self.episode_length:
                    self.log.info(f"Episode length ({self.episode_length}s) reached, stopping policy")
                    self.stop_event.set()
                    # Move joints to zero before exiting
                    await self._zero_all_joints()
                    break

                # Clear arrays for this iteration
                self.model_provider.arrays.clear()
                # Run one step of the model
                output, self.carry = self.model_runner.step(self.carry)
                
                # Apply the output to the actuators
                self.model_runner.take_action(output)

                # Calculate time to sleep until next deadline
                now = loop.time()
                sleep_time = deadline - now
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    self.log.warning(f"Control loop running behind by {-sleep_time*1000:.2f}ms")
                
                # Set next deadline
                deadline += 0.02  # 50Hz control loop

        except Exception as e:
            self.log.error(f"Policy execution error: {e}")
            raise  # Re-raise to be handled by the caller
        finally:
            self.running = False
            self.model_runner = None
            self.carry = None