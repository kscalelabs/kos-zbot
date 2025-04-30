import json
import time
import base64
import tempfile
import subprocess
import os
from typing import Any, Dict, List
from pyee.asyncio import AsyncIOEventEmitter
from openai import OpenAI
import dotenv
import asyncio

dotenv.load_dotenv()


class ToolManager(AsyncIOEventEmitter):
    """Manages LLM tools for the voice system.

    This class handles the definition, registration, and execution of LLM tools.
    It manages the tool definitions and handles invoking the appropriate functions
    when tools are called by the LLM.

    Attributes:
        robot: Reference to the main robot instance
        connection: Active connection to OpenAI API

    Events emitted:
        - set_volume: When the volume tool is called
    """

    def __init__(self, robot=None, api_key=None):
        """Initialize the ToolManager.

        Args:
            robot: Reference to the main robot instance
            api_key: OpenAI API key for vision functionality
        """
        super().__init__()
        self.robot = robot
        self.connection = None
        # Initialize OpenAI client for vision API
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key must be provided either through constructor or OPENAI_API_KEY environment variable")
        from openai import AsyncOpenAI
        self.openai_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.openai.com/v1"
        )

    def set_connection(self, connection):
        """Set the OpenAI API connection.

        Args:
            connection: Active connection to OpenAI API
        """
        self.connection = connection

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get the tool definitions for the LLM.

        Returns:
            List of tool definitions in the format expected by OpenAI
        """
        return [
            {
                "type": "function",
                "name": "get_current_time",
                "description": "Get the current time of the day.",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "type": "function",
                "name": "set_volume",
                "description": "Set the volume of the robot's voice",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "volume": {
                            "type": "number",
                            "description": "Volume level between 0.0 (silent) and 1.0 (maximum)",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        }
                    },
                    "required": ["volume"],
                },
            },
            {
                "type": "function",
                "name": "describe_surroundings",
                "description": "Take a photo with the camera and describe what is visible in the surroundings",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

    async def handle_tool_call(self, event):
        """Handle a tool call from the LLM.

        Args:
            event: Tool call event from OpenAI API

        Returns:
            bool: True if the tool call was handled, False otherwise
        """
        if not self.connection:
            print("No connection available for tool call")
            return False

        handlers = {
            "get_current_time": self._handle_get_current_time,
            "set_volume": self._handle_set_volume,
            "describe_surroundings": self._handle_describe_surroundings,
        }

        handler = handlers.get(event.name)
        if handler:
            await handler(event)
            return True
        else:
            print(f"Unknown tool: {event.name}")
            return False

    def capture_jpeg_cli(self, width: int = 640, height: int = 480, warmup_ms: int = 500) -> bytes:
        """Capture a single JPEG image via libcamera-jpeg CLI in headless mode.
        Returns the raw JPEG bytes.
        """
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cmd = [
                "libcamera-jpeg",
                "-o", tmp.name,
                "-n",                # no preview, headless
                "--width", str(width),
                "--height", str(height),
                "-t", str(warmup_ms),
                "--nopreview",
                "--quality", "75"
            ]
            try:
                subprocess.run(cmd, check=True)
                tmp.seek(0)
                data = tmp.read()
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Camera capture failed: {e}")
            finally:
                os.remove(tmp.name)
            return data

    async def _handle_describe_surroundings(self, event):
        """Handle the describe_surroundings tool call.

        Args:
            event: Tool call event containing the request details
        """
        try:
            # Send immediate acknowledgment
            await self._create_tool_response(event.call_id, "Let me look...")
            
            # Capture and process image
            jpeg_bytes = self.capture_jpeg_cli()
            base64_image = base64.b64encode(jpeg_bytes).decode('utf-8')
            
            # Get description from Vision API
            response = await self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Describe this scene briefly, focusing only on the most important or interesting elements."},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=100,
                temperature=0.7
            )
            
            description = response.choices[0].message.content.strip()
            await self._create_tool_response(event.call_id, f"I see {description}")
            
        except Exception as e:
            await self._create_tool_response(event.call_id, f"Sorry, I had trouble processing the image: {str(e)}")

    async def _handle_get_current_time(self, event):
        """Handle the get_current_time tool call.

        Args:
            event: Tool call event
        """
        current_time = time.strftime("%I:%M %p")
        message = f"The current time is {current_time}."
        await self._create_tool_response(event.call_id, message)

    async def _handle_set_volume(self, event):
        """Handle the set_volume tool call.

        Args:
            event: Tool call event
        """
        args = json.loads(event.arguments)
        volume = float(args["volume"])

        self.emit("set_volume", volume)

        message = f"Volume has been set to {int(volume * 100)}%"
        await self._create_tool_response(event.call_id, message)

    async def _create_tool_response(self, call_id, output):
        """Create a response for a tool call.

        Args:
            call_id (str): ID of the tool call
            output (str): Output of the tool call
        """
        if not self.connection:
            print("No connection available for tool response")
            return

        await self.connection.conversation.item.create(
            item={
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )
