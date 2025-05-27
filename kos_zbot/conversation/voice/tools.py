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
from kos_zbot.tests.hello_wave import run_sine_test

dotenv.load_dotenv()


class ToolManager(AsyncIOEventEmitter):

    def __init__(self, robot=None, api_key=None):
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
        self.connection = connection

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
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
           
            {
                "type": "function",
                "name": "wave_hand",
                "description": "Physically wave the robot's hand. Use this for greetings (hello, hi, hey, good morning, good afternoon, good evening) and departures (goodbye, bye, see you later).",
                "parameters": {"type": "object", "properties": {}},
            },

            {
                "type": "function",
                "name": "salute",
                "description": "Physically salute the robot's hand. Use this for formal greetings and patriotic situations (at attention, salute, etc).",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

    async def handle_tool_call(self, event):
        if not self.connection:
            print("No connection available for tool call")
            return False

        handlers = {
            "get_current_time": self._handle_get_current_time,
            "set_volume": self._handle_set_volume,
            "describe_surroundings": self._handle_describe_surroundings,
            "wave_hand": self._handle_wave_hand,
            "salute": self._handle_salute,
        }

        handler = handlers.get(event.name)
        if handler:
            await handler(event)
            return True
        else:
            print(f"Unknown tool: {event.name}")
            return False

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
        current_time = time.strftime("%I:%M %p")
        message = f"The current time is {current_time}."
        await self._create_tool_response(event.call_id, message)

    async def _handle_set_volume(self, event):
        args = json.loads(event.arguments)
        volume = float(args["volume"])

        self.emit("set_volume", volume)

        message = f"Volume has been set to {int(volume * 100)}%"
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
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))            
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
                        "start_pos": 120.0,
                        "position_offset": 0.0,
                    },
                    "shoulder_roll": {
                        "actuators": [12],
                        "amplitude": 10.0,
                        "frequency": 0.75,
                        "phase_offset": 0.0,
                        "freq_multiplier": 1.0,
                        "start_pos": 0.0,
                        "position_offset": 0.0,
                    },
                    "elbow_roll": {
                        "actuators": [13],
                        "amplitude": 10.0,
                        "frequency": 1,
                        "phase_offset": 90.0,
                        "freq_multiplier": 1.0,
                        "start_pos": 0.0,
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
            
            asyncio.create_task(run_sine_test(HAND_ACTUATOR_IDS, **HAND_WAVE_CONFIG))
            
        except Exception as e:
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't wave: {str(e)}")

    async def _handle_salute(self, event):
        try:
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
            from kos_zbot.scripts.salute import salute as salute_func

            HAND_ACTUATOR_IDS = [21, 22, 23, 24]

            SALUTE_CONFIG = {
                "kos_ip": "127.0.0.1",
                "squeeze_duration": 5.0,
            }

            await self._create_tool_response(event.call_id, "At attention!")
            
            asyncio.create_task(salute_func(HAND_ACTUATOR_IDS, **SALUTE_CONFIG))
            
        except Exception as e:
            await self._create_tool_response(event.call_id, f"Sorry, I couldn't salute: {str(e)}")


            
         

