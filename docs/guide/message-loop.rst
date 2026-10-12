The message loop
================

CEF does its work when the program lets it: nothing happens (no page loads, no callback runs) unless :meth:`~cefweaver.CefApp.do_message_loop_work` is called on the thread that called :meth:`~cefweaver.CefApp.initialize`. Every handler, binding and exposed function of :doc:`concepts` runs inside that call. There are three ways to call it:

- **Under a toolkit** you do nothing: :class:`~cefweaver.ui.Session` runs it from the event loop of the toolkit (:doc:`embedding`).
- **A loop of your own** that calls ``do_message_loop_work()`` over and over (below).
- **A loop of your own with** :class:`~cefweaver.MessagePump`, which tells you when CEF wants to run, so the loop can sleep in between.

A loop that polls
-----------------

.. literalinclude:: recipes/message_loop.py
   :language: python

The page calls ``finish()`` after 100 ms; the binding closes the browser, :attr:`~cefweaver.CefApp.is_running` becomes ``False`` and the loop ends. The script was run against the built wheel on a virtual X server (``xvfb-run python -P message_loop.py``) and printed, in three runs in a row:

.. code-block:: text

   ['finish() called by the page']
   the loop ran: True - is_running: False
   shut down

Points about this loop:

- The call returns after one round of CEF's work. How often to call it is up to the program; the docstring says to call it regularly. The scripts of this guide sleep 5 ms between calls.
- A callback runs inside the call, so a callback that takes a second delays every page and window by a second.
- On macOS, when ``Settings.external_message_pump`` is not set, ``do_message_loop_work()`` also handles the pending events of the application, which the windows made by CEF need for input, title and closing.
- ``do_message_loop_work()`` raises ``RuntimeError`` before ``initialize()`` and after ``shutdown()``.

The loop is the place to put your own work too, as long as each turn stays short. :doc:`quickstart` shows the same loop with the window of CEF, and the headless adapter of :doc:`cookbook` has its own (``run_until``).

A loop that waits for CEF
-------------------------

A program with an event loop of its own (a GUI toolkit, ``asyncio``, a ``select`` loop) should not poll. With ``Settings.external_message_pump`` set, CEF calls :meth:`~cefweaver.AppHandler.on_schedule_message_pump_work` when it wants a run, from any of its threads, with the delay in milliseconds. :class:`~cefweaver.MessagePump` implements the protocol around that hook:

- A new request replaces the pending one (a delay of zero or less means now).
- The wait between two runs never exceeds 1/30 s, because not every kind of work is announced.
- ``wake(delay)``, the optional second argument of the constructor, is called for each request with the seconds until the run. It may be called from any thread, so it should only wake your loop (set an event, write to a pipe, ask the toolkit to call a function later).
- :meth:`~cefweaver.MessagePump.timeout` gives the seconds until the next run is due.
- :meth:`~cefweaver.MessagePump.run` calls ``do_message_loop_work()`` if a run is due and returns whether it did. Call it on the thread that called ``initialize()``.

The constructor sets ``external_message_pump`` and installs the pump as the app handler, so create it **before** ``initialize()``. The loop below sleeps on an event until CEF asks for work:

.. literalinclude:: recipes/message_pump.py
   :language: python

It printed, in three runs in a row:

.. code-block:: text

   external_message_pump: True
   ['the page has run']
   [('task from a thread, on the initialize() thread:', True)]
   runs: True - longest wait <= 1/30 s: True
   shut down

The loop never polls: it sleeps for ``pump.timeout()`` at most, and the event ends the sleep early when CEF announces work. The page loaded and the binding ran this way. The task that a timer thread posted with :func:`~cefweaver.post_task` ran on the thread of the loop, inside a ``pump.run()``. A task posted from another thread makes CEF announce work, which wakes a sleeping loop; the test ``test_a_task_from_a_thread_wakes_the_message_pump_of_the_application`` of the repository checks it.

:class:`~cefweaver.ui.Session` is this loop for a toolkit: its ``wake`` posts a function to the main thread with ``adapter.post``, that function arms ``adapter.call_later(pump.timeout(), ...)``, and the timer calls ``pump.run()``.

When CEF owns the window
~~~~~~~~~~~~~~~~~~~~~~~~

The external pump is meant for programs where a toolkit owns the window and its events (offscreen rendering, or a native window of the toolkit). With windows that CEF makes itself (Views), mouse and key input of the window did not arrive when the loop was driven by a pump; use a polling loop there. This was found on Linux X11 only and the cause was not looked for in the source of CEF. Details are in :doc:`views` and :doc:`limitations`.

Stopping
--------

A loop ends for one of these reasons, and after it you call :meth:`~cefweaver.CefApp.shutdown`:

- ``is_running`` became ``False``: every browser is closed. Closing the browser from code (``browser.get_host().close_browser(True)``, as in the script) does it, and so does the user closing the window of a browser that CEF made. A popup closing alone leaves ``is_running`` true.
- Your own condition holds (a flag set by a callback, a quit command of the toolkit).
- With ``initialize(None)`` there is no first browser and ``is_running`` stays true until ``shutdown()``. Watch for the end of your windows yourself (for Views, ``WindowDelegate.on_window_destroyed``, see :doc:`views`).

``shutdown()`` closes the browsers that are left and waits for them by running the message loop itself (up to about 5 seconds for the browsers of the application, then up to about 5 seconds more for any others that are still open, such as a Views window), so it needs no loop of yours around it; both scripts above call it as the last step. Under a toolkit call :meth:`~cefweaver.ui.Session.shutdown`, which returns at once and calls ``done`` when CEF has shut down; do not end the toolkit before that.
