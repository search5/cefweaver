Views (without a toolkit)
=========================

You can build windows with CEF alone. The **Views framework** of CEF draws the window, toolbars, buttons, text fields, layouts and the browser itself and handles mouse and key input. The program assembles views and reacts in delegates (callbacks). Unlike :doc:`embedding`, which draws an offscreen picture into a toolkit widget, the browser here is drawn into the own window of CEF.

.. note::

   This page was verified on Linux x86_64 (X11). Windows, macOS and Wayland were not verified.

Classes
-------

The classes follow the inheritance of CEF. ``Window`` is a subclass of ``Panel``, and ``Panel`` of ``View``. ``BrowserView``, ``Button`` (``LabelButton``, ``MenuButton``), ``Textfield`` and ``ScrollView`` are subclasses of ``View`` too. An object of a subclass can be passed wherever the base class is expected. In the other direction, an object that CEF returns as ``View`` arrives as the class of its real kind (a ``Window`` as ``Window``, a ``LabelButton`` as ``LabelButton``).

Starting
--------

``initialize(None)`` starts CEF **without a first browser**; then you create a ``BrowserView`` and a ``Window``. ``WindowDelegate.on_window_created`` is called when the window exists, which is where you attach the views.

.. code-block:: python

   import cefweaver as cef
   from cefweaver import types

   class Window(cef.WindowDelegate):
       def __init__(self, browser_view):
           super().__init__()
           self.browser_view = browser_view
       def on_window_created(self, window):
           window.add_child_view(self.browser_view)
           window.show()
       def on_window_destroyed(self, window):
           global done
           done = True
       def can_close(self, window):
           return True

   app = cef.CefApp()
   app.initialize(None)
   view = cef.BrowserView.create_browser_view(cef.Client(), "https://example.org/", types.BrowserSettings(), None, None, cef.BrowserViewDelegate())
   cef.Window.create_top_level_window(Window(view))
   done = False
   while not done:
       app.do_message_loop_work()
   app.shutdown()

A full example with a toolbar (buttons and an address field) is in ``examples/views/`` (``quickstart.py``, and ``smoke.py``, which checks it with real X events).

Good to know
------------

- **The loop must poll ``do_message_loop_work()`` often.** CEF owns the window, so CEF has to process the events of the window system itself. With a ``MessagePump`` (``external_message_pump``) CEF only does the work it announced and does not process the X11 events of its own window: pressing a button never delivered ``on_button_pressed``.
- **You may call ``shutdown()`` while a window is open.** ``shutdown()`` closes the remaining browsers first and then shuts CEF down (it used to crash with a segmentation fault). Still, the ``on_window_destroyed`` call is the clearer signal that a window closed.
- **The same CEF view is a different Python object every time.** To tell the buttons apart in a delegate, give each one a number with ``set_id`` and compare ``get_id()``.
- After ``initialize(None)`` you cannot use ``app.create_browser()`` (a first browser is required; it raises ``RuntimeError``). ``app.load_url()`` and ``app.execute_javascript()`` do not apply to a browser started by ``initialize(None)`` or to the browser of a Views window; they return ``False``. For such a browser use the frame: ``view.get_browser().get_main_frame().load_url(...)``.
- ``View.get_delegate()``, ``BrowserHost.get_client()`` and ``RequestContext.get_handler()`` return the Python object you gave CEF (``None`` for what CEF made). ``BrowserViewDelegate.get_delegate_for_popup_browser_view`` was called when the client of the view that opens the popup had a ``LifeSpanHandler``; ``WindowDelegate.get_parent_window`` works too. More in :doc:`limitations`.
