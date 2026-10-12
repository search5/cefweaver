Quick start
===========

There are two ways to use CEFWeaver. Putting the browser inside the window of a GUI toolkit (:mod:`cefweaver.ui`) is the usual one. You can also use the window that CEF itself creates (:class:`cefweaver.CefApp`).

In a widget of a GUI toolkit
----------------------------

The smallest program that shows a page in Tk:

.. literalinclude:: ../../examples/tk/quickstart.py
   :language: python

The other toolkits have the same shape in ``examples/<toolkit>/quickstart.py``. What the lines do:

.. list-table::
   :header-rows: 1
   :widths: 35 65

   * - Line
     - What it does
   * - ``ui.Session(TkLoop(root))``
     - The Tk event loop runs CEF. There is no extra thread and no polling.
   * - ``CefCanvas(root, session, ...)``
     - The widget that draws the browser. You size it like any Tk widget.
   * - ``canvas.on_ready``
     - Called once the browser exists; ``load_url()`` works from then on.
   * - ``canvas.on_title``
     - Called when the title of the page changes. ``on_address`` and ``on_loading`` exist too.
   * - ``session.shutdown(root.destroy)``
     - Closes the browser first and destroys the window when that is done.

With any toolkit three steps are the same: create the session, create the widget, call ``session.start(widget)``. See :doc:`embedding` for the structure.

Attaching to a Cocoa window (macOS)
-----------------------------------

If a macOS application builds its window with Cocoa or SwiftUI (``NSViewRepresentable``), the browser can become a child of that ``NSView``. CEF draws the view, so GPU compositing, input and the input method are native. Pass the address of the view as ``parent_view``:

.. code-block:: python

   import objc
   import cefweaver

   app = cefweaver.CefApp()
   pump = cefweaver.MessagePump(app)               # CEF asks for the loop when it needs it
   app.parent_view = objc.pyobjc_id(window.contentView())   # the browser fills this view
   app.initialize("https://example.org/")          # on the main thread, after the view exists
   # the Cocoa loop (NSApp.run()) runs and an NSTimer calls pump.run()

The browser follows when the view grows or shrinks. A complete example is ``examples/cocoa/quickstart.py`` (PyObjC is required). To close the window, return ``False`` from ``windowShouldClose_`` and call ``app.shutdown()`` from a timer (the wrapper detaches the view of the browser from the window and finishes the close; ``shutdown()`` completes within 0.1 seconds). A block for ``NSTimer`` must return ``None``. This works on macOS only and for browsers that are not offscreen. ``examples/swiftui/`` embeds Python in a Swift app; Python's GIL must be held only during calls (see the README in that folder).

With the window of CEF
----------------------

.. code-block:: python

   import cefweaver

   app = cefweaver.CefApp()
   app.add_javascript_binding("hello", print)    # the page calls Python as window.hello(...)
   app.initialize("https://example.com")
   while app.is_running:                         # False once the window is closed
       app.do_message_loop_work()
   app.shutdown()

A page can also come from memory, without a network:

.. code-block:: python

   app.add_resource("http://app.test/index.html", "<h1>hello</h1>")
   app.load_url("http://app.test/index.html")

Events of the browser (load, life span, display) arrive in the handlers of a ``Client``. Set it before ``initialize()``:

.. code-block:: python

   class Load(cefweaver.LoadHandler):
       def on_load_end(self, browser, frame, http_status_code):
           print("loaded", frame.get_url())

   class MyClient(cefweaver.Client):
       def __init__(self):
           self.load = Load()

       def get_load_handler(self):
           return self.load

   app.set_client(MyClient())

Window mode uses X11 on Linux (XWayland on a Wayland desktop); the reason is in :doc:`wayland-gpu`.

The CEF classes come as generated wrappers in PEP 8 style (``cefweaver.Request``, ``cefweaver.ResourceHandler``, ...). Enumerations and value types are in ``cefweaver.types`` (``types.MouseButtonType.LEFT``, ``types.Rect(0, 0, 640, 480)``); plain integers and tuples are accepted wherever they are expected.
