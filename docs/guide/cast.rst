Cast devices (Chromecast)
=========================

:class:`cefweaver.Cast` finds Cast devices on the same network, connects to them, sends a video address and controls playback, seeking and volume. CEF gives only ``MediaRouter``, ``MediaSink`` and ``MediaRoute``; the JSON messages of the Cast protocol that playback uses are wrapped by the module ``cefweaver.cast``. This was verified on Linux x86_64 with CEF 154 and real devices (a Google Nest Hub and one other Cast device).

.. code-block:: python

   import cefweaver

   casts = []                                         # keep a reference to the Cast object

   def on_sinks(sinks):                               # called whenever the list of devices changes
       print([sink.get_name() for sink in sinks])

   def ready(cast):
       casts.append(cast)
       cast.on_sinks = on_sinks

   cefweaver.Cast.open(ready)                         # call after app.initialize()

   # after the device appears in the list
   session = cast.connect(cast.find("Living room"), lambda session, result, error: print(result, error))
   session.on_status = lambda status: print(status.player_state, status.current_time)
   session.load("http://192.168.0.10:8765/video.mp4")  # the device fetches this address itself
   session.pause(); session.play(); session.seek(30.0)
   session.set_volume(0.3); session.set_muted(False)
   session.stop()                                     # ends playback and the session (the device returns to its home screen)
   session.disconnect()                               # only ends the connection, without stopping playback

How it works
------------

- Every call is made on the thread that called ``initialize()`` (the message loop), and callbacks run on that thread. Calls return at once; results arrive in ``on_status`` (player state), ``on_volume`` and ``on_state`` (``connecting``, ``connected``, ``closed``).
- It takes time for a device to appear in the list. First an empty list arrived and a device appeared later. Wait for ``on_sinks`` or call ``cast.refresh()`` again.
- A command sent before the app opened (``load`` and so on) waits in line and goes out in order.
- A reply of the device is not paired with a request by number. Wait for the state you expect (``PLAYING``, ``PAUSED``, ``IDLE`` with ``FINISHED``).
- After ``stop()`` the app on the device ends and the session becomes ``closed``. To play again, ``connect()`` again.
- The device fetches the video address, so it must be reachable from the device (not ``localhost``). On the devices tested it played when the server sent a correct ``Content-Type`` and answered Range requests and CORS headers. An address that is refused (``403``) shows the playback bar for a moment and returns to the home screen.

What was verified and what was not
----------------------------------

Verified: finding devices (Cast sinks), playing video and sound (MP3), connecting, ``load``, ``pause``, ``play``, ``seek``, ``set_volume``, ``set_muted``, ``stop`` and ``disconnect``. A person watched the device screen: ``pause`` stopped the video, ``play`` moved it again and ``stop`` returned to the photo screen.

Take care: ``load()`` does not change the volume of the device. The speaker tested was at maximum (1.0) and quite loud, so look at ``session.volume`` before making sound and lower it with ``set_volume()`` if needed. When sent to a speaker group, only one speaker of the group made sound.

Not verified: DIAL devices (this network had none), speaker groups (a sink named like a group appeared but its behavior was not observed), mirroring a tab (CEF does not support it; CEF's own source states as intended that ``MediaRouter.get_source()`` returns ``None`` for ``http`` and ``https`` addresses and tab addresses), behavior when a device loses power or Wi-Fi, and playback on a speaker without a screen. The list of sinks differs between runs (a sink like a group came and went), so wait for ``on_sinks``. A ``GET_STATUS`` requested during playback got no answer from the device, and the status (``on_status``) keeps arriving without a request. Without a device, the logic of the library is tested with a fake router (``tests/test_cast.py``).
