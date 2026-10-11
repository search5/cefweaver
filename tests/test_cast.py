"""cefweaver.cast without a device: a fake router, sink and route play the part of CEF.

What a real Chromecast sends and does is in llm-wiki/pages/reference/verified-findings-opened.md (F114);
the messages here are shortened copies of those.
"""

import json
import unittest

try:
    import cefweaver
    from cefweaver import cast, types
except ImportError:  # pragma: no cover
    cefweaver = None


class FakeSource:
    def __init__(self, urn):
        self.urn = urn


class FakeSink:
    def __init__(self, name, cast_sink=True, compatible=True):
        self.name, self.cast_sink, self.compatible = name, cast_sink, compatible

    def get_name(self):
        return self.name

    def is_cast_sink(self):
        return self.cast_sink

    def is_compatible_with(self, source):
        return self.compatible


class FakeRoute:
    def __init__(self, route_id):
        self.id, self.sent, self.terminated = route_id, [], False

    def get_id(self):
        return self.id

    def send_route_message(self, data):
        self.sent.append(json.loads(bytes(data)))

    def terminate(self):
        self.terminated = True


class FakeRouter:
    def __init__(self):
        self.observers, self.created, self.notified = [], [], []

    def add_observer(self, observer):
        self.observers.append(observer)
        return object()

    def notify_current_sinks(self):
        self.notified.append("sinks")

    def notify_current_routes(self):
        self.notified.append("routes")

    def get_source(self, urn):
        return None if "bad" in urn else FakeSource(urn)

    def create_route(self, source, sink, callback):
        self.created.append((source, sink, callback))


def session_message(kind, session_id="s1"):
    return json.dumps({"clientId": "cefweaver1", "timeoutMillis": 0, "type": kind, "message": {
        "appId": "CC1AD845", "displayName": "Default Media Receiver", "sessionId": session_id,
        "receiver": {"volume": {"level": 0.19, "muted": False}}}}).encode()


def media_status(state, current_time=0, idle_reason=None, media_session_id=1):
    entry = {"playerState": state, "currentTime": current_time, "mediaSessionId": media_session_id,
             "playbackRate": 1, "media": {"contentId": "http://h/v.mp4", "duration": 10.0}}
    if idle_reason:
        entry["idleReason"] = idle_reason
    return json.dumps({"clientId": "cefweaver1", "timeoutMillis": 0, "type": "v2_message", "message": {
        "requestId": 12, "sessionId": "s1", "status": [entry], "type": "MEDIA_STATUS"}}).encode()


@unittest.skipIf(cefweaver is None, "cefweaver is not installed")
class CastWithoutADevice(unittest.TestCase):
    def setUp(self):
        self.router = FakeRouter()
        self.cast = cast.Cast(self.router)
        self.observer = self.router.observers[0]
        self.sink = FakeSink("Living room")

    def connect(self):
        results = []
        session = self.cast.connect(self.sink, lambda *a: results.append(a))
        source, sink, callback = self.router.created[-1]
        route = FakeRoute("route-%d" % len(self.router.created))
        callback.on_media_route_create_finished(types.MediaRouteCreateResult.OK, "", route)
        return session, route, results

    def test_it_asks_for_the_sinks_and_keeps_only_cast_sinks(self):
        self.assertEqual(self.router.notified, ["sinks", "routes"])
        heard = []
        self.cast.on_sinks = heard.append
        self.observer.on_sinks([])
        self.observer.on_sinks([self.sink, FakeSink("A TV (DIAL)", cast_sink=False)])
        self.assertEqual(heard, [[], [self.sink]])
        self.assertEqual(self.cast.sinks, [self.sink])
        self.assertIs(self.cast.find("Living room"), self.sink)
        self.assertIsNone(self.cast.find("Kitchen"))

    def test_connect_checks_the_sink_and_the_application(self):
        with self.assertRaises(ValueError):
            self.cast.connect(FakeSink("TV", cast_sink=False))
        with self.assertRaises(ValueError):
            self.cast.connect(FakeSink("Old", compatible=False))
        with self.assertRaises(ValueError):
            self.cast.connect(self.sink, application_id="bad")
        self.assertEqual(self.router.created, [])

    def test_connect_asks_for_the_default_media_receiver_with_a_client_id(self):
        session = self.cast.connect(self.sink)
        source = self.router.created[0][0]
        self.assertEqual(source.urn, "cast:CC1AD845?clientId=cefweaver1")
        self.assertEqual(session.state, "connecting")
        second = self.cast.connect(self.sink)
        self.assertNotEqual(self.router.created[1][0].urn, source.urn)
        self.assertIsNot(second, session)

    def test_a_failed_route_closes_the_session_and_reports_the_error(self):
        results, states = [], []
        session = self.cast.connect(self.sink, lambda *a: results.append(a))
        session.on_state = states.append
        self.router.created[0][2].on_media_route_create_finished(
            types.MediaRouteCreateResult.TIMED_OUT, "timed out", None)
        self.assertEqual(results, [(session, types.MediaRouteCreateResult.TIMED_OUT, "timed out")])
        self.assertEqual((session.state, states), ("closed", ["closed"]))
        with self.assertRaises(RuntimeError):
            session.play()

    def test_the_client_announces_itself_when_the_route_is_connected(self):
        session, route, results = self.connect()
        self.assertEqual(results[0][1], types.MediaRouteCreateResult.OK)
        self.assertEqual(route.sent, [])
        self.observer.on_route_state_changed(route, types.MediaRouteConnectionState.CONNECTED)
        self.assertEqual(session.state, "connected")
        self.assertEqual(route.sent, [{"type": "client_connect", "clientId": "cefweaver1",
                                       "sequenceNumber": -1, "timeoutMillis": 0}])

    def test_commands_wait_for_the_application_and_go_out_in_order(self):
        session, route, _ = self.connect()
        self.observer.on_route_state_changed(route, types.MediaRouteConnectionState.CONNECTED)
        route.sent.clear()
        session.load("http://h/v.mp4")
        session.set_volume(0.3)
        self.assertEqual(route.sent, [])
        self.assertFalse(session.ready)
        self.observer.on_route_message_received(route, memoryview(session_message("new_session")))
        self.assertTrue(session.ready)
        self.assertEqual(session.application_name, "Default Media Receiver")
        load, volume = route.sent
        self.assertEqual(load["type"], "v2_message")
        self.assertEqual(load["clientId"], "cefweaver1")
        self.assertEqual(load["message"]["type"], "LOAD")
        self.assertEqual(load["message"]["sessionId"], "s1")
        self.assertEqual(load["message"]["media"], {"contentId": "http://h/v.mp4", "contentType": "video/mp4",
                                                    "streamType": "BUFFERED"})
        self.assertTrue(load["message"]["autoplay"])
        self.assertEqual(load["message"]["media"].get("hlsSegmentFormat"), None)
        self.assertNotIn("mediaSessionId", load["message"])
        self.assertEqual(volume["message"]["volume"], {"level": 0.3})
        self.assertLess(load["sequenceNumber"], volume["sequenceNumber"])

    def ready(self):
        session, route, _ = self.connect()
        self.observer.on_route_state_changed(route, types.MediaRouteConnectionState.CONNECTED)
        self.observer.on_route_message_received(route, memoryview(session_message("new_session")))
        route.sent.clear()
        return session, route

    def test_the_controls_use_the_media_session_the_device_reported(self):
        session, route = self.ready()
        session.pause()
        self.assertEqual(route.sent[-1]["message"]["mediaSessionId"], 1)  # none reported yet
        self.observer.on_route_message_received(route, memoryview(media_status("PLAYING", media_session_id=7)))
        for call, kind, extra in ((session.play, "PLAY", {}), (session.pause, "PAUSE", {}),
                                  (session.stop, "STOP", {}),
                                  (lambda: session.seek(30), "SEEK", {"currentTime": 30.0})):
            call()
            message = route.sent[-1]["message"]
            self.assertEqual((message["type"], message["mediaSessionId"], message["sessionId"]), (kind, 7, "s1"))
            for key, value in extra.items():
                self.assertEqual(message[key], value)
        ids = [m["message"]["requestId"] for m in route.sent]
        self.assertEqual(ids, sorted(set(ids)))

    def test_the_volume_commands_go_to_the_device_and_are_checked(self):
        session, route = self.ready()
        session.set_volume(0.5)
        session.set_muted(True)
        self.assertEqual([m["message"]["volume"] for m in route.sent], [{"level": 0.5}, {"muted": True}])
        self.assertNotIn("mediaSessionId", route.sent[0]["message"])
        for bad in (-0.1, 1.5):
            with self.assertRaises(ValueError):
                session.set_volume(bad)

    def test_a_media_status_becomes_a_cast_status(self):
        session, route = self.ready()
        seen = []
        session.on_status = seen.append
        self.observer.on_route_message_received(route, memoryview(media_status("PLAYING", 4.7)))
        self.observer.on_route_message_received(route, memoryview(media_status("IDLE", 0, "FINISHED")))
        self.assertEqual([s.player_state for s in seen], ["PLAYING", "IDLE"])
        self.assertEqual((seen[0].current_time, seen[0].duration, seen[0].content_id), (4.7, 10.0, "http://h/v.mp4"))
        self.assertEqual(seen[1].idle_reason, "FINISHED")
        self.assertIs(session.status, seen[1])
        # an empty status (nothing plays) is not a state
        empty = json.dumps({"type": "v2_message", "message": {"type": "MEDIA_STATUS", "status": []}}).encode()
        self.observer.on_route_message_received(route, memoryview(empty))
        self.assertEqual(len(seen), 2)

    def test_the_volume_of_the_device_comes_from_the_session_and_from_device_updated(self):
        session, route = self.ready()
        self.assertEqual(session.volume, (0.19, False))
        seen = []
        session.on_volume = lambda level, muted: seen.append((level, muted))
        updated = json.dumps({"type": "app_message", "message": {
            "namespaceName": "urn:x-cast:com.google.cast.multizone", "sessionId": "s1",
            "message": json.dumps({"type": "DEVICE_UPDATED", "device": {"volume": {"level": 0.3, "muted": True}}})}})
        self.observer.on_route_message_received(route, memoryview(updated.encode()))
        self.observer.on_route_message_received(route, memoryview(updated.encode()))  # no change: no call
        self.assertEqual(seen, [(0.3, True)])
        self.assertEqual(session.volume, (0.3, True))

    def test_other_messages_go_to_on_message_and_bad_ones_are_ignored(self):
        session, route = self.ready()
        seen = []
        session.on_message = seen.append
        self.observer.on_route_message_received(route, memoryview(b'{"type":"receiver_action","message":{"action":"cast"}}'))
        self.observer.on_route_message_received(route, memoryview(b"not json"))
        self.observer.on_route_message_received(route, memoryview(b'{"type":"v2_message","message":null,"sequenceNumber":3}'))
        self.assertEqual([m["type"] for m in seen], ["receiver_action", "v2_message"])

    def test_disconnect_terminates_the_route_and_the_session_closes(self):
        session, route = self.ready()
        states = []
        session.on_state = states.append
        session.disconnect()
        self.assertTrue(route.terminated)
        self.observer.on_route_state_changed(route, types.MediaRouteConnectionState.TERMINATED)
        self.assertEqual((session.state, states), ("closed", ["closed"]))
        self.assertFalse(session.ready)
        with self.assertRaises(RuntimeError):
            session.pause()

    def test_a_route_that_disappears_closes_its_session(self):
        session, route = self.ready()
        other_session, other_route, _ = self.connect()
        self.observer.on_routes([other_route])
        self.assertEqual((session.state, other_session.state), ("closed", "connecting"))

    def test_close_disconnects_every_session(self):
        a, route_a = self.ready()
        b, route_b = self.ready()
        self.cast.close()
        self.assertTrue(route_a.terminated and route_b.terminated)


if __name__ == "__main__":
    unittest.main()
