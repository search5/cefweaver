"""Control Cast devices (Chromecast and others) through the CEF media router.

:class:`~cefweaver.cast.Cast` lists the Cast sinks of the network and connects to one;
:class:`~cefweaver.cast.CastSession` sends player commands to the connected device and reports its
state.

Note:
    Everything runs on the thread of the CEF message loop (the thread that called
    ``CefApp.initialize()``), and all callbacks are called on that thread. No call blocks: a command
    returns at once and its effect is reported through ``on_status``, ``on_volume`` and ``on_state``.
    The device does not answer a request with a matching reply, so wait for the player state you
    expect (``PLAYING``, ``PAUSED``, ``FINISHED``).

Example:
    ::

        def ready(cast):
            cast.on_sinks = lambda sinks: print([s.get_name() for s in sinks])

        Cast.open(ready)                          # after CefApp.initialize(); keep the Cast

        session = cast.connect(sink, on_result)   # on_result(session, result, error)
        session.load("http://host/video.mp4")
        session.pause()
        session.play()
        session.seek(30.0)
        session.set_volume(0.3)
        session.stop()
        session.disconnect()
"""

import json
from dataclasses import dataclass

from . import types
from ._cefweaver import CompletionCallback, MediaObserver, MediaRouteCreateCallback, MediaRouter

DEFAULT_MEDIA_RECEIVER = "CC1AD845"  # the application of a Cast device that plays a media address


@dataclass(frozen=True)
class CastStatus:
    """The state of the player of a device (a ``MEDIA_STATUS`` message).

    Attributes:
        player_state (str): ``"IDLE"``, ``"BUFFERING"``, ``"PLAYING"`` or ``"PAUSED"``.
        current_time (float): The playback position in seconds.
        duration (float | None): The media duration in seconds, or None while the device does not
            know it.
        idle_reason (str | None): Why the player is ``"IDLE"`` after a playback: ``"FINISHED"``,
            ``"ERROR"``, ``"CANCELLED"`` or ``"INTERRUPTED"``. None otherwise.
        media_session_id (int | None): The id of the media session on the device.
        content_id (str | None): The address of the loaded media.
        playback_rate (float): The playback speed (1.0 is normal).
    """

    player_state: str
    current_time: float
    duration: float | None
    idle_reason: str | None
    media_session_id: int | None
    content_id: str | None
    playback_rate: float


def _status_from(message):
    """Return the :class:`CastStatus` of a ``MEDIA_STATUS`` message, or None if it has no status."""
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
    """The Cast devices of the network, and the means to connect to one.

    Create it with :meth:`open`, or with ``Cast(router)`` if a ``MediaRouter`` that is ready is at
    hand. Keep a reference: the observer of the router stays registered until the object is dropped
    or :meth:`close` is called.

    Args:
        router (MediaRouter): A media router that is ready.

    Attributes:
        on_sinks (callable | None): Called as ``on_sinks(sinks)`` every time the list of sinks
            changes, with a list of ``MediaSink`` (Cast sinks only, ``is_cast_sink()``). A device
            often shows up after a first empty list, so wait for the call (or call :meth:`refresh`)
            instead of reading :attr:`sinks` at once. Default None.
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
        """Start the media router and call ``callback`` when it is ready.

        Args:
            callback (callable): Called as ``callback(cast)`` on the UI thread with the
                :class:`Cast`. Keep a reference to it.
            request_context (RequestContext, optional): The context whose router is started.
                Default: the global context.

        Raises:
            RuntimeError: If the media router is not available (CEF is not initialized).
        """
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
        """MediaRouter: The media router this object observes."""
        return self._router

    @property
    def sinks(self):
        """list: The Cast sinks seen last, as ``MediaSink`` objects."""
        return list(self._sinks)

    def refresh(self):
        """Request the current sinks and routes again; ``on_sinks`` is called with the result."""
        self._router.notify_current_sinks()
        self._router.notify_current_routes()

    def find(self, name):
        """Return the Cast sink with the given name, or None.

        Args:
            name (str): The name to match against ``MediaSink.get_name()``.

        Returns:
            MediaSink | None: The sink among the last seen ones, or None if there is none.
        """
        for sink in self._sinks:
            if sink.get_name() == name:
                return sink
        return None

    def connect(self, sink, on_result=None, application_id=DEFAULT_MEDIA_RECEIVER):
        """Connect to a sink and start an application there.

        Args:
            sink (MediaSink): The device to connect to.
            on_result (callable, optional): Called as ``on_result(session, result, error)`` on the
                UI thread when the connection attempt finishes. ``result`` is a
                ``types.MediaRouteCreateResult``; ``error`` is the text CEF gave on a failure.
            application_id (str, optional): The Cast application to start. Default:
                ``DEFAULT_MEDIA_RECEIVER``, the receiver that plays a media address.

        Returns:
            CastSession: The session, returned at once. It is usable when ``on_result`` reports
            ``types.MediaRouteCreateResult.OK``; on a failure its ``state`` is ``"closed"``.

        Raises:
            ValueError: If there is no media source for ``application_id``, or the sink cannot
                play it.
        """
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
        """Disconnect all sessions and stop observing the router."""
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
    """One connection to a Cast device. Get it from :meth:`Cast.connect`.

    Commands given before the device has opened its application (see :attr:`ready`) are queued and
    sent in order once it has. Commands on a closed session raise ``RuntimeError``.

    Args:
        sink (MediaSink): The device.
        client_id (str): The client id used in the messages of this session.

    Attributes:
        sink (MediaSink): The device.
        application_name (str | None): The name of the running application, once known.
        status (CastStatus | None): The last player status received.
        volume (tuple | None): The last ``(level, muted)`` of the device volume received.
        on_state (callable | None): Called as ``on_state(state)`` when :attr:`state` changes, with
            ``"connecting"``, ``"connected"`` or ``"closed"``.
        on_status (callable | None): Called as ``on_status(status)`` with a :class:`CastStatus`
            each time the device reports the player state.
        on_volume (callable | None): Called as ``on_volume(level, muted)`` when the volume of the
            device (not of the stream) changes.
        on_message (callable | None): Called as ``on_message(data)`` with every other message of
            the device, as decoded JSON.
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
        """str: ``"connecting"``, ``"connected"`` or ``"closed"``."""
        return self._state

    @property
    def ready(self):
        """bool: True when the application of the device is open, so commands are sent at once."""
        return self._state == "connected" and self._session_id is not None

    # --- commands -------------------------------------------------------------------------

    def load(self, url, content_type="video/mp4", autoplay=True, current_time=0.0, stream_type="BUFFERED",
             media_options=None):
        """Load and play media.

        The device downloads the media itself, so the address must be reachable from the device
        (not ``localhost``) and answer with the right ``Content-Type``; some formats also need CORS
        headers.

        Args:
            url (str): The address of the media.
            content_type (str, optional): The MIME type. Default ``"video/mp4"``.
            autoplay (bool, optional): Start playing at once. Default True.
            current_time (float, optional): The start position in seconds. Default 0.0.
            stream_type (str, optional): ``"BUFFERED"``, ``"LIVE"`` or ``"NONE"``. Default
                ``"BUFFERED"``.
            media_options (dict, optional): More fields of the Cast ``MediaInformation``, for
                example ``{"hlsSegmentFormat": "ts"}``.

        Raises:
            RuntimeError: If the session is closed.
        """
        media = {"contentId": url, "contentType": content_type, "streamType": stream_type}
        media.update(media_options or {})
        self._command("LOAD", False, autoplay=bool(autoplay), currentTime=float(current_time), media=media)

    def play(self):
        """Resume the paused playback.

        Raises:
            RuntimeError: If the session is closed.
        """
        self._command("PLAY", True)

    def pause(self):
        """Pause the playback.

        Raises:
            RuntimeError: If the session is closed.
        """
        self._command("PAUSE", True)

    def seek(self, seconds):
        """Seek to a position in the current media.

        Args:
            seconds (float): The position from the start, in seconds.

        Raises:
            RuntimeError: If the session is closed.
        """
        self._command("SEEK", True, currentTime=float(seconds))

    def stop(self):
        """End the playback and the application on the device.

        The session becomes ``"closed"`` once the device ends the application; connect again to
        play something else. The device does not report the stop as a player state.

        Raises:
            RuntimeError: If the session is closed.
        """
        self._command("STOP", True)

    def set_volume(self, level):
        """Set the volume of the device; ``on_volume`` reports the result.

        Args:
            level (float): The volume, from 0.0 to 1.0.

        Raises:
            ValueError: If ``level`` is outside 0.0 to 1.0.
            RuntimeError: If the session is closed.
        """
        if not 0.0 <= level <= 1.0:
            raise ValueError("the volume is between 0.0 and 1.0")
        self._command("SET_VOLUME", False, volume={"level": float(level)})

    def set_muted(self, muted):
        """Mute or unmute the device; ``on_volume`` reports the result.

        Args:
            muted (bool): True to mute.

        Raises:
            RuntimeError: If the session is closed.
        """
        self._command("SET_VOLUME", False, volume={"muted": bool(muted)})

    def disconnect(self):
        """End the connection and the application on the device. Queued commands are dropped."""
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
