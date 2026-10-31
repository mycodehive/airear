import asyncio
from fractions import Fraction

import numpy as np

from airear.audio import AudioEngine, apply_gain


def test_limiter_has_no_overflow_and_mute():
    samples = np.array([[-32768, 32767], [100, -100]], dtype=np.int16)
    gained = apply_gain(samples, 2)
    assert gained[0, 0] < 0 and gained[0, 1] > 0
    assert abs(gained.astype(float)).max() <= 32700
    assert not apply_gain(samples, 2, True).any()
    assert np.array_equal(apply_gain(np.array([[100, -100]], dtype=np.int16), 1), [[100, -100]])


def test_queue_is_bounded_and_discards_stale_audio():
    engine = AudioEngine()
    for n in range(100):
        engine._enqueue(str(n).encode(), 48000, 2)
    assert len(engine._packets) == 4
    assert engine._take()[0] == b"98"


def test_continuous_silence_and_sample_timestamps():
    async def run():
        engine = AudioEngine()
        track = engine.track()
        first = await track.recv()
        second = await track.recv()
        assert first.samples == second.samples == 960
        assert first.sample_rate == 48000
        assert first.time_base == Fraction(1, 48000)
        assert second.pts - first.pts == 960
        assert not second.to_ndarray().any()
        track.stop()
    asyncio.run(run())


def test_resamples_mono_44100_to_stereo_and_keeps_signal():
    async def run():
        engine = AudioEngine()
        # Provide enough source samples to account for the resampler's filter delay.
        wave = (0.1 * np.sin(np.arange(1764) * 2 * np.pi * 440 / 44100)).astype(np.float32)
        engine._enqueue(wave.tobytes(), 44100, 1)
        frame = await engine.track().recv()
        out = frame.to_ndarray().reshape(-1, 2)
        assert out.shape == (960, 2)
        assert np.max(np.abs(out)) > 1000
        assert np.array_equal(out[:, 0], out[:, 1])
        assert 0 < engine.level < 1
    asyncio.run(run())


def test_device_change_flushes_captured_packets():
    engine = AudioEngine()
    engine._enqueue(b"old", 48000, 2)
    engine.select(123)
    assert engine.device_id == 123
    assert engine._take() is None


def test_surround_center_channel_is_included_in_downmix():
    async def run():
        engine = AudioEngine()
        block = np.zeros((960, 6), dtype=np.float32)
        block[:, 2] = 0.1  # dialogue in the center channel of a 5.1 output
        engine._enqueue(block.tobytes(), 48000, 6)
        frame = await engine.track().recv()
        out = frame.to_ndarray().reshape(-1, 2)
        assert out[:, 0].max() > 100
        assert out[:, 1].max() > 100
    asyncio.run(run())


def test_stop_replaces_track_and_discards_resampler_pending_audio():
    engine = AudioEngine()
    old = engine.track()
    old._pending = np.ones((960, 2), dtype=np.int16)
    engine.stop()
    assert old.readyState == "ended"
    fresh = engine.track()
    assert fresh is not old
    assert not fresh._pending.size
    assert fresh._pts == 0


class FakeBackend:
    """Deterministic PortAudio adapter; this does not exercise Windows WASAPI."""
    paFloat32 = 1
    paContinue = 0

    def __init__(self):
        self.inventory = [self.device(7, "Speaker A"), self.device(8, "Speaker B")]
        self.default = 7
        self.opened = []
        self.streams = []
        self.terminated = 0
        self.on_probe = lambda stream: True

    @staticmethod
    def device(index, name):
        return {"index": index, "name": name, "isLoopbackDevice": True,
                "maxInputChannels": 2, "defaultSampleRate": 48000}

    def PyAudio(self):
        backend = self

        class Adapter:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.terminate()

            def terminate(self):
                backend.terminated += 1

            def get_loopback_device_info_generator(self):
                return iter(list(backend.inventory))

            def get_device_info_by_index(self, index):
                return next(d for d in backend.inventory if d["index"] == index)

            def get_default_wasapi_loopback(self):
                return self.get_device_info_by_index(backend.default)

            def open(self, **kwargs):
                backend.opened.append(kwargs["input_device_index"])

                class Stream:
                    closed = False

                    def is_active(self):
                        return backend.on_probe(self)

                    def close(self):
                        self.closed = True

                stream = Stream()
                backend.streams.append(stream)
                block = np.full((960, 2), 0.1, dtype=np.float32)
                assert kwargs["stream_callback"](block.tobytes(), 960, {}, 0) == (None, 0)
                return stream
        return Adapter()


def fake_engine(monkeypatch):
    backend = FakeBackend()
    engine = AudioEngine()
    monkeypatch.setattr(engine, "_backend", lambda: backend)
    engine._poll_interval = 0.005
    engine._retry_interval = 0.005
    engine._default_check_interval = 0.005
    return engine, backend


def eventually(predicate):
    import time
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    assert predicate(), "Mock capture worker did not reach expected state"


def test_mock_capture_opens_loopback_delivers_callback_and_closes(monkeypatch):
    engine, backend = fake_engine(monkeypatch)
    engine.start()
    try:
        eventually(lambda: bool(engine._packets))
        packet = engine._take()
        assert packet is not None and packet[1:] == (48000, 2)
        assert backend.opened == [7]
    finally:
        engine.stop()
    assert backend.streams[0].closed
    assert backend.terminated == 1
    assert not engine._thread.is_alive()


def test_mock_default_change_reopens_new_loopback(monkeypatch):
    engine, backend = fake_engine(monkeypatch)
    engine.start()
    try:
        eventually(lambda: backend.opened == [7])
        backend.default = 8
        eventually(lambda: backend.opened == [7, 8])
        assert backend.streams[0].closed
    finally:
        engine.stop()
    assert all(stream.closed for stream in backend.streams)


def test_mock_unplug_reconnect_retains_name_when_index_is_reused(monkeypatch):
    engine, backend = fake_engine(monkeypatch)
    engine.devices()  # cache the displayed endpoint identity at selection time
    engine.select(7)

    def disconnect_first(stream):
        if stream is backend.streams[0]:
            # The original index now names a different physical endpoint.
            backend.inventory = [backend.device(7, "Unrelated endpoint"), backend.device(19, "Speaker A")]
            return False
        return True

    backend.on_probe = disconnect_first
    engine.start()
    try:
        eventually(lambda: backend.opened == [7, 19])
        assert backend.streams[0].closed
        assert engine._selected_name == "Speaker A"
        assert engine.error == ""
    finally:
        engine.stop()
    assert backend.opened == [7, 19]


def test_mock_missing_selected_name_does_not_fall_back_to_reused_index(monkeypatch):
    engine, backend = fake_engine(monkeypatch)
    engine.devices()
    engine.select(7)
    backend.inventory = [backend.device(7, "Unrelated endpoint")]
    engine.start()
    try:
        eventually(lambda: "Speaker A" in engine.error)
        assert backend.opened == []
    finally:
        engine.stop()


def test_mock_explicit_device_selection_reopens_capture(monkeypatch):
    engine, backend = fake_engine(monkeypatch)
    engine.devices()
    engine.start()
    try:
        eventually(lambda: backend.opened == [7])
        engine.select(8)
        eventually(lambda: backend.opened == [7, 8])
        assert engine._selected_name == "Speaker B"
    finally:
        engine.stop()
