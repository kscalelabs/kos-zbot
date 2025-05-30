from __future__ import annotations

"""
This code is directly ported from https://github.com/openai/openai-python/blob/main/examples/realtime/audio_util.py
"""

import io
import pyaudio
import asyncio
import threading
import numpy as np
import sounddevice as sd
import platform
import logging
from pydub import AudioSegment
from pyee.asyncio import AsyncIOEventEmitter

# Configure logging
logger = logging.getLogger(__name__)

CHANNELS = 1
SAMPLE_RATE = 24000
FORMAT = pyaudio.paInt16
CHUNK_LENGTH_S = 0.1


def audio_to_pcm16_base64(audio_bytes: bytes) -> bytes:

    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    print(
        f"Loaded audio: {audio.frame_rate=} {audio.channels=} {audio.sample_width=} {audio.frame_width=}"
    )

    pcm_audio = (
        audio.set_frame_rate(SAMPLE_RATE)
        .set_channels(CHANNELS)
        .set_sample_width(2)
        .raw_data
    )
    return pcm_audio


class AudioPlayer(AsyncIOEventEmitter):
    """Handles audio playback using a separate thread.

    This class manages playback of audio data using sounddevice in a non-blocking way.
    It runs the actual audio output in a separate thread using callback-based playback.

    Attributes:
        queue (list): Queue of audio chunks to play
        lock (threading.Lock): Thread lock for queue access
        volume (float): Playback volume (0.0 to 1.0)
        buffer_size (int): Size of audio buffer
        min_buffer_fill (float): Minimum buffer fill level before starting playback
        input_rate (int): Sample rate of input audio
        output_rate (int): Sample rate of output device
        stream (sd.OutputStream): Audio output stream
        playing (bool): Whether audio is currently playing
        device_id (int): ID of the output device to use

    Events emitted:
        - queue_empty: When the audio queue becomes empty
        - playback_started: When playback starts
        - playback_stopped: When playback stops
    """

    def __init__(self, device_id=None, volume=0.15):
        """Initialize the audio player.

        Args:
            device_id (int, optional): ID of the output device to use. Defaults to None (system default).
            volume (float, optional): Initial volume level (0.0 to 1.0). Defaults to 0.15.
        """
        super().__init__()

        self.queue = []
        self.lock = threading.Lock()
        self.volume = max(0.0, min(1.0, volume))
        self.buffer_size = 4096
        self.min_buffer_fill = 0.5
        self.device_id = device_id

        self._setup_audio_device()

        self._queue_check_task = None

    def _setup_audio_device(self):
        """Set up the audio output device."""

        try:
            if self.device_id is not None:
                try:
                    # Validate that the device exists and has output channels
                    device = sd.query_devices(self.device_id)
                    if device["max_output_channels"] > 0:
                        device_id = self.device_id
                        logger.info(f"Using specified output device ID {device_id}: {device['name']}")
                    else:
                        logger.warning(f"Device ID {self.device_id} has no output channels")
                        raise ValueError(f"Device {self.device_id} is not an output device")
                except Exception as e:
                    logger.warning(f"Could not use specified device ID {self.device_id}: {e}")
                    logger.info("Falling back to default output device")
                    device_id = None
            
            if device_id is None:
                # Use system default output device
                default_device = sd.query_devices(kind="output")
                device_id = default_device["index"] if "index" in default_device else None
                logger.info(f"Using default output device: {default_device['name']}")

            # Get device info for sample rate
            if device_id is not None:
                device = sd.query_devices(device_id)
                supported_rates = device.get("default_samplerate")
                self.input_rate = SAMPLE_RATE
                self.output_rate = int(supported_rates) if supported_rates else SAMPLE_RATE
                logger.info(f"Sample rate: {self.output_rate} Hz")
            else:
                logger.warning("No valid output device found, using default sample rate")
                self.input_rate = SAMPLE_RATE
                self.output_rate = SAMPLE_RATE

        except Exception as e:
            logger.error(f"Audio setup error: {e}")
            device_id = None
            self.input_rate = SAMPLE_RATE
            self.output_rate = SAMPLE_RATE

        try:
            self.stream = sd.OutputStream(
                device=device_id,
                callback=self._audio_callback,
                samplerate=self.output_rate,
                channels=CHANNELS,
                dtype=np.int16,
                blocksize=int(CHUNK_LENGTH_S * self.output_rate),
            )
            self.playing = False
            self._frame_count = 0
            
            if device_id is not None:
                final_device = sd.query_devices(device_id)
                logger.info(f"Successfully initialized audio output on: {final_device['name']}")
            else:
                logger.info("Successfully initialized audio output on system default device")
                
        except Exception as e:
            logger.error(f"Warning: Could not initialize audio output: {e}")
            self.stream = None
            self.playing = False
            self._frame_count = 0

    def _audio_callback(self, outdata, frames, time, status):
        """Audio output callback function.

        This is called by sounddevice to get the next chunk of audio data.

        Args:
            outdata: Output buffer to fill with audio data
            frames: Number of frames to fill
            time: Time info (unused)
            status: Status info (unused)
        """
        with self.lock:
            data = np.empty(0, dtype=np.int16)

            while len(data) < frames and len(self.queue) > 0:
                item = self.queue.pop(0)
                frames_needed = frames - len(data)
                data = np.concatenate((data, item[:frames_needed]))
                if len(item) > frames_needed:
                    self.queue.insert(0, item[frames_needed:])

            self._frame_count += len(data)

            if len(data) < frames:
                data = np.concatenate(
                    (data, np.zeros(frames - len(data), dtype=np.int16))
                )

                if len(self.queue) == 0:
                    self._emit_queue_empty_soon = True

            data = (data * self.volume).astype(np.int16)

            outdata[:] = data.reshape(-1, 1)

    async def start_queue_monitor(self):
        """Start monitoring the queue for empty state.

        This should be called once when the player is started.
        """
        self._emit_queue_empty_soon = False

        while True:
            await asyncio.sleep(0.1)

            if getattr(self, "_emit_queue_empty_soon", False):
                self._emit_queue_empty_soon = False
                self.emit("queue_empty")

    def add_data(self, data: bytes):
        """Add audio data to the playback queue.

        Args:
            data (bytes): Raw audio data (PCM)
        """
        if self.stream is None:
            return

        with self.lock:
            if self.input_rate != self.output_rate:
                audio_segment = AudioSegment(
                    data=data,
                    sample_width=2,
                    frame_rate=self.input_rate,
                    channels=CHANNELS,
                )
                resampled = audio_segment.set_frame_rate(self.output_rate)
                np_data = np.frombuffer(resampled.raw_data, dtype=np.int16)
            else:
                np_data = np.frombuffer(data, dtype=np.int16)

            self.queue.append(np_data)
            buffer_fill = sum(len(x) for x in self.queue) / self.buffer_size

            if not self.playing and buffer_fill >= self.min_buffer_fill:
                self.start()

    def start(self):
        """Start audio playback."""
        if self.stream is None:
            print("Warning: Audio output not available")
            return

        self.playing = True
        self.stream.start()
        self.emit("playback_started")

    def stop(self):
        """Stop audio playback and clear queue."""
        if self.stream is None:
            return

        self.playing = False
        self.stream.stop()

        with self.lock:
            self.queue = []

        self.emit("playback_stopped")

    def pause(self):
        """Pause audio playback without clearing queue."""
        if self.stream is None or not self.playing:
            return

        self.playing = False
        self.stream.stop()
        self.emit("playback_stopped")

    def resume(self):
        """Resume audio playback if paused."""
        if self.stream is None or self.playing:
            return

        self.playing = True
        self.stream.start()
        self.emit("playback_started")

    def terminate(self):
        """Close audio stream and release resources."""
        if self.stream is not None:
            self.stop()
            self.stream.close()
            self.stream = None

    def get_queue_length(self):
        """Get the current length of the audio queue.

        Returns:
            int: Number of chunks in queue
        """
        with self.lock:
            return len(self.queue)

    def is_queue_empty(self):
        """Check if the audio queue is empty.

        Returns:
            bool: True if queue is empty, False otherwise
        """
        with self.lock:
            return len(self.queue) == 0

    async def wait_for_queue_empty(self):
        """Wait until the audio queue is empty.

        This is useful to ensure all audio has been played before proceeding.
        """
        while not self.is_queue_empty():
            await asyncio.sleep(0.1)

AudioPlayerAsync = AudioPlayer
