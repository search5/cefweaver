Sound, microphone and camera
============================

Playing the sound of a page
---------------------------

By default CEF (Chromium) plays the sound directly on the system audio. If the application wants to receive and handle the sound, it gives the view ``audio=``.

.. code-block:: python

   widget = CefCanvas(root, session, audio="auto")       # to the constructor of the widget of the toolkit

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - ``audio=``
     - Meaning
   * - not given (``None``)
     - CEF plays the sound.
   * - ``"auto"``
     - The sink of the toolkit if there is one, otherwise pygame. If neither exists, CEF plays.
   * - a sink object
     - Your own sink is used.

- **Sinks of toolkits**: Qt has ``QtSink`` (QtMultimedia) and SDL2 has ``SdlSink``. GTK 3, Tk, wx and Kivy have no playback API, so they use pygame (``cefweaver[pygame]``).
- **The shape of a sink**: three methods, ``start(sample_rate, channels)``, ``write(samples, frames)`` and ``stop()``. ``samples`` holds ``frames * channels`` little-endian float32 values with the channels interleaved. ``write`` is called on the audio thread of CEF, so it must not block.
- **Errors**: if a sink raises, the sink is detached and ``view.on_audio_error(message)`` is called once. CEF does not play after that, so there is no sound.
- **Muting**: ``view.audio_muted = True``.
- To control loudness, adjust the ``volume`` of the sink (0.0 to 1.0).

.. note::

   When the application plays the sound instead of CEF, video and sound can drift apart by the latency of the sink (tens of milliseconds up to about 100 ms). In the tests a YouTube video played at the speed of the clock without breaks.

Microphone and camera
---------------------

When a page asks for the microphone or the camera with ``getUserMedia``, the application decides with a **policy**. Without a policy the answer is the default of CEF: **deny**.

.. code-block:: python

   from cefweaver import ui

   widget.view.media_permissions = ui.permissions.allow_origins("https://meet.example.org")
   session.start(widget)                                 # give the policy before the session starts

``allow_origins(...)`` gives the microphone and the camera to the listed origins only, and never screen capture. For finer decisions write the policy as a function:

.. code-block:: python

   def policy(request):
       # request.origin, request.permissions (types.MediaAccessPermissionTypes), request.is_main_frame
       if request.origin.startswith("https://meet.example.org"):
           request.allow()                               # everything asked; request.allow(permissions) grants part of it
       else:
           request.deny()

   widget.view.media_permissions = policy

- You may answer **now** or **later** (after asking the user). An answer counts once.
- If the policy raises, the request is denied and the error is reported.
- When allowed, Chromium receives sound and video **directly from the system devices**. In the tests a microphone (48 kHz) and a USB webcam (640x480, about 30 fps) opened and delivered data.
- There is not yet a way for the application to supply sound or video in place of the device (a file, a virtual device, another mixer).

.. note::

   If the microphone is muted in the system, the device opens but the track is ``muted`` and no sound arrives. When no sound arrives, check the input mute of the system first.
