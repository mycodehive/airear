"""Bounded WASAPI loopback capture and a paced, continuous Opus-ready track.

PortAudio owns its callback thread; the asyncio consumer never blocks on a device.
Device errors produce silence while the capture worker attempts recovery.
"""
from __future__ import annotations

import asyncio
from collections import deque
from fractions import Fraction
import importlib
import logging
import threading
import time

import av
import numpy as np
from aiortc import AudioStreamTrack

LOG = logging.getLogger(__name__)
RATE = 48_000
SAMPLES = 960


def apply_gain(samples: np.ndarray, gain: float, muted: bool = False) -> np.ndarray:
    """Apply independent transmit gain with a block peak limiter (no int wrap)."""
    if muted:
        return np.zeros(samples.shape, dtype=np.int16)
    values = samples.astype(np.float32) * max(0.0, min(2.0, float(gain)))
    peak = float(np.max(np.abs(values))) if values.size else 0.0
    if peak > 32700:
        values *= 32700 / peak
    return np.clip(values, -32700, 32700).astype(np.int16)


class AudioEngine:
    """One capture source, shared by all receivers through an unbuffered relay."""

    def __init__(self) -> None:
        self.gain = 1.0
        self.muted = False
        self.level = 0.0
        self.error = ""
        self.device_id: int | None = None
        self._selected_name: str | None = None
        self._device_names: dict[int, str] = {}
        self._selection_generation = 0
        self._poll_interval = 0.2
        self._retry_interval = 2.0
        self._default_check_interval = 2.0
        self._packets: deque[tuple[bytes, int, int]] = deque(maxlen=4)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._reopen = threading.Event()
        self._thread: threading.Thread | None = None
        self._track: LoopbackTrack | None = None

    @staticmethod
    def _backend():
        # Windows-only dependency: importing the rest of the application is safe on CI.
        return importlib.import_module("pyaudiowpatch")

    def devices(self) -> list[dict]:
        try:
            module = self._backend()
            with module.PyAudio() as audio:
                try:
                    default = int(audio.get_default_wasapi_loopback()["index"])
                except (OSError, ValueError):
                    default = -1
                result = [
                    {
                        "id": int(device["index"]),
                        "name": device["name"],
                        "virtual": any(s in device["name"].lower() for s in ("vb-audio", "cable input", "voicemeeter")),
                        "default": int(device["index"]) == default,
                    }
                    for device in audio.get_loopback_device_info_generator()
                    if device["maxInputChannels"] > 0
                ]
                with self._lock:
                    self._device_names = {d["id"]: d["name"] for d in result}
                return result
        except (ImportError, OSError, ValueError) as exc:
            self.error = f"오디오 장치 조회 실패: {exc}"
            return []

    def select(self, device_id: int | None) -> None:
        with self._lock:
            self.device_id = device_id
            self._selected_name = self._device_names.get(device_id)
            self._selection_generation += 1
            self._packets.clear()
        self._reopen.set()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._reopen.clear()
        self._thread = threading.Thread(target=self._capture, name="WASAPI capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._reopen.set()
        if self._thread:
            self._thread.join(timeout=4)
        with self._lock:
            self._packets.clear()
        self.level = 0.0
        if self._track is not None:
            self._track.stop()
            self._track = None

    def track(self) -> AudioStreamTrack:
        if self._track is None or self._track.readyState == "ended":
            self._track = LoopbackTrack(self)
        return self._track

    def _enqueue(self, data: bytes, rate: int, channels: int) -> None:
        with self._lock:
            self._packets.append((data, rate, channels))

    def _take(self):
        with self._lock:
            # Favor current audio after a slow consumer instead of replaying stale buffers.
            while len(self._packets) > 2:
                self._packets.popleft()
            return self._packets.popleft() if self._packets else None

    def _capture(self) -> None:
        while not self._stop.is_set():
            stream = None
            audio = None
            try:
                module = self._backend()
                audio = module.PyAudio()
                with self._lock:
                    selected = self.device_id
                    selected_name = self._selected_name
                    generation = self._selection_generation
                if selected is None:
                    device = audio.get_default_wasapi_loopback()
                elif selected_name is not None:
                    matches = [d for d in audio.get_loopback_device_info_generator()
                               if d["name"] == selected_name and d["maxInputChannels"] > 0]
                    if not matches:
                        raise OSError(f"선택한 장치가 연결되지 않았습니다: {selected_name}")
                    # A reconnected endpoint may have a new PortAudio index.
                    device = next((d for d in matches if d["index"] == selected), matches[0])
                else:
                    device = audio.get_device_info_by_index(selected)
                if not device.get("isLoopbackDevice") or device["maxInputChannels"] < 1:
                    raise OSError("선택한 WASAPI 루프백 장치를 사용할 수 없습니다.")
                with self._lock:
                    if selected is not None and generation == self._selection_generation:
                        self._selected_name = device["name"]
                rate = int(device["defaultSampleRate"])
                channels = int(device["maxInputChannels"])
                self._reopen.clear()

                def callback(data, frame_count, time_info, status):
                    if status:
                        LOG.debug("WASAPI callback status: %s", status)
                    self._enqueue(data, rate, channels)
                    return (None, module.paContinue)

                stream = audio.open(format=module.paFloat32, channels=channels, rate=rate,
                                    input=True, input_device_index=int(device["index"]),
                                    frames_per_buffer=max(1, rate // 50), stream_callback=callback)
                self.error = ""
                LOG.info("WASAPI loopback opened: %s (%s Hz)", device["name"], rate)
                check_at = time.monotonic() + self._default_check_interval
                while not self._stop.wait(self._poll_interval) and not self._reopen.is_set():
                    if self._selection_generation != generation:
                        break
                    if not stream.is_active():
                        raise OSError("오디오 장치 연결이 해제되었습니다.")
                    if selected is None and time.monotonic() >= check_at:
                        current = audio.get_default_wasapi_loopback()
                        if current["index"] != device["index"]:
                            break
                        check_at = time.monotonic() + self._default_check_interval
            except Exception as exc:
                self.error = f"오디오 캡처 재시도 중: {exc}"
                LOG.warning("Audio capture unavailable: %s", exc)
                self._stop.wait(self._retry_interval)
            finally:
                if stream:
                    try:
                        stream.close()
                    except OSError:
                        LOG.debug("Audio stream already disconnected")
                if audio:
                    audio.terminate()
                with self._lock:
                    self._packets.clear()


class LoopbackTrack(AudioStreamTrack):
    """20 ms stereo frames, including silence, with monotonic sample timestamps."""

    def __init__(self, engine: AudioEngine) -> None:
        super().__init__()
        self.engine = engine
        self._pts = 0
        self._deadline: float | None = None
        self._resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
        self._format: tuple[int, int] | None = None
        self._pending = np.empty((0, 2), dtype=np.int16)

    def _convert(self, packet) -> None:
        data, rate, channels = packet
        if self._format != (rate, channels):
            self._resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
            self._pending = np.empty((0, 2), dtype=np.int16)
            self._format = (rate, channels)
        samples = np.frombuffer(data, dtype=np.float32)
        if not samples.size or samples.size % channels:
            return
        samples = samples.reshape(-1, channels)
        # Standard Windows channel order matches FFmpeg native layouts through 7.1.
        # Downmix all channels so center-channel dialogue is not discarded.
        layouts = {1: "mono", 2: "stereo", 3: "3.0", 4: "quad",
                   5: "5.0", 6: "5.1", 7: "6.1", 8: "7.1"}
        layout = layouts.get(channels, "stereo")
        if channels not in layouts:
            # Unusual interfaces expose no channel mask via PortAudio: bounded fallback.
            samples = np.column_stack((samples[:, ::2].mean(axis=1), samples[:, 1::2].mean(axis=1)))
        samples = np.ascontiguousarray(samples.T)
        frame = av.AudioFrame.from_ndarray(samples, format="fltp", layout=layout)
        frame.sample_rate = rate
        for converted in self._resampler.resample(frame):
            block = converted.to_ndarray().reshape(-1, 2)
            self._pending = np.concatenate((self._pending, block))[-SAMPLES * 4:]

    async def recv(self) -> av.AudioFrame:
        from aiortc.mediastreams import MediaStreamError
        if self.readyState != "live":
            raise MediaStreamError
        now = time.monotonic()
        if self._deadline is None or now - self._deadline > 0.1:
            self._deadline = now
        await asyncio.sleep(max(0, self._deadline - now))
        self._deadline += SAMPLES / RATE
        # A bounded loop protects the event loop even if a device returns unusual block sizes.
        for _ in range(4):
            if len(self._pending) >= SAMPLES:
                break
            packet = self.engine._take()
            if packet is None:
                break
            self._convert(packet)
        count = min(SAMPLES, len(self._pending))
        output = np.zeros((SAMPLES, 2), dtype=np.int16)
        if count:
            output[:count] = self._pending[:count]
            self._pending = self._pending[count:]
        self.engine.level = min(1.0, float(np.sqrt(np.mean(output.astype(np.float32) ** 2))) / 32768)
        output = apply_gain(output, self.engine.gain, self.engine.muted)
        frame = av.AudioFrame.from_ndarray(output.reshape(1, -1), format="s16", layout="stereo")
        frame.sample_rate = RATE
        frame.pts = self._pts
        frame.time_base = Fraction(1, RATE)
        self._pts += SAMPLES
        return frame
