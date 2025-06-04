import time
import json
import base64
from openai import AsyncOpenAI
from typing import Any, Dict, List
from pyee.asyncio import AsyncIOEventEmitter
from kos_zbot.conversation.tools.animation import AnimationController
from kos_zbot.conversation.tools.utils import capture_jpeg_cli, get_wave_hand_config, get_salute_config, get_robot_status


class ToolManager(AsyncIOEventEmitter):

    def __init__(self, openai_api_key=None):
        super().__init__()
        self.connection = None
        self.tools = {} 
        self.motion_controller = AnimationController()

        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url="https://api.openai.com/v1"
        )

        self.register_tool(
            "set_volume",
            "Set the volume of the robot's voice. The volume is a float between 0.0 and 1.0. Convert the volume to a float between 0.0 and 1.0 if provided as a percentage.",
            {
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
            self._handle_set_volume,
        )

        self.register_tool(
            "get_current_time",
            "Get the current time of the day.",
            {"type": "object", "properties": {}},
            self._handle_get_current_time
        )
        self.register_tool(
            "describe_surroundings",
            "Describe the environment you see around you. Use this if the user asks what you see, where you are, what's around you, to look around, or anything similar.",
            {"type": "object", "properties": {}},
            self._handle_describe_surroundings
        )
        self.register_tool(
            "wave_hand",
            "Physically wave the robot's hand. Use this for greetings and departures.",
            {"type": "object", "properties": {}},
            self._handle_wave_hand
        )
        self.register_tool(
            "salute",
            "Physically salute the robot's hand for formal greetings and patriotic situations.",
            {"type": "object", "properties": {}},
            self._handle_salute
        )
        self.register_tool(
            "get_status",
            "Get the current status of the robot including actuators, sensors, and system health. Use this when asked about robot status, actuator status, actuator positions, IMU status, accelerometer status, gyroscope status, magnetometer status, and system performance. The tool will provide you with a detailed status report. Ensure you report all the information you can get from the robot.",
            {"type": "object", "properties": {}},
            self._handle_get_status
        )

    def set_connection(self, connection):
        self.connection = connection

    def register_tool(self, name: str, description: str, parameters: Dict[str, Any], handler):
        self.tools[name] = {"description": description, "parameters": parameters, "handler": handler}

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        definitions = []
        for name, info in self.tools.items():
            definitions.append({
                "type": "function",
                "name": name,
                "description": info["description"],
                "parameters": info["parameters"]
            })
        return definitions

    async def handle_tool_call(self, event):
        if not self.connection:
            print("No connection available for tool call")
            return False

        tool_info = self.tools.get(event.name)
        if not tool_info:
            print(f"Unknown tool: {event.name}")
            return False

        print(f"Tool call: {event.name}")

        handler = tool_info["handler"]
        await handler(event)
        return True
    
    async def _create_tool_response(self, call_id, output):
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
        
    async def _handle_set_volume(self, event):
        try:
            args = json.loads(event.arguments)
            volume = float(args["volume"])
            self.emit("set_volume", volume)
            await self._create_tool_response(event.call_id, f"Volume set to {volume}")
        except Exception as e:
            print(e)
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't set the volume: {str(e)}")

    async def _handle_describe_surroundings(self, event):
        try:
            await self._create_tool_response(event.call_id, "Let me look...")

            jpeg_bytes = capture_jpeg_cli()
            base64_image = base64.b64encode(jpeg_bytes).decode('utf-8')

            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
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
            print(e)
            await self._create_tool_response(event.call_id, f"Sorry, I had trouble processing the image: {str(e)}")

    async def _handle_get_current_time(self, event):
        current_time = time.strftime("%I:%M %p")
        message = f"The current time is {current_time}."
        await self._create_tool_response(event.call_id, message)

    async def _handle_wave_hand(self, event):
        try:
            await self._create_tool_response(event.call_id, "Waving hello!")
            
            wave_config = get_wave_hand_config()
            self.motion_controller.play("wave", wave_config["actuator_ids"], **wave_config["config"])
        except Exception as e:
            print(e)
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't wave: {str(e)}")

    async def _handle_salute(self, event):
        try:
            await self._create_tool_response(event.call_id, "At attention!")
            
            salute_config = get_salute_config()
            self.motion_controller.play("salute", salute_config["actuator_ids"], **salute_config["config"])
        except Exception as e:
            print(e)
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't salute: {str(e)}")

    async def _handle_get_status(self, event):
        try:
            await self._create_tool_response(event.call_id, "Let me check my current status...")
            
            status_info = await get_robot_status()
            await self._create_tool_response(event.call_id, status_info)
        except Exception as e:
            print(f"Status check error: {e}")
            await self._create_tool_response(event.call_id, "I'm having some difficulty checking my status right now, but I seem to be functioning normally for our conversation.")
