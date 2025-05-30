# kos-zbot/kos_zbot/utils/metadata.py
import asyncio
from pathlib import Path
from typing import Dict, Optional

from kscale import K
from kscale.web.gen.api import JointMetadataOutput, RobotURDFMetadataOutput
from kscale.web.utils import get_robots_dir, should_refresh_file
from kos_zbot.utils.logging import get_logger

class RobotMetadata:
    """Simple metadata manager with singleton pattern."""
    _instance = None
    
    @classmethod
    def get_instance(cls) -> "RobotMetadata":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = RobotMetadata()
        return cls._instance
    
    def __init__(self):
        self.robot_name = None
        self.metadata = None
        self.log = get_logger(__name__)
    
    async def get_metadata_async(self) -> RobotURDFMetadataOutput:
        """Get metadata for the current robot."""
        if self.robot_name is None:
            raise ValueError("Robot name not set. Call load_model_metadata first.")
            
        if self.metadata is None:
            async with K() as api:
                self.metadata = await get_model_metadata(api, self.robot_name)
                
        return self.metadata

    def get_metadata(self) -> RobotURDFMetadataOutput:
        """Synchronous way to get metadata. 
        Returns cached metadata or loads it using asyncio.run."""
        if self.robot_name is None:
            raise ValueError("Robot name not set. Call load_model_metadata first.")
            
        if self.metadata is None:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an event loop, so we need to create a task
                # This is a bit tricky - we'll need to use a different approach
                import concurrent.futures
                import threading
                
                # Create a new event loop in a separate thread
                def run_in_new_loop():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(self.get_metadata_async())
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_new_loop)
                    self.metadata = future.result()
                    
            except RuntimeError:
                # No event loop running, safe to use asyncio.run
                self.metadata = asyncio.run(self.get_metadata_async())
                
        return self.metadata
    
    def load_model_metadata(self, robot_name: str) -> None:
        """Set the robot name and clear metadata cache."""
        self.robot_name = robot_name
        self.metadata = None  # Clear cache to ensure fresh load

    def get_joint_to_actuator_mapping(self) -> dict[str, int]:
        """Get joint-to-actuator ID mapping from robot metadata.
        
        Returns:
            Dictionary mapping joint names to actuator IDs.
        """
        try:
            metadata = self.get_metadata()
            
            if metadata is None or metadata.joint_name_to_metadata is None:
                self.log.error("No joint metadata available, returning empty mapping")
                return {}
            
            joint_to_actuator = {}
            for joint_name, joint_metadata in metadata.joint_name_to_metadata.items():
                if joint_metadata.id is not None:
                    joint_to_actuator[joint_name] = joint_metadata.id
                else:
                    self.log.warning(f"Joint {joint_name} has no actuator ID in metadata")
            
            self.log.info(f"Loaded {len(joint_to_actuator)} joint-to-actuator mappings from metadata")
            return joint_to_actuator
            
        except Exception as e:
            self.log.error(f"Failed to load joint metadata: {e}")
            self.log.warning("Returning empty joint-to-actuator mapping")
            return {}

async def get_model_metadata(api: K, model_name: str, cache: bool = True) -> RobotURDFMetadataOutput:
    """Get robot metadata from the API or cached file."""
    model_path = get_robots_dir() / model_name / "metadata.json"
    if cache and model_path.exists() and not should_refresh_file(model_path):
        return RobotURDFMetadataOutput.model_validate_json(model_path.read_text())
    model_path.parent.mkdir(parents=True, exist_ok=True)
    robot_class = await api.get_robot_class(model_name)
    metadata = robot_class.metadata
    if metadata is None:
        raise ValueError(f"No metadata found for model {model_name}")
    model_path.write_text(metadata.model_dump_json())
    return metadata