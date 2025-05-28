import io
import os
import time
import base64
import asyncio
import datetime
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
    ):

        super().__init__()
        self.robot = robot
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.connection = None
        self.session = None
        self.connected = asyncio.Event()

        self.combined_audio_buffer = []
        self.conversation_start_time = None

        self.debug_audio_dir = "debug_audio"
        os.makedirs(self.debug_audio_dir, exist_ok=True)

        self.tool_manager = ToolManager(robot=robot, api_key=openai_api_key)

        self.tool_manager.on(
            "set_volume", lambda volume: self.emit("set_volume", volume)
        )

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
                    self.save_combined_audio()
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

        if self.conversation_start_time is None:
            self.conversation_start_time = datetime.datetime.now()
        
        current_time = datetime.datetime.now()
        self.combined_audio_buffer.append((current_time, "input", audio_bytes))
            
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await connection.input_audio_buffer.append(audio=audio_b64)

    async def _handle_audio_delta(self, event):
        audio_bytes = base64.b64decode(event.delta)
        
        if self.conversation_start_time is None:
            self.conversation_start_time = datetime.datetime.now()
        
        current_time = datetime.datetime.now()
        self.combined_audio_buffer.append((current_time, "output", audio_bytes))
        
        self.emit("audio_to_play", audio_bytes)

    def save_combined_audio(self):
        if self.conversation_start_time is None or not self.combined_audio_buffer:
            return
            
        timestamp = self.conversation_start_time.strftime("%Y%m%d_%H%M%S")
        sorted_audio = sorted(self.combined_audio_buffer, key=lambda x: x[0])
        combined_audio = AudioSegment.empty()
        
        for _, audio_type, audio_bytes in sorted_audio:
            
            try:
                audio_segment = AudioSegment(
                    data=audio_bytes,
                    sample_width=2,  # 16-bit = 2 bytes
                    frame_rate=24000,  # 24kHz sample rate
                    channels=1  # mono
                )
                
                combined_audio += audio_segment
                    
            except Exception as e:
                print(f"Error processing {audio_type} audio chunk: {e}")
                continue
        
        if len(combined_audio) > 0:
            combined_filename = os.path.join(self.debug_audio_dir, f"conversation_{timestamp}.wav")
            combined_audio.export(combined_filename, format="wav")
    
    def reset_audio_buffers(self):
        self.combined_audio_buffer = []
        self.conversation_start_time = None
    
    def save_and_reset_audio(self):
        self.save_combined_audio()
        self.reset_audio_buffers()

    async def _handle_tool_call(self, conn, event):
        await self.tool_manager.handle_tool_call(event)

    def cancel_response(self):
        if self.connection:
            asyncio.create_task(
                self.connection.send({"type": "response.cancel"})
            )
