import json
import time
from typing import Any, Dict, List
from pyee.asyncio import AsyncIOEventEmitter


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

    def __init__(self, robot=None):
        """Initialize the ToolManager.

        Args:
            robot: Reference to the main robot instance
        """
        super().__init__()
        self.robot = robot
        self.connection = None

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
        }

        handler = handlers.get(event.name)
        if handler:
            await handler(event)
            return True
        else:
            print(f"Unknown tool: {event.name}")
            return False

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
