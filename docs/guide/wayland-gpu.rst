Wayland and GPU
===============

On Linux Chromium works on either X11 or Wayland (the ``ozone-platform`` switch). CEFWeaver picks a different default depending on the use.

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Use
     - Default
     - Reason
   * - :mod:`cefweaver.ui` (offscreen, ``ui.Session``)
     - ``wayland`` if a Wayland compositor exists, otherwise Chromium chooses
     - Offscreen is fine on Wayland, and on some machines the GPU dies on X11 and no video appears.
   * - :class:`cefweaver.CefApp` (window mode)
     - ``x11`` if ``DISPLAY`` is set (XWayland on a Wayland desktop)
     - A window in window mode cannot be closed from code on Wayland.

"A Wayland compositor exists" means that the socket ``WAYLAND_DISPLAY`` points to really exists. If the application gives ``ozone-platform`` or ``ozone-platform-hint`` itself, that is followed as given.

.. code-block:: python

   session = ui.Session(loop, switches=[("ozone-platform", "x11")])    # go back to X11

Offscreen and Wayland
---------------------

With the GPU on, video (YouTube), sound and WebGL work on Wayland. It was the same in the offscreen browsers of GTK 3, Qt, Tk, SDL2, wxPython and Kivy. An offscreen browser has no native window, so the window-mode problem below does not occur.

When the GPU is on with X11
---------------------------

On some machines the GPU process dies again and again on X11 (XWayland) and video playback fails (``error.code`` of ``<video>`` is 3, and the log has ``gbm_bo_import`` and ``could not create backing``). The environment was a laptop (GNOME) with an AMD integrated GPU and an NVIDIA discrete GPU. On the same machine the installed Chrome works on X11 too, and the example application of CEF (``cefsimple``) gives the same error, so it is a problem of the X11 path of CEF and not of CEFWeaver. The cause was not found.

If you must use X11, these are workarounds:

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Switch
     - Effect
   * - ``disable-gpu``
     - Video plays. **WebGL is gone** (there is no software fallback).
   * - ``disable-accelerated-video-decode``
     - In window mode all 3 runs passed; offscreen 2 of 3 passed. Not a complete fix.

.. note::

   Only one machine was tested. A machine with a single GPU, or another compositor (KDE, Sway and so on), was not verified. If you hit the problem, switch the ``ozone-platform`` switch between ``x11`` and ``wayland``.

Window mode and Wayland
-----------------------

A window made by ``CefApp`` appears on Wayland and the page runs well. The problem is **closing from code**. ``close_browser()`` does not finish, and calling ``shutdown()`` in that state ends the process abnormally inside ``CefShutdown()``. Adding the close call to an example of CEF without the wrapper (``cefsimple --use-native``) makes X11 exit normally and Wayland never finish, so this is a limit of CEF. Closing with the close button of the window was not tested. That is why window mode uses X11 by default.
