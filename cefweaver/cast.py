"""Cast devices (Chromecast and others): find them, connect, play, pause, seek and disconnect.

CEF only gives the building blocks (``MediaRouter``, ``MediaSink``, ``MediaRoute``,
``MediaObserver``): a route is a connection to a sink, and what is played over it is a JSON
message of the Cast protocol. This module wraps that::

    def ready(cast):
        cast.on_sinks = lambda sinks: print([s.get_name() for s in sinks])

    Cast.open(ready)                          # after CefApp.initialize(); keep the Cast you get

    session = cast.connect(sink, on_result)   # on_result(session, result, error)
    session.load("http://host/video.mp4")     # the device downloads the address itself
    session.pause(); session.play(); session.seek(30.0); session.set_volume(0.3)
    session.stop()                            # ends the playback and the session (the device goes back to its home screen)
    session.disconnect()

Everything runs on the thread of the CEF message loop (the thread that called ``initialize()``)
and the callbacks are called there. Nothing blocks: a call returns at once and its effect is
reported by ``on_status`` (the state of the player), ``on_volume`` and ``on_state`` (the
connection). The device does not answer a request with a matching reply, so wait for the state
you expect (``PLAYING``, ``PAUSED``, ``FINISHED``).

What was checked on real devices (a Google Nest Hub and another Cast sink) is in the llm-wiki,
F114: load, pause, play, seek, volume, mute, stop and disconnect. Not checked: DIAL sinks,
speaker groups and mirroring a tab.
"""

import json
from dataclasses import dataclass

from . import types
from ._cefweaver import CompletionCallback, MediaObserver, MediaRouteCreateCallback, MediaRouter

DEFAULT_MEDIA_RECEIVER = "CC1AD845"  # the application of a Cast device that plays a media address


@dataclass(frozen=True)
class CastStatus:
    """The state of the player of a device (a ``MEDIA_STATUS`` message).

    ``player_state`` is ``"IDLE"``, ``"BUFFERING"``, ``"PLAYING"`` or ``"PAUSED"``; when it is
    ``"IDLE"`` after a playback, ``idle_reason`` says why (``"FINISHED"``, ``"ERROR"``,
    ``"CANCELLED"``, ``"INTERRUPTED"``). ``duration`` is ``None`` while the device does not know it.
    """

    player_state: str
    current_time: float
    duration: float | None
    idle_reason: str | None
    media_session_id: int | None
    content_id: str | None
    playback_rate: float


def _status_from(message):
    """The ``CastStatus`` of a ``MEDIA_STATUS`` message, or None when it has no status (nothing is playing)."""
    status = message.get("status")
    if not status:
        return None
    entry = status[0]
    media = entry.get("media") or {}
    return CastStatus(
        player_state=entry.get("playerState", "IDLE"),
        current_time=float(entry.get("currentTime", 0)),
        duration=media.get("duration"),
        idle_reason=entry.get("idleReason"),
        media_session_id=entry.get("mediaSessionId"),
        content_id=media.get("contentId"),
        playback_rate=float(entry.get("playbackRate", 1)),
    )


class _Observer(MediaObserver):
    def __init__(self, cast):
        self._cast = cast

    def on_sinks(self, sinks):
        self._cast._sinks_changed(list(sinks))

    def on_routes(self, routes):
        self._cast._routes_changed(list(routes))

    def on_route_state_changed(self, route, state):
        self._cast._route_state_changed(route, state)

    def on_route_message_received(self, route, message):
        self._cast._route_message(route, bytes(message))


class _Created(MediaRouteCreateCallback):
    def __init__(self, cast, session, on_result):
        self._cast, self._session, self._on_result = cast, session, on_result

    def on_media_route_create_finished(self, result, error, route):
        self._cast._created(self._session, self._on_result, result, error, route)


class _Ready(CompletionCallback):
    def __init__(self, callback):
        self._callback = callback

    def on_complete(self):
        self._callback()


class Cast:
    """The Cast devices of the network: ``sinks``, and ``connect()`` to one of them.

    Create it with ``Cast.open(callback)`` (the router needs a moment to start) or, if you have a
    ``MediaRouter`` that is ready, ``Cast(router)``. Keep a reference: the observer of the router
    is registered until this object is dropped or ``close()`` is called.

    ``on_sinks(sinks)``, if you set it, is called with the list of ``MediaSink`` (only the Cast
    sinks, ``is_cast_sink()``) every time the list changes. A device often shows up after a first
    empty list, so wait for the call (or call ``refresh()``) instead of reading ``sinks`` at once.
    """

    def __init__(self, router):
        self._router = router
        self._sinks = []
        self._sessions = {}  # route id -> CastSession
        self._clients = 0
        self.on_sinks = None
        self._registration = router.add_observer(_Observer(self))
        self.refresh()

    @classmethod
    def open(cls, callback, request_context=None):
        """Start the router of ``request_context`` (default: the global context) and call
        ``callback(cast)`` on the UI thread when it is ready. The ``Cast`` is the argument of the
        callback; keep it."""
        def ready():
            callback(cast)

        if request_context is None:
            router = MediaRouter.get_global_media_router(_Ready(ready))
        else:
            router = request_context.get_media_router(_Ready(ready))
        if router is None:
            raise RuntimeError("the media router is not available (is CEF initialized?)")
        cast = cls(router)

    @property
    def router(self):
        return self._router

    @property
    def sinks(self):
        """The Cast sinks seen last (a list of ``MediaSink``)."""
        return list(self._sinks)

    def refresh(self):
        """Ask for the sinks again; ``on_sinks`` is called with the answer."""
        self._router.notify_current_sinks()
        self._router.notify_current_routes()

    def find(self, name):
        """The Cast sink with this name (``MediaSink.get_name()``), or None."""
        for sink in self._sinks:
            if sink.get_name() == name:
                return sink
        return None

    def connect(self, sink, on_result=None, application_id=DEFAULT_MEDIA_RECEIVER):
        """Connect to ``sink`` and start ``application_id`` there (default: the receiver that plays a
        media address). Returns the ``CastSession`` at once; it is usable when ``on_result(session,
        result, error)`` reports ``result == types.MediaRouteCreateResult.OK``. On a failure the
        session is ``closed`` and ``error`` is the text CEF gave."""
        self._clients += 1
        client_id = "cefweaver%d" % self._clients
        source = self._router.get_source("cast:%s?clientId=%s" % (application_id, client_id))
        if source is None:
            raise ValueError("no media source for application %r" % application_id)
        if not sink.is_cast_sink() or not sink.is_compatible_with(source):
            raise ValueError("%r cannot play application %r" % (sink.get_name(), application_id))
        session = CastSession(sink, client_id)
        self._router.create_route(source, sink, _Created(self, session, on_result))
        return session

    def close(self):
        """Disconnect all sessions and stop watching the router."""
        for session in list(self._sessions.values()):
            session.disconnect()
        self._registration = None

    # --- what the observer reports --------------------------------------------------------

    def _sinks_changed(self, sinks):
        self._sinks = [sink for sink in sinks if sink.is_cast_sink()]
        if self.on_sinks is not None:
            self.on_sinks(list(self._sinks))

    def _routes_changed(self, routes):
        alive = {route.get_id() for route in routes}
        for route_id, session in list(self._sessions.items()):
            if route_id not in alive:
                del self._sessions[route_id]
                session._closed()

    def _route_state_changed(self, route, state):
        session = self._sessions.get(route.get_id())
        if session is not None:
            session._route_state(state)

    def _route_message(self, route, raw):
        session = self._sessions.get(route.get_id())
        if session is not None:
            session._message(raw)

    def _created(self, session, on_result, result, error, route):
        if route is not None and result == types.MediaRouteCreateResult.OK:
            self._sessions[route.get_id()] = session
            session._attach(route)
        else:
            session._closed()
        if on_result is not None:
            on_result(session, result, error)


class CastSession:
    """One connection to a Cast device. Get it from ``Cast.connect()``.

    The callbacks you can set (all optional, called on the UI thread):

    * ``on_state(state)``: ``state`` is ``"connecting"``, ``"connected"`` or ``"closed"``.
    * ``on_status(status)``: a ``CastStatus`` of the player; also in ``status``.
    * ``on_volume(level, muted)``: the volume of the device (not of the stream); also in ``volume``.
    * ``on_message(data)``: every other message of the device, as the decoded JSON.

    Commands given before the device has opened its application (``ready``) wait and are sent in
    order when it has.
    """

    def __init__(self, sink, client_id):
        self.sink = sink
        self._client_id = client_id
        self._route = None
        self._state = "connecting"
        self._session_id = None
        self._media_session_id = None
        self._pending = []
        self._sequence = 0
        self._request = 0
        self.application_name = None
        self.status = None
        self.volume = None
        self.on_state = None
        self.on_status = None
        self.on_volume = None
        self.on_message = None

    @property
    def state(self):
        return self._state

    @property
    def ready(self):
        """True when the application of the device is open (commands are sent at once)."""
        return self._state == "connected" and self._session_id is not None

    # --- commands -------------------------------------------------------------------------

    def load(self, url, content_type="video/mp4", autoplay=True, current_time=0.0, stream_type="BUFFERED"):
        """Play the media at ``url``. The device downloads it, so the address must be reachable from
        the device (not ``localhost``) and answer with the right ``Content-Type``; some formats also
        need CORS headers. ``stream_type`` is ``"BUFFERED"``, ``"LIVE"`` or ``"NONE"``."""
        self._command("LOAD", False, autoplay=bool(autoplay), currentTime=float(current_time), media={
            "contentId": url, "contentType": content_type, "streamType": stream_type})

    def play(self):
        self._command("PLAY", True)

    def pause(self):
        self._command("PAUSE", True)

    def seek(self, seconds):
        """Go to this position of the media (seconds)."""
        self._command("SEEK", True, currentTime=float(seconds))

    def stop(self):
        """End the playback. The device goes back to its home screen, its application ends and the
        session becomes ``closed`` (about 0.2 s later on the device that was tried); connect again
        to play something else. The device does not report the stop as a player state."""
        self._command("STOP", True)

    def set_volume(self, level):
        """The volume of the device, 0.0 to 1.0 (reported by ``on_volume``)."""
        if not 0.0 <= level <= 1.0:
            raise ValueError("the volume is between 0.0 and 1.0")
        self._command("SET_VOLUME", False, volume={"level": float(level)})

    def set_muted(self, muted):
        self._command("SET_VOLUME", False, volume={"muted": bool(muted)})

    def disconnect(self):
        """End the connection (the application of the device ends too)."""
        self._pending.clear()
        if self._route is not None:
            route, self._route = self._route, None
            route.terminate()

    # --- sending --------------------------------------------------------------------------

    def _command(self, kind, with_media_session, **fields):
        if self._state == "closed":
            raise RuntimeError("the session is closed")
        if not self.ready:
            self._pending.append((kind, with_media_session, fields))
            return
        self._request += 1
        message = {"type": kind, "requestId": self._request, "sessionId": self._session_id}
        if with_media_session:
            message["mediaSessionId"] = self._media_session_id if self._media_session_id is not None else 1
        message.update(fields)
        self._send("v2_message", message)

    def _send(self, kind, message=None, sequence=None):
        if self._route is None:
            return
        if sequence is None:
            self._sequence += 1
            sequence = self._sequence
        payload = {"type": kind, "clientId": self._client_id, "sequenceNumber": sequence, "timeoutMillis": 0}
        if message is not None:
            payload["message"] = message
        self._route.send_route_message(json.dumps(payload).encode())

    # --- what the device sends ------------------------------------------------------------

    def _attach(self, route):
        self._route = route

    def _route_state(self, state):
        if state == types.MediaRouteConnectionState.CONNECTED:
            if self._state == "connecting":
                self._send("client_connect", sequence=-1)  # the client announces itself first
                self._set_state("connected")
                self._flush()
        elif state in (types.MediaRouteConnectionState.TERMINATED, types.MediaRouteConnectionState.CLOSED):
            self._closed()

    def _closed(self):
        self._route = None
        self._session_id = None
        self._pending.clear()
        self._set_state("closed")

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            if self.on_state is not None:
                self.on_state(state)

    def _flush(self):
        if not self.ready:
            return
        pending, self._pending = self._pending, []
        for kind, with_media_session, fields in pending:
            self._command(kind, with_media_session, **fields)

    def _message(self, raw):
        try:
            data = json.loads(raw)
        except ValueError:
            return
        kind, message = data.get("type"), data.get("message")
        if kind in ("new_session", "update_session") and isinstance(message, dict):
            self.application_name = message.get("displayName")
            self._set_volume((message.get("receiver") or {}).get("volume"))
            self._session_id = message.get("sessionId", self._session_id)
            self._flush()
            return
        if kind == "v2_message" and isinstance(message, dict) and message.get("type") == "MEDIA_STATUS":
            status = _status_from(message)
            if status is not None:
                self._media_session_id = status.media_session_id
                self.status = status
                if self.on_status is not None:
                    self.on_status(status)
            return
        if kind == "app_message" and isinstance(message, dict) and \
                message.get("namespaceName", "").endswith(".multizone"):
            try:
                inner = json.loads(message.get("message", ""))
            except ValueError:
                inner = None
            if isinstance(inner, dict) and inner.get("type") == "DEVICE_UPDATED":
                self._set_volume((inner.get("device") or {}).get("volume"))
                return
        if self.on_message is not None:
            self.on_message(data)

    def _set_volume(self, volume):
        if not volume or "level" not in volume:
            return
        volume = (volume["level"], bool(volume.get("muted", False)))
        if volume != self.volume:
            self.volume = volume
            if self.on_volume is not None:
                self.on_volume(*volume)
