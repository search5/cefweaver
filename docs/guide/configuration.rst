Configuration
=============

What you can set before CEF starts, where each setting goes, the environment variables that matter and where files are. The statements were checked with the installed wheel (CEF 154, Python 3.13) on Linux x86_64 on a virtual X server, offscreen. A statement that comes from the source or a docstring and was not run is marked "source". Windows and macOS were not tried for this page; see :doc:`limitations`.

Everything here must be set **before** CEF is initialized (``CefApp.initialize()``, which :meth:`~cefweaver.ui.Session.start` calls). After that the setters raise ``RuntimeError`` (the messages are in :doc:`troubleshooting`).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Where
     - What
   * - ``CefApp.settings`` (:class:`~cefweaver.Settings`)
     - The fields of CEF's settings struct: user agent, log, remote debugging, locale and others.
   * - ``CefApp.add_command_line_switch()``, ``Session(switches=...)``
     - Chromium command line switches.
   * - ``set_cache_path()``, ``set_resources_path()``, ``set_subprocess_path()``
     - Folders and the helper executable. ``Session(cache_path=...)`` calls the first.
   * - :class:`~cefweaver.AppHandler`
     - Hooks into the command line, the custom schemes and the start of the context.
   * - ``CefApp.offscreen``, ``transparent``, ``shared_texture``, ``windowless_frame_rate``, ``parent_view``, ``browser_settings``
     - Properties of the browsers; see the docstrings of :class:`~cefweaver.CefApp`.

One script sets several of them and reads the result back from the page and from CEF:

.. literalinclude:: recipes/configuration.py
   :language: python

Run with ``LANGUAGE=en LANG=en_US.UTF-8 xvfb-run -a python -P configuration.py`` it prints:

.. code-block:: text

   page: {'ua': 'MyApp/1.0', 'gc': 'function', 'language': 'en-US', 'location': 'myapp://app', 'secure': True}
   switches: {'autoplay-policy': 'no-user-gesture-required', 'js-flags': '--expose-gc', 'lang': 'ko', 'no-sandbox': '', 'ozone-platform': 'x11', 'user-agent': 'MyApp/1.0'}
   before the application's switches: False | process type: ''
   scheme registered: True
   remote debugging: True
   log file written: True
   cache folder: ['Default', 'Local State']
   after initialize: the settings cannot change after initialize()

The output is the same in three runs in a row. The sections below explain it.

Settings
--------

:class:`~cefweaver.Settings` holds the fields below. A field left at ``None`` is not given to CEF, which uses its own default. A wrong type raises ``TypeError``, a value out of range ``ValueError``, a name that is not a field ``AttributeError`` (``Settings(foo=1)`` raises ``TypeError``). Assigning after initialization raises ``RuntimeError``. The messages are in :doc:`troubleshooting`. The fields are the ones of ``Settings`` in the wheel and in the source; the meaning is the docstring (source):

.. list-table::
   :header-rows: 1
   :widths: 32 14 54

   * - Field
     - Type
     - Meaning
   * - ``user_agent``
     - ``str``
     - Replaces the default user agent.
   * - ``user_agent_product``
     - ``str``
     - The product token of the default user agent, such as ``Product/1.2``.
   * - ``locale``
     - ``str``
     - The UI locale, such as ``ko``. On Linux the language of the pages follows ``LANGUAGE`` and ``LANG`` instead (see below).
   * - ``log_file``, ``log_severity``
     - ``str``, :class:`~cefweaver.types.LogSeverity`
     - The log file and the level. The levels are ``DEFAULT``, ``VERBOSE``, ``INFO``, ``WARNING``, ``ERROR``, ``FATAL`` and ``DISABLE``, which writes nothing.
   * - ``javascript_flags``
     - ``str``
     - Flags for V8, such as ``--expose-gc``.
   * - ``remote_debugging_port``
     - ``int``
     - The port of the remote debugging server, 1024 to 65535; 0 or unset turns it off. A port below 1024 raises ``ValueError``.
   * - ``root_cache_path``
     - ``str``
     - The folder of the profile data (see "Files").
   * - ``persist_session_cookies``
     - ``bool``
     - Keep session cookies in the cache folder across restarts.
   * - ``command_line_args_disabled``
     - ``bool``
     - Ignore the command line arguments of the process.
   * - ``external_message_pump``
     - ``bool``
     - The application runs the message loop when :meth:`~cefweaver.AppHandler.on_schedule_message_pump_work` says so. See :doc:`message-loop`. :class:`~cefweaver.ui.Session` uses a :class:`~cefweaver.MessagePump`.
   * - ``chrome_policy_id``
     - ``str``
     - The id of the Chrome policy that applies to the app.
   * - ``uncaught_exception_stack_size``
     - ``int``
     - The number of frames in the stack trace of an uncaught JavaScript exception.
   * - ``background_color``
     - ``int``
     - ARGB (``0xAARRGGBB``) where the page draws nothing.
   * - ``cookieable_schemes_list``, ``cookieable_schemes_exclude_defaults``
     - ``str``, ``bool``
     - The schemes that may have cookies, separated by commas, and whether ``http``, ``https``, ``ws`` and ``wss`` are left out of the default list.

What the script above showed:

- ``user_agent`` reached the page (``navigator.userAgent``), and ``javascript_flags="--expose-gc"`` made ``gc`` a function in the page.
- ``log_file`` was written, and ``remote_debugging_port`` opened a server: ``/json/version`` on that port answered with the Chromium version. The port number must be free (the script picks one).
- ``locale="ko"`` became the switch ``lang=ko`` on the command line, and **the page language stayed** ``en-US`` while ``LANGUAGE=en``. In a run with ``LANGUAGE=ko:en`` and the same setting the page language was ``ko-KR``. So on Linux the language of pages is set through ``LANGUAGE`` and ``LANG``, not through this field. The docstring of ``locale`` (the same in the wheel and in the source) says the same.
- The settings that have a switch appear on the command line of the browser process: ``js-flags``, ``lang``, ``log-file``, ``log-severity``, ``remote-debugging-port``, ``user-agent``, and ``no-sandbox`` (below).
- The fields that were not run: ``user_agent_product``, ``root_cache_path`` (see "Files"), ``persist_session_cookies``, ``command_line_args_disabled``, ``chrome_policy_id``, ``uncaught_exception_stack_size``, ``background_color``, ``cookieable_schemes_*``, and ``external_message_pump``. :class:`~cefweaver.ui.Session` sets ``external_message_pump`` itself: printing ``session.app.settings`` right after creating a session shows ``external_message_pump=True``.
- Not a field: the sandbox, the cache path (``set_cache_path()``), the resources and subprocess paths.

Command line switches
---------------------

.. code-block:: python

   session = ui.Session(adapter, switches=[("autoplay-policy", "no-user-gesture-required")])
   # window mode and any CefApp:
   app.add_command_line_switch("disable-gpu")                  # a switch without a value
   app.add_command_line_switch("disable-features", "EnableOopPrintDrivers")

``add_command_line_switch(name, value="")`` adds a switch; an empty value adds a bare switch (``no-sandbox`` shows as ``''`` in the output above). ``Session(switches=...)`` takes ``(name, value)`` pairs and keeps the list as ``session.switches``; it holds the ``ozone-platform=wayland`` that ``Session`` adds (see below), and not the ``ozone-platform=x11`` that ``CefApp`` adds on its own. The switch that was given reached the browser process (``autoplay-policy`` above).

- **Added by cefweaver.** If neither ``ozone-platform`` nor ``ozone-platform-hint`` is given, ``CefApp.initialize()`` adds ``ozone-platform=x11`` when ``DISPLAY`` is set (the output above has it), and ``Session`` adds ``ozone-platform=wayland`` when a Wayland compositor exists. See :doc:`wayland-gpu`. If the request handler of the client overrides ``get_auth_credentials``, ``CefApp.initialize()`` adds ``disable-chrome-login-prompt`` (source).
- **Hooks.** :meth:`~cefweaver.AppHandler.on_before_command_line_processing` gets the command line of the browser process (``process_type`` is ``''``) and may change it; it is called before the switches of ``add_command_line_switch`` are added (``autoplay-policy`` was not yet in it in the script above). :meth:`~cefweaver.AppHandler.on_before_child_process_launch` changes the command line of the renderer, GPU and utility processes (source; not run here). Give the handler with :meth:`~cefweaver.CefApp.set_app_handler`.
- **Read back.** ``cefweaver.CommandLine.get_global_command_line().get_switches()`` is what the browser process has.
- **Used in this guide:** ``autoplay-policy`` (:doc:`cookbook`), ``disable-gpu``, ``disable-accelerated-video-decode`` and ``ozone-platform`` (:doc:`wayland-gpu`), ``disable-features=EnableOopPrintDrivers`` (:doc:`printing`). Other Chromium switches were not tried.

Custom schemes
--------------

A scheme of your own (``myapp://app/index.html``) needs three things, shown in the script: register the scheme in :meth:`~cefweaver.AppHandler.on_register_custom_schemes`, register a :class:`~cefweaver.SchemeHandlerFactory` with :func:`cefweaver.register_scheme_handler_factory`, and answer the request with a :class:`~cefweaver.ResourceHandler`.

.. code-block:: python

   class Hooks(cefweaver.AppHandler):
       def on_register_custom_schemes(self, registrar):
           registrar.add_custom_scheme("myapp", types.SchemeOptions.STANDARD | types.SchemeOptions.SECURE)

   app.set_app_handler(Hooks())
   # after initialize (here in on_ready):
   cefweaver.register_scheme_handler_factory("myapp", "app", Factory())

- The options are :class:`~cefweaver.types.SchemeOptions` flags (``STANDARD``, ``LOCAL``, ``DISPLAY_ISOLATED``, ``SECURE``, ``CORS_ENABLED``, ``CSP_BYPASSING``, ``FETCH_ENABLED``). The renderer processes get the same schemes: with ``STANDARD | SECURE`` the page saw ``location.host == 'app'`` and ``isSecureContext`` true. Without ``STANDARD`` only the ``scheme:`` part is parsed (docstring of ``SchemeOptions``; not run).
- ``add_custom_scheme`` returns ``True`` when CEF took the scheme, and it raises ``RuntimeError`` outside the hook. The registrar is valid during the hook only.
- The domain argument of ``register_scheme_handler_factory`` matches the host of a standard scheme; an empty one matches every host, and it is ignored for a non-standard scheme (docstring).
- For ``http`` and ``https`` URLs served from memory there is a shorter way: ``CefApp.add_resource()`` (:doc:`cookbook`).

Environment variables
---------------------

.. list-table::
   :header-rows: 1
   :widths: 24 76

   * - Variable
     - Effect
   * - ``DISPLAY``
     - ``CefApp.initialize()`` adds ``ozone-platform=x11`` when it is set (run). Offscreen browsers ran with it unset (the browser started and shut down; one ``GLib-GObject`` line was printed), but the window of ``CefApp`` ended the process with exit status 133 (see :doc:`troubleshooting`).
   * - ``WAYLAND_DISPLAY``, ``XDG_RUNTIME_DIR``
     - ``ui.Session`` chooses ``ozone-platform=wayland`` if ``WAYLAND_DISPLAY`` names a socket that exists, as an absolute path or relative to ``XDG_RUNTIME_DIR``. :func:`cefweaver.ui.session.default_ozone_platform` returned ``'wayland'`` for an existing socket, in both forms, and ``None`` for a missing socket, a relative name without ``XDG_RUNTIME_DIR``, and an empty environment (run). The Wayland session itself was not used for this page.
   * - ``LANGUAGE``, ``LANG``
     - The language of the pages and the language of Chromium's own messages on Linux (run: the text of a print error was English with ``LANGUAGE=en`` and Korean in the default environment of the machine, ``LANGUAGE=ko:en``).
   * - ``CEFQT_BINDING``
     - ``pyqt6`` or ``pyside6``. Without it, or with another value, PyQt6 is used if installed and otherwise PySide6 (source: ``cefweaver.ui.toolkits.qt``; not run).
   * - ``SDL_VIDEODRIVER``, ``SDL_HINT_RENDER_DRIVER``
     - ``cefweaver.ui.toolkits.sdl2`` sets them with ``setdefault``: ``x11`` on Linux (never the real Wayland session) and ``software``. A value you set first is kept (source; not run).
   * - ``PYGAME_HIDE_SUPPORT_PROMPT``
     - Set with ``setdefault`` to ``1`` when the pygame audio fallback is used (source).
   * - ``CEF_ROOT``
     - Build time only: the CEF distribution that ``uv build --wheel`` and ``tools/prepare.py`` use (:doc:`installation`).

The examples read a few of their own (``CEFSDL_SWITCHES``, ``CEFKIVY_SWITCHES``, ``KIVY_NO_ARGS``); they are not part of the package.

Files
-----

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Path
     - What
   * - ``site-packages/cefweaver/``
     - The package and the runtime. In the installed wheel: ``libcef.so``, ``icudtl.dat``, ``resources.pak``, ``chrome_100_percent.pak``, ``chrome_200_percent.pak``, ``v8_context_snapshot.bin``, ``locales/``, ``libvk_swiftshader.so``, ``libvulkan.so.1``, ``vk_swiftshader_icd.json`` and ``cefsubprocess`` next to ``_cefweaver.*.so``. There is no ``chrome-sandbox``. (``ls`` of the installed package.)
   * - ``./cache/``
     - The cache and profile folder when no ``cache_path`` is given: relative to the **working directory** of the process (run). Pass ``cache_path`` (:class:`~cefweaver.ui.Session`) or ``set_cache_path()``.
   * - ``<cache>/Default/``, ``<cache>/Local State``, ``<cache>/SingletonLock``
     - Created by CEF in the cache folder (run; a few of the many entries). ``Default/`` and ``Local State`` are the profile. The singleton files are what makes a second process with the same folder fail (:doc:`troubleshooting`).
   * - ``<cache>/chrome_debug.log``
     - The log when ``log_file`` is not set (run: present after a start and shutdown with no log settings). The docstring of ``Settings.log_file`` says the default is ``debug.log`` in the executable's directory; on Linux with a cache folder the file was ``chrome_debug.log`` in the cache folder, and no ``debug.log`` was found in the folder of the ``python`` executable.
   * - ``log_file``
     - The path you give; written (run).
   * - Standard error
     - Nearly silent by default: the cookbook script and ``start_only.py`` wrote no byte there in three runs. Lines appear for some errors (see :doc:`troubleshooting`), and with ``remote_debugging_port`` set Chromium prints ``DevTools listening on ws://...``.

``set_resources_path()`` sets ``resources_dir_path`` and ``locales_dir_path`` (the ``locales`` folder below it); it is optional, and the docstring and a comment in the source say that on Linux CEF looks for ``icudtl.dat`` next to ``libcef.so`` whatever it is set to (source; the path setters were not run). ``set_subprocess_path()`` sets the helper executable, which by default is ``cefsubprocess`` next to the extension module (source).

**Root cache path.** ``root_cache_path`` is the folder of the profile data. Source: a ``cache_path`` that lies outside it gives way to the root. Run (three times each, with ``root_cache_path`` set to ``root`` and ``cache_path`` either ``root/profile-a`` or a folder outside ``root``): in both cases ``Default/`` and the other entries were created in ``root``, and ``root/profile-a`` stayed empty. What a second profile folder is for in CEF 154 was not explored.

**Two processes.** Two processes with the same cache folder cannot both run CEF; the second one fails in ``initialize()`` (:doc:`troubleshooting`). Give each its own ``cache_path``.

The sandbox
-----------

CEFWeaver starts CEF with ``no_sandbox`` set (source: ``native/cefwrapper/library.cpp``). In a run with a renderer, a GPU process, utility processes and the zygote, every ``cefsubprocess`` child had ``--no-sandbox`` on its command line (three runs; the browser process shows ``no-sandbox`` in the output above). The wheel does not contain ``chrome-sandbox``, and :class:`~cefweaver.Settings` has no field to turn the sandbox on. So the processes that run the pages you load are started without the Chromium sandbox. Whether a build with a sandbox is possible was not tried. On Windows the sandbox library of CEF is not linked (:doc:`limitations`).
