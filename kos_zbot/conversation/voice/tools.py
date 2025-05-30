import os
import json
import time
import base64
import asyncio
import tempfile
import subprocess
from openai import AsyncOpenAI
from typing import Any, Dict, List

from kos_zbot.conversation.animation import AnimationController

class ToolManager:

    def __init__(self, robot=None, openai_api_key=None):
        super().__init__()
        self.robot = robot
        self.connection = None
        self.tools = {} 
        self.motion_controller = AnimationController()

        self.openai_client = AsyncOpenAI(
            api_key=openai_api_key,
            base_url="https://api.openai.com/v1"
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

    def capture_jpeg_cli(self, width: int = 640, height: int = 480, warmup_ms: int = 500) -> bytes:
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
        try:
            await self._create_tool_response(event.call_id, "Let me look...")
            
            jpeg_bytes = self.capture_jpeg_cli()
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
            await self._create_tool_response(event.call_id, f"Sorry, I had trouble processing the image: {str(e)}")

    async def _handle_get_current_time(self, event):
        current_time = time.strftime("%I:%M %p")
        message = f"The current time is {current_time}."
        await self._create_tool_response(event.call_id, message)


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

    async def _handle_wave_hand(self, event):
        try:
            HAND_ACTUATOR_IDS = [11, 12, 13]
            
            HAND_WAVE_CONFIG = {
                "kos_ip": "127.0.0.1",
                "amplitude": 15.0,
                "frequency": 1.5,
                "duration": 3.0,
                "sample_rate": 50.0,
                "start_pos": 0.0,
                "sync_all": False,
                "wave_patterns": {
                    "shoulder_pitch": {
                        "actuators": [11],
                        "amplitude": 5.0,
                        "frequency": 0.25,
                        "phase_offset": 0.0,
                        "freq_multiplier": 1.0,
                        "start_pos": 0,
                        "position_offset": 0.0,
                    },
                    "shoulder_roll": {
                        "actuators": [12],
                        "amplitude": 10.0,
                        "frequency": 0.75,
                        "phase_offset": 0.0,
                        "freq_multiplier": 1.0,
                        "start_pos": 120,
                        "position_offset": 0.0,
                    },
                    "elbow_roll": {
                        "actuators": [13],
                        "amplitude": 20.0,
                        "frequency": 1,
                        "phase_offset": 90.0,
                        "freq_multiplier": 1.0,
                        "start_pos": -60,
                        "position_offset": 0.0,
                    },
                },
                "kp": 15.0,
                "kd": 3.0,
                "ki": 0.0,
                "max_torque": 50.0,
                "acceleration": 500.0,
                "torque_enabled": True,
            }
            
            await self._create_tool_response(event.call_id, "Waving hello!")
            self.motion_controller.wave(HAND_ACTUATOR_IDS, **HAND_WAVE_CONFIG)
            #asyncio.create_task(run_sine_test(HAND_ACTUATOR_IDS, **HAND_WAVE_CONFIG))
            
        except Exception as e:
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't wave: {str(e)}")

    async def _handle_salute(self, event):
        try:
            HAND_ACTUATOR_IDS = [21, 22, 23, 24]

            SALUTE_CONFIG = {
                "kos_ip": "127.0.0.1",
                "squeeze_duration": 5.0,
            }

            await self._create_tool_response(event.call_id, "At attention!")
            #asyncio.create_task(salute_func(HAND_ACTUATOR_IDS, **SALUTE_CONFIG))
            self.motion_controller.salute(HAND_ACTUATOR_IDS, **SALUTE_CONFIG)
        except Exception as e:
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't salute: {str(e)}")


            
         

