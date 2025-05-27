import io
import os
import time
import base64
import asyncio
from pydub import AudioSegment
from openai import AsyncOpenAI
from .tools import ToolManager
from pyee.asyncio import AsyncIOEventEmitter

SYSTEM_PROMPT = """You are the Z-Bot, an open-source humanoid robot by K-Scale Labs. Communicate as the robot itself, never breaking character or referencing anything beyond this role. Be as concise as possible. You always speak in English unless explicitly asked otherwise"""

class AudioProcessor(AsyncIOEventEmitter):

    def __init__(
        self,
        openai_api_key,
        robot=None,
        debug=False,
    ):

        super().__init__()
        self.robot = robot
        self.debug = debug
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.connection = None
        self.session = None
        self.connected = asyncio.Event()

        self.tool_manager = ToolManager(robot=robot, api_key=openai_api_key)

        self.tool_manager.on(
            "set_volume", lambda volume: self.emit("set_volume", volume)
        )

        if debug:
            os.makedirs("debug_audio", exist_ok=True)
            os.makedirs("debug_audio/input", exist_ok=True)
            os.makedirs("debug_audio/output", exist_ok=True)

    async def connect(self):
        async with self.client.beta.realtime.connect(
            model="gpt-4o-realtime-preview"
        ) as conn:
            self.connection = conn
            self.connected.set()

            self.tool_manager.set_connection(conn)

            print("Connected to OpenAI")

            async for event in conn:
                if event.type == "session.created":
                    print("Session created")
                    await self._handle_session_created(conn)
                elif event.type == "session.updated":
                    self.session = event.session
                elif event.type == "response.audio.delta":
                    await self._handle_audio_delta(event)
                elif event.type == "response.done":
                    self.emit("processing_complete")
                elif event.type == "response.function_call_arguments.done":
                    await self._handle_tool_call(conn, event)
                    await conn.response.create()
                elif event.type == "error":
                    print(event.error)

    async def _handle_session_created(self, conn):
        self.session = conn.session

        tools = self.tool_manager.get_tool_definitions()

        await conn.session.update(
            session={
                "voice": "alloy",
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.7,
                },
                "tools": tools,
                "instructions": SYSTEM_PROMPT,
            }
        )

        self.emit("session_ready")

    async def process_audio(self, audio_bytes):
        if not self.connected.is_set():
            print("Not connected to OpenAI API")
            return

        connection = self.connection
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await connection.input_audio_buffer.append(audio=audio_b64)

    async def _handle_audio_delta(self, event):
        audio_bytes = base64.b64decode(event.delta)
        self.emit("audio_to_play", audio_bytes)

    async def _handle_tool_call(self, conn, event):
        await self.tool_manager.handle_tool_call(event)

    def cancel_response(self):
        if self.connection:
            asyncio.create_task(
                self.connection.send({"type": "response.cancel"})
            )
