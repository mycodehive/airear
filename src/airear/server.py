"""LAN-only receiver service. Administrative controls stay in the desktop process."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import secrets
import ssl
import threading
import time
from collections import OrderedDict, deque
from pathlib import Path
from urllib.parse import urlsplit

from aiohttp import web
from aiortc import RTCPeerConnection, RTCConfiguration, RTCSessionDescription, RTCRtpSender
from aiortc.contrib.media import MediaRelay

log = logging.getLogger(__name__)
WEB = Path(__file__).parent / 'web'
STATE = web.AppKey('state', object)
LAN = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.0/8', '169.254.0.0/16', '::1/128', 'fc00::/7', 'fe80::/10'))


def is_lan(value):
    try:
        address = ipaddress.ip_address(value)
        if address.version == 6 and address.ipv4_mapped:
            address = address.ipv4_mapped
        return any(address.version == network.version and address in network for network in LAN)
    except ValueError:
        return False


class Service:
    def __init__(self, engine, pin=None):
        self.engine = engine
        self.pin = pin or f'{secrets.randbelow(100000000):08d}'
        self.tokens = {}  # token -> (expiry, originating address)
        self.attempts = OrderedDict()
        self.global_attempts = deque()
        self.peers = {}
        self.relay = MediaRelay()

    def limited(self, address):
        now = time.monotonic()
        while self.global_attempts and self.global_attempts[0] < now - 60:
            self.global_attempts.popleft()
        times = self.attempts.pop(address, deque())
        while times and times[0] < now - 60:
            times.popleft()
        blocked = len(times) >= 8 or len(self.global_attempts) >= 60
        if not blocked:
            times.append(now)
            self.global_attempts.append(now)
        self.attempts[address] = times
        while len(self.attempts) > 256:
            self.attempts.popitem(last=False)
        return blocked

    def authenticated(self, request):
        token = request.headers.get('Authorization', '').removeprefix('Bearer ')
        now = time.monotonic()
        self.tokens = {k: v for k, v in self.tokens.items() if v[0] > now}
        value = self.tokens.get(token)
        if not value or value[1] != request.remote:
            log.warning('Receiver authentication denied: address=%s reason=expired-or-unrecognized-session', request.remote)
            raise web.HTTPUnauthorized(text='인증이 만료되었습니다. PIN을 다시 입력하세요.')
        return token

    async def remove(self, identity):
        item = self.peers.pop(identity, None)
        if item:
            item['track'].stop()
            await item['pc'].close()
            log.info('Receiver closed: address=%s', item['address'])

    async def close(self):
        await asyncio.gather(*(self.remove(key) for key in list(self.peers)))
        self.tokens.clear()

    async def rotate(self):
        await self.close()
        self.pin = f'{secrets.randbelow(100000000):08d}'
        log.info('Access credentials rotated; existing receivers disconnected')
        return self.pin

    async def reap(self, app):
        async def monitor():
            while True:
                await asyncio.sleep(5)
                now = time.monotonic()
                for key, item in list(self.peers.items()):
                    if item['expires'] < now or (item['pc'].connectionState != 'connected' and now - item['created'] > 30):
                        await self.remove(key)
        task = asyncio.create_task(monitor())
        yield
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await self.close()


@web.middleware
async def guard(request, handler):
    if not is_lan(request.remote or ''):
        raise web.HTTPForbidden(text='개인 LAN에서만 연결할 수 있습니다.')
    host = urlsplit('//' + request.host).hostname
    if host != 'localhost' and not is_lan(host or ''):
        raise web.HTTPForbidden(text='LAN IP 주소로 접속하세요.')
    if request.method != 'GET':
        origin = request.headers.get('Origin')
        if origin != f'{request.scheme}://{request.host}':
            raise web.HTTPForbidden(text='다른 출처의 요청은 허용하지 않습니다.')
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        response = web.Response(status=exc.status, body=exc.body, headers=exc.headers)
    except (ValueError, TypeError):
        response = web.Response(status=400, text='요청 형식이 올바르지 않습니다.')
    response.headers.update({'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; media-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"})
    return response


async def auth(request):
    state = request.app[STATE]
    if state.limited(request.remote):
        log.warning('Receiver authentication denied: address=%s reason=rate-limit', request.remote)
        raise web.HTTPTooManyRequests(text='시도가 너무 많습니다. 1분 후 다시 시도하세요.')
    data = await request.json()
    if not isinstance(data, dict) or not isinstance(data.get('pin'), str) or not secrets.compare_digest(data['pin'], state.pin):
        log.warning('Receiver authentication denied: address=%s reason=incorrect-pin', request.remote)
        raise web.HTTPUnauthorized(text='PIN이 올바르지 않습니다.')
    now = time.monotonic()
    state.tokens = {k: v for k, v in state.tokens.items() if v[0] > now}
    if len(state.tokens) >= 64:
        raise web.HTTPServiceUnavailable(text='인증 세션이 가득 찼습니다. 잠시 후 다시 시도하세요.')
    token = secrets.token_urlsafe(32)
    state.tokens[token] = (time.monotonic() + 12 * 3600, request.remote)
    log.info('Receiver authenticated: address=%s', request.remote)
    return web.json_response({'token': token})


async def offer(request):
    state = request.app[STATE]
    token = state.authenticated(request)
    if len(state.peers) >= 4:
        raise web.HTTPServiceUnavailable(text='최대 수신기 4대가 연결되어 있습니다.')
    data = await request.json()
    if not isinstance(data, dict) or data.get('type') != 'offer' or not isinstance(data.get('sdp'), str):
        raise web.HTTPBadRequest(text='잘못된 SDP 요청입니다.')
    pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))
    identity = secrets.token_hex(12)
    track = state.relay.subscribe(state.engine.track(), buffered=False)
    state.peers[identity] = {'pc': pc, 'track': track, 'address': request.remote, 'token': token, 'created': time.monotonic(), 'expires': state.tokens[token][0]}

    @pc.on('connectionstatechange')
    async def changed():
        if pc.connectionState == 'connected':
            log.info('Receiver connected: address=%s codec=Opus', request.remote)
        if pc.connectionState in ('failed', 'closed'):
            await state.remove(identity)

    log.info('Receiver joining: address=%s', request.remote)
    try:
        await asyncio.wait_for(pc.setRemoteDescription(RTCSessionDescription(sdp=data['sdp'], type='offer')), 10)
        if any(t.kind != 'audio' for t in pc.getTransceivers()):
            raise ValueError('Only audio receivers are supported')
        sender = pc.addTrack(track)
        codecs = [c for c in RTCRtpSender.getCapabilities('audio').codecs if c.mimeType.lower() == 'audio/opus']
        for transceiver in pc.getTransceivers():
            if transceiver.kind == 'audio':
                transceiver.direction = 'sendonly'
            if transceiver.sender == sender:
                transceiver.setCodecPreferences(codecs)
        await asyncio.wait_for(pc.setLocalDescription(await pc.createAnswer()), 15)
        return web.json_response({'sdp': pc.localDescription.sdp, 'type': pc.localDescription.type, 'id': identity})
    except Exception as exc:
        log.warning('Receiver negotiation failed: address=%s error=%s', request.remote, type(exc).__name__)
        await state.remove(identity)
        raise web.HTTPBadRequest(text='오디오 연결 협상에 실패했습니다.') from None


async def disconnect(request):
    state = request.app[STATE]
    token = state.authenticated(request)
    identity = request.match_info['id']
    item = state.peers.get(identity)
    if item and secrets.compare_digest(item['token'], token):
        await state.remove(identity)
    return web.Response(status=204)


def create_app(engine, pin=None):
    app = web.Application(middlewares=[guard], client_max_size=65536)
    state = Service(engine, pin)
    app[STATE] = state
    app.cleanup_ctx.append(state.reap)
    app.router.add_post('/api/auth', auth)
    app.router.add_post('/api/offer', offer)
    app.router.add_delete('/api/peers/{id}', disconnect)
    for route, name in (('/', 'index.html'), ('/app.js', 'app.js'), ('/style.css', 'style.css')):
        async def static(request, filename=name):
            return web.FileResponse(WEB / filename)
        app.router.add_get(route, static)
    return app


class Runtime:
    def __init__(self, engine):
        self.engine = engine
        self._pin = f'{secrets.randbelow(100000000):08d}'
        self.loop = None
        self.thread = None
        self.state = None
        self.error = ''
        self.port = None
        self.running = False
        self._ready = threading.Event()

    @property
    def pin(self):
        return self._pin

    def start(self, host='0.0.0.0', port=8765, cert=None, key=None):
        if self.thread and self.thread.is_alive():
            return
        self.error = ''
        self.port = port
        self._ready.clear()
        self.thread = threading.Thread(target=self._run, args=(host, port, cert, key), daemon=True, name='airear-server')
        self.thread.start()
        if not self._ready.wait(20):
            raise RuntimeError('서버 시작 시간 초과')
        if self.error:
            raise RuntimeError(self.error)

    def _run(self, host, port, cert, key):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        runner = None
        try:
            self.engine.start()
            app = create_app(self.engine, self._pin)
            self.state = app[STATE]
            runner = web.AppRunner(app, access_log=None)
            self.loop.run_until_complete(runner.setup())
            context = None
            if cert and key:
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.minimum_version = ssl.TLSVersion.TLSv1_2
                context.load_cert_chain(cert, key)
            site = web.TCPSite(runner, host, port, ssl_context=context)
            self.loop.run_until_complete(site.start())
            self.running = True
            log.info('LAN server started: host=%s port=%s tls=%s', host, port, bool(context))
            # Signal readiness only after the loop begins processing callbacks.
            # Otherwise an immediate GUI stop could miss the not-yet-running loop.
            self.loop.call_soon(self._ready.set)
            self.loop.run_forever()
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            log.error('LAN server failed: error=%s', type(exc).__name__)
        finally:
            self.running = False
            self._ready.set()
            if runner:
                self.loop.run_until_complete(runner.cleanup())
            self.engine.stop()
            tasks = asyncio.all_tasks(self.loop)
            for task in tasks:
                task.cancel()
            self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            self.loop.close()
            log.info('LAN server stopped')

    def stop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=20)
            if self.thread.is_alive():
                raise RuntimeError('서버 종료 시간 초과')

    def _call(self, coroutine):
        if not self.running:
            coroutine.close()
            return None
        return asyncio.run_coroutine_threadsafe(coroutine, self.loop).result(timeout=10)

    def disconnect(self, identity):
        if self.state:
            self._call(self.state.remove(identity))

    def rotate_pin(self):
        if self.running:
            self._pin = self._call(self.state.rotate())
        else:
            self._pin = f'{secrets.randbelow(100000000):08d}'
        return self._pin

    def snapshot(self):
        # A shallow dict copy is atomic under CPython's GIL. No event-loop wait
        # is allowed here: the GUI polls this method from its main thread.
        peers = self.state.peers.copy() if self.running and self.state else {}
        clients = [{'id': key, 'address': value['address'], 'state': value['pc'].connectionState}
                   for key, value in peers.items()]
        return {'running': self.running, 'error': self.error, 'clients': clients, 'port': self.port}
