import os
import dotenv
import asyncio
from .config import load_config, get_microphone_id, get_speaker_id
from .voice.audio import AudioPlayer
from .voice.recorder import AudioRecorder
from .voice.processor import AudioProcessor


class Voice:

    def __init__(self, openai_api_key, config=None):
        if config is None:
            self.config = load_config()
        else:
            self.config = config

        microphone_id = get_microphone_id(self.config)
        speaker_id = get_speaker_id(self.config)
        self.volume = self.config.get("volume", 0.35)

        self.recorder = AudioRecorder(microphone_id=microphone_id)
        self.processor = AudioProcessor(
            openai_api_key=openai_api_key,
            robot=self,
        )
        self.player = AudioPlayer(device_id=speaker_id, volume=self.volume)

        self._setup_component_connections()

    def _setup_component_connections(self):
        # Recorder -> Processor
        self.recorder.on("audio_captured", self._handle_audio_captured)

        # Processor -> Player
        self.processor.on("audio_to_play", self._handle_audio_to_play)
        self.processor.on(
            "processing_complete", self._handle_processing_complete
        )
        self.processor.on(
            "session_ready", lambda: self.recorder.start_recording()
        )

        # Player -> Voice
        self.player.on("queue_empty", self._handle_queue_empty)

    async def _handle_audio_captured(self, data):
        await self.processor.process_audio(data["audio_bytes"])

    def _handle_audio_to_play(self, audio_bytes):
        self.player.add_data(audio_bytes)
        self.recorder.stop_recording()

    def _handle_processing_complete(self):
        asyncio.create_task(self._wait_for_audio_completion())

    def _handle_queue_empty(self):
        self.recorder.start_recording()

    async def _wait_for_audio_completion(self):
        await self.player.wait_for_queue_empty()
        await asyncio.sleep(0.1)
        self.recorder.start_recording()

    async def run(self):
        await self.recorder.start()
        queue_monitor_task = asyncio.create_task(
            self.player.start_queue_monitor()
        )

        await self.processor.connect()
        queue_monitor_task.cancel()


async def run_voice_system(openai_api_key=None, config=None):
    if openai_api_key is None:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable."
            )

    print("\nInitializing voice system...")
    voice = Voice(openai_api_key=openai_api_key, config=config)

    await voice.run()


if __name__ == "__main__":
    dotenv.load_dotenv()
    asyncio.run(run_voice_system())
