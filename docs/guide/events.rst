Handlers and events
===================

The events and startup hooks that CEF reports and that were verified by tests. The complete signatures are in ``cefweaver/_cefweaver.pyi``. The environment was Linux x86_64 and CEF 154.

Events of the renderer process
------------------------------

The renderer is C++, so Python code cannot run in the renderer. Instead, when you switch on ``enable_renderer_events()`` the renderer tells the browser process what happened, and ``RendererEvents`` decodes it and calls Python methods.

.. code-block:: python

   class Events(cefweaver.RendererEventHandler):
       def on_uncaught_exception(self, browser, frame, exception):      # a JavaScript error nobody caught
           print(exception.message, exception.script_name, exception.line, exception.stack[0].function_name)
       def on_focused_node_changed(self, browser, frame, node):         # the node that got focus (None if none)
           print(node and (node.tag, node.editable, node.bounds))
       def on_context_created(self, browser, frame, is_main, url): ...
       def on_context_released(self, browser, frame, is_main, url): ...

   decoder = cefweaver.RendererEvents(Events())
   # call decoder.on_process_message_received(...) from on_process_message_received of the client
   app.enable_renderer_events()                                         # before initialize() only

- If you do not switch it on, the renderer sends nothing.
- When the main frame navigates to another page, no release notice came for the previous context (it does come when an iframe is removed).

Startup hooks (``AppHandler``)
------------------------------

.. code-block:: python

   class Hooks(cefweaver.AppHandler):
       def on_before_child_process_launch(self, command_line):          # before the renderer, the GPU process and so on start
           print(command_line.get_switch_value("type"))
       def on_register_custom_preferences(self, type, registrar):       # once for global and once per request context
           registrar.add_preference("myapp.greeting", value)            # value: cefweaver.Value, valid only inside this call

   app.set_app_handler(Hooks())                                         # before initialize() only

Read and change a registered preference with ``request_context.has_preference()``, ``get_preference()`` and ``set_preference()``.

Handlers the client returns
---------------------------

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Handler
     - What it receives
   * - ``FindHandler``
     - The results of ``browser.get_host().find(...)`` (``on_find_result``). The ordinal of the first result is 0.
   * - ``FrameHandler``
     - Frames being created and destroyed, and the replacement of the main frame.
   * - ``AccessibilityHandler``
     - The accessibility tree after ``set_accessibility_state(ENABLED)``.
   * - ``RequestHandler.on_select_client_certificate``
     - The choice of the client certificate that a server asks for.

The find and frame handlers are returned by ``get_find_handler()`` and ``get_frame_handler()`` of the ``Client``. Read certificate information not from ``on_certificate_error`` but with ``browser.get_host().get_visible_navigation_entry().get_ssl_status()``.

What else is open
-----------------

- **HTTP server**: with ``Server`` and ``ServerHandler`` Python answers the HTTP server of CEF.
- **Changing a response body**: ``ResponseFilter`` (returned by ``ResourceRequestHandler.get_resource_response_filter``).
- **Developer tools**: ``browser.get_host().show_dev_tools()`` opens a window of its own. Opening again right after closing is ignored, so run ``do_message_loop_work()`` for a moment first.
- **Shared-memory messages**: ``SharedProcessMessageBuilder.write()`` and ``SharedMemoryRegion.to_bytes()`` exchange bytes by copying.
- **Tracing**: ``begin_tracing()`` and ``end_tracing(file, callback)``.
- **Media router and component updater**: ``request_context.get_media_router()`` and ``ComponentUpdater`` (the easy way to use Cast devices is :doc:`cast`). The tests assume an environment without Cast devices (zero sinks and routes). Separately, a real Chromecast (a Google Nest Hub and so on) was used once to check finding sinks, device information, creating and ending routes, sending and receiving route messages and media playback (``PLAYING`` and ``FINISHED`` after ``LOAD``); this is not an automated test and needs a device. Mirroring a tab was not verified.

A function like ``is_rtl()`` (``CefIsRTL``), which kills the process when called before CEF starts, raises ``RuntimeError`` when called before the start.
