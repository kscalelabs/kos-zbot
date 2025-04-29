import io
import os
import time
import base64
import asyncio
from pydub import AudioSegment
from openai import AsyncOpenAI
from .tools import ToolManager
from pyee.asyncio import AsyncIOEventEmitter

# OpenAI system prompt
SYSTEM_PROMPT = """You are ZBot, a friendly and helpful voice assistant robot. You have a warm, engaging personality and always aim to be helpful while maintaining a natural conversation flow. 

Key characteristics:
- You are a robot named ZBot, and you should acknowledge this in your first interaction
- You should mention that you're here to help the user today
- You speak in a friendly, conversational tone
- You're concise and clear in your responses
- You always speak in English unless explicitly asked otherwise
- You can show personality while staying professional
- You're knowledgeable but humble
- You can make appropriate jokes or light-hearted comments when appropriate
- You're always ready to help with tasks or answer questions

Remember to:
- Keep responses brief and to the point
- Use natural language and contractions
- Be friendly but not overly casual
- Show enthusiasm when appropriate
- Admit when you don't know something
- Maintain a helpful and positive attitude
- Always start your first interaction with: "Hello! I'm ZBot, your personal robot. I'm here to help you today. How can I assist you?" """

# Available voices for the assistant
AVAILABLE_VOICES = [
    "alloy",    # A clear, natural voice
    "echo",     # A warm, friendly voice
    "fable",    # A smooth, professional voice
    "onyx",     # A deep, authoritative voice
    "nova",     # A bright, energetic voice
    "shimmer",  # A soft, gentle voice
]

# Default voice selection
DEFAULT_VOICE = "echo"  # Changed from "ash" to "nova" for a more robot-like voice

class AudioProcessor(AsyncIOEventEmitter):
    """Processes audio through OpenAI's API.

    This class handles the communication with OpenAI's API for speech processing.
    It acts as the bridge between the AudioRecorder and AudioPlayer components.

    Attributes:
        client (AsyncOpenAI): OpenAI API client
        connection (AsyncRealtimeConnection): Active connection to OpenAI API
        session: Current voice session
        robot: Reference to the main robot instance
        connected (asyncio.Event): Indicates active API connection
        debug (bool): Enable debug mode
        tool_manager (ToolManager): Manages LLM tools

    Events emitted:
        - audio_to_play: When audio is ready to be played
        - processing_complete: When processing is complete
        - set_volume: When the volume should be changed
    """

    def __init__(self, openai_api_key, robot=None, debug=False):
        """Initialize the AudioProcessor.

        Args:
            openai_api_key (str): OpenAI API key
            robot: Reference to the main robot instance
            debug (bool): Enable debug mode
        """
        super().__init__()
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.connection = None
        self.session = None
        self.robot = robot
        self.connected = asyncio.Event()
        self.debug = debug

        self.tool_manager = ToolManager(robot=robot)

        self.tool_manager.on(
            "set_volume", lambda volume: self.emit("set_volume", volume)
        )

        if debug:
            os.makedirs("debug_audio", exist_ok=True)
            os.makedirs("debug_audio/input", exist_ok=True)
            os.makedirs("debug_audio/output", exist_ok=True)

    async def connect(self):
        """Connect to OpenAI's API and start processing loop."""
        async with self.client.beta.realtime.connect(
            model="gpt-4o-mini-realtime-preview"
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
        """Handle OpenAI session creation and setup.

        Args:
            conn (AsyncRealtimeConnection): Active connection to OpenAI API
        """
        self.session = conn.session

        tools = self.tool_manager.get_tool_definitions()

        await conn.session.update(
            session={
                "voice": DEFAULT_VOICE,
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
        """Process audio data through OpenAI API.

        Args:
            audio_bytes (bytes): Audio data to process
        """
        if not self.connected.is_set():
            print("Not connected to OpenAI API")
            return

        connection = self.connection
        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        await connection.input_audio_buffer.append(audio=audio_b64)

    async def _handle_audio_delta(self, event):
        """Process incoming audio chunks from OpenAI.

        Args:
            event: OpenAI audio delta event with audio data
        """
        audio_bytes = base64.b64decode(event.delta)
        self.emit("audio_to_play", audio_bytes)

    async def _handle_tool_call(self, conn, event):
        """Handle tool calls from the LLM.

        Args:
            conn (AsyncRealtimeConnection): Active connection to OpenAI API
            event: Tool call event
        """
        await self.tool_manager.handle_tool_call(event)

    def _get_timestamp_filename(self, prefix):
        """Generate a timestamp-based filename for debug audio.

        Args:
            prefix (str): Prefix for filename ('input' or 'output')

        Returns:
            str: Formatted filename
        """
        timestamp = int(time.time() * 1000)
        return f"debug_audio/{prefix}/{timestamp}.wav"

    def cancel_response(self):
        """Cancel the current response."""
        if self.connection:
            asyncio.create_task(
                self.connection.send({"type": "response.cancel"})
            )
