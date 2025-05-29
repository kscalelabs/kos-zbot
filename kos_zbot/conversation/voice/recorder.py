import os
import io
import time
import asyncio
import sounddevice as sd
import concurrent.futures
from pydub import AudioSegment
from .audio import CHANNELS, SAMPLE_RATE
from pyee.asyncio import AsyncIOEventEmitter


class AudioRecorder(AsyncIOEventEmitter):

    def __init__(self, microphone_id=None, debug=False):
        super().__init__()
        self.microphone_id = microphone_id
        self.should_record = asyncio.Event()
        self.debug = debug
        self.debug_mic_buffer = io.BytesIO() if debug else None
        self.input_sample_rate = SAMPLE_RATE

        self.audio_thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="audio_recorder"
        )

    async def start(self):
        self._main_loop = asyncio.get_running_loop()
        asyncio.create_task(self._start_recording())

    async def _start_recording(self):
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.audio_thread_pool, self._capture_audio
            )
        except Exception as e:
            print(f"Error in mic audio capture: {e}")

    def _capture_audio(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        devices = sd.query_devices()
        input_devices = [d for d in devices if d["max_input_channels"] > 0]

        device = self.microphone_id
        try:
            if device is not None:
                device_info = sd.query_devices(device, "input")
                print(f"Using specified input device: {device_info['name']}")
            else:
                device_info = sd.query_devices(None, "input")
                device = device_info["index"]
                print(f"Using default input device: {device_info['name']}")
        except Exception as e:
            print(f"Error using specified input device {device}: {e}")
            device_info = sd.query_devices(None, "input")
            device = device_info["index"]
            print(
                f"Falling back to default input device: {device_info['name']}"
            )

        actual_input_sr = int(device_info["default_samplerate"])
        self.input_sample_rate = actual_input_sr
        print(
            f"Using input sample rate {actual_input_sr} instead of {SAMPLE_RATE}"
        )

        read_size = int(actual_input_sr * 0.1)

        stream = sd.InputStream(
            device=device,
            channels=CHANNELS,
            samplerate=actual_input_sr,
            dtype="int16",
            blocksize=read_size,
            latency="high",
            callback=None,
        )
        stream.start()

        try:
            while True:
                try:
                    data, _ = stream.read(read_size)
                except sd.PortAudioError as e:
                    print(f"PortAudio error: {e}")
                    time.sleep(0.1)
                    continue

                if self.should_record.is_set():
                    asyncio.run_coroutine_threadsafe(
                        self._process_captured_audio(data), self._main_loop
                    )
                else:
                    time.sleep(0.01)
        finally:
            stream.stop()
            stream.close()

    async def _process_captured_audio(self, data):
        raw_bytes = data.tobytes()

        if self.input_sample_rate != SAMPLE_RATE:
            segment = AudioSegment(
                data=raw_bytes,
                sample_width=2,
                frame_rate=self.input_sample_rate,
                channels=CHANNELS,
            )
            segment = segment.set_frame_rate(SAMPLE_RATE)
            audio_bytes = segment.raw_data
        else:
            audio_bytes = raw_bytes

        if self.debug and self.debug_mic_buffer is not None:
            self.debug_mic_buffer.write(audio_bytes)

        self.emit(
            "audio_captured",
            {"audio_bytes": audio_bytes, "sample_rate": SAMPLE_RATE},
        )

    def start_recording(self):
        self.should_record.set()

    def stop_recording(self):
        self.should_record.clear()

    def close(self):
        self.stop_recording()
        self.audio_thread_pool.shutdown()
