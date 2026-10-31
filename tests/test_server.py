import asyncio
import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from airear.server import STATE, create_app, is_lan


class Engine:
    def track(self):
        raise AssertionError('Unauthenticated requests must not allocate audio')


@pytest_asyncio.fixture
async def client():
    async with TestClient(TestServer(create_app(Engine(), '12345678'))) as client:
        yield client


def origin(client):
    return {'Origin': str(client.make_url('/')).rstrip('/')}


@pytest.mark.asyncio
async def test_pin_token_and_no_administration_routes(client):
    result = await client.post('/api/auth', json={'pin':'12345678'}, headers=origin(client))
    assert result.status == 200
    token = (await result.json())['token']
    assert len(token) >= 32
    result = await client.delete('/api/peers/missing', headers={**origin(client), 'Authorization':f'Bearer {token}'})
    assert result.status == 204
    assert (await client.get('/api/admin')).status == 404
    assert (await client.get('/')).status == 200


@pytest.mark.asyncio
async def test_cross_origin_and_unauthorized_offer(client):
    assert (await client.post('/api/auth',json={'pin':'12345678'},headers={'Origin':'https://evil.test'})).status == 403
    assert (await client.post('/api/auth',json={'pin':'12345678'})).status == 403
    assert (await client.post('/api/offer',json={'type':'offer','sdp':'x'},headers=origin(client))).status == 401


@pytest.mark.asyncio
async def test_rate_limit_and_pin_rotation(client):
    for _ in range(8):
        assert (await client.post('/api/auth',json={'pin':'wrong'},headers=origin(client))).status == 401
    assert (await client.post('/api/auth',json={'pin':'12345678'},headers=origin(client))).status == 429
    state = client.server.app[STATE]
    state.tokens['old'] = (float('inf'), '127.0.0.1')
    old = state.pin
    await state.rotate()
    assert len(state.pin) == 8 and state.pin.isdigit()
    assert state.pin != old
    assert not state.tokens


@pytest.mark.asyncio
async def test_expired_and_address_bound_tokens(client):
    state = client.server.app[STATE]
    state.tokens['expired'] = (0, '127.0.0.1')
    state.tokens['elsewhere'] = (float('inf'), '192.168.0.9')
    for token in ('expired','elsewhere'):
        response = await client.delete('/api/peers/missing',headers={**origin(client),'Authorization':f'Bearer {token}'})
        assert response.status == 401


@pytest.mark.parametrize('address', ['127.0.0.1','192.168.1.8','10.0.0.4','172.16.1.1','::1','fd00::1','::ffff:192.168.0.1'])
def test_lan_addresses(address):
    assert is_lan(address)


@pytest.mark.parametrize('address', ['8.8.8.8','172.32.0.1','203.0.113.1','2001:db8::1','evil.test',''])
def test_non_lan_addresses(address):
    assert not is_lan(address)


@pytest.mark.asyncio
async def test_real_webrtc_opus_audio_and_cleanup(monkeypatch):
    import asyncio
    from aiortc import AudioStreamTrack, RTCConfiguration, RTCPeerConnection, RTCSessionDescription

    # This transport test deliberately uses loopback ICE only. The sandbox blocks
    # interface enumeration; real LAN candidate gathering remains a device check.
    monkeypatch.setattr('aioice.ice.get_host_addresses', lambda **kwargs: ['127.0.0.1'])

    class SilentEngine:
        def __init__(self):
            self.source = AudioStreamTrack()

        def track(self):
            return self.source

    engine = SilentEngine()
    receiver = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    got_audio = asyncio.get_running_loop().create_future()

    @receiver.on('track')
    def received(track):
        if not got_audio.done():
            got_audio.set_result(track)

    try:
        async with TestClient(TestServer(create_app(engine, '12345678'))) as client:
            auth = await client.post('/api/auth', json={'pin':'12345678'}, headers=origin(client))
            token = (await auth.json())['token']
            headers = {**origin(client), 'Authorization':f'Bearer {token}'}
            receiver.addTransceiver('audio', direction='recvonly')
            await receiver.setLocalDescription(await receiver.createOffer())
            result = await client.post('/api/offer', json={'type':receiver.localDescription.type, 'sdp':receiver.localDescription.sdp}, headers=headers)
            assert result.status == 200, await result.text()
            answer = await result.json()
            assert 'opus/48000' in answer['sdp']
            await receiver.setRemoteDescription(RTCSessionDescription(type=answer['type'], sdp=answer['sdp']))
            track = await asyncio.wait_for(got_audio, timeout=10)
            frame = await asyncio.wait_for(track.recv(), timeout=10)
            assert frame.sample_rate == 48000
            assert frame.samples > 0
            response = await client.delete(f"/api/peers/{answer['id']}", headers=headers)
            assert response.status == 204
            assert not client.server.app[STATE].peers
    finally:
        await receiver.close()
        engine.source.stop()


def test_runtime_start_stop_and_error_cleanup():
    from airear.server import Runtime

    class RuntimeEngine:
        started = False

        def start(self):
            self.started = True

        def stop(self):
            self.started = False

    engine = RuntimeEngine()
    runtime = Runtime(engine)
    try:
        runtime.start(host='127.0.0.1', port=0)
        assert runtime.snapshot()['running']
        assert runtime.snapshot()['clients'] == []
        old_pin = runtime.pin
        assert runtime.rotate_pin() != old_pin
        assert engine.started
    finally:
        runtime.stop()
    assert not engine.started
    assert not runtime.snapshot()['running']
    assert not runtime.thread.is_alive()


@pytest.mark.asyncio
async def test_authentication_logs_never_include_secrets(client, caplog):
    import logging

    caplog.set_level(logging.INFO, logger='airear.server')
    response = await client.post('/api/auth', json={'pin':'12345678'}, headers=origin(client))
    token = (await response.json())['token']
    await client.post('/api/auth', json={'pin':'wrong-secret-pin'}, headers=origin(client))
    assert 'Receiver authenticated' in caplog.text
    assert 'Receiver authentication denied' in caplog.text
    for secret in ('12345678', 'wrong-secret-pin', token):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_receiver_language_override_is_live_and_errors_localized(client, tmp_path, monkeypatch):
    import json
    import airear.i18n as i18n
    monkeypatch.setattr(i18n, 'data_dir', lambda: tmp_path)
    folder = tmp_path / 'languages'
    folder.mkdir()
    pack = folder / 'xx.json'
    pack.write_text(json.dumps({'name': 'Custom', 'web': {'wrong_pin': 'First custom error'}}))
    listing = await (await client.get('/languages')).json()
    assert {'code': 'xx', 'name': 'Custom'} in listing
    response = await client.get('/languages/xx.json')
    assert response.status == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert (await response.json())['web']['wrong_pin'] == 'First custom error'
    pack.write_text(json.dumps({'name': 'Custom', 'web': {'wrong_pin': 'Edited immediately'}}))
    response = await client.post('/api/auth', json={'pin': 'wrong'},
                                 headers={**origin(client), 'X-AirEar-Language': 'xx'})
    assert response.status == 401
    assert await response.text() == 'Edited immediately'
    assert (await client.get('/languages/missing.json')).status == 404


@pytest.mark.asyncio
async def test_builtin_receiver_languages(client):
    en = await (await client.get('/languages/en.json')).json()
    ko = await (await client.get('/languages/ko.json')).json()
    assert en['web']['connect'] == 'Connect and listen'
    assert ko['web']['connect'] == '연결하고 듣기 시작'
    assert en['web'].keys() == ko['web'].keys()


@pytest.mark.asyncio
async def test_bounded_relay_preserves_frames_through_short_consumer_stall():
    from airear.server import BoundedAudioRelay
    class Source:
        def __init__(self):
            self.queue = asyncio.Queue()
        async def recv(self):
            return await self.queue.get()
    source = Source()
    relay = BoundedAudioRelay()
    slow = relay.subscribe(source)
    fast = relay.subscribe(source)
    relay.start(slow)
    relay.start(fast)
    try:
        for value in range(4):
            source.queue.put_nowait(value)
            assert await fast.recv() == value
        # The stalled peer still receives every frame in order, not only the last.
        assert [await slow.recv() for _ in range(4)] == list(range(4))
        assert slow.dropped_frames == 0
        for value in range(15):
            source.queue.put_nowait(value)
        await asyncio.sleep(0)
        assert slow.queue.qsize() == 10
        assert slow.dropped_frames == 5
        assert [await slow.recv() for _ in range(10)] == list(range(5, 15))
    finally:
        await relay.close()
    assert relay.task is None and not relay.proxies


@pytest.mark.asyncio
async def test_bounded_relay_stop_wakes_waiters_and_can_restart():
    from airear.server import BoundedAudioRelay
    from aiortc.mediastreams import MediaStreamError
    class Source:
        async def recv(self):
            await asyncio.sleep(3600)
    relay = BoundedAudioRelay()
    track = relay.subscribe(Source())
    pending = asyncio.create_task(track.recv())
    await asyncio.sleep(0)
    track.stop()
    with pytest.raises(MediaStreamError):
        await pending
    # New receiver arriving before the cancelled old pump has completed.
    new_track = relay.subscribe(Source())
    relay.start(new_track)
    assert not relay.task.cancelling()
    await relay.close()
