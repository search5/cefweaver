Cookbook
========

Short recipes for common jobs. Each one builds on :doc:`quickstart` and :doc:`embedding`.

The recipes of the first four sections come from one script that runs without a screen (it uses :class:`~cefweaver.ui.headless.HeadlessAdapter`). It was run against the built wheel on a virtual X server (``xvfb-run python -P headless.py``) and prints ``evaluate: {'v': 'hello', 'e': None}``, ``snapshot: True True`` and ``ok ['app.test/index.html', 'sum=5']``. Here is the whole script:

.. literalinclude:: recipes/headless.py
   :language: python

Show a page from memory
-----------------------

``app.add_resource(url, html)`` answers a fake URL without a network. Add the resource once the browser exists (``on_ready``), then load it:

.. code-block:: python

   def ready():
       session.app.add_resource("http://app.test/index.html", PAGE)
       view.load_url("http://app.test/index.html")
   view.on_ready = ready

``add_resource`` raises ``RuntimeError`` before ``initialize()``, which :meth:`~cefweaver.ui.Session.start` calls.

Call Python from the page
-------------------------

Expose the function **before** ``session.start()``; the page gets a ``Promise``:

.. code-block:: python

   session.bridge.expose("add", lambda a, b: a + b)

.. code-block:: javascript

   add(2, 3).then(function (sum) { document.title = "sum=" + sum; });

An exception in the function rejects the ``Promise`` with its type and message. ``with_frame=True`` passes the calling frame as the first argument.

Run JavaScript from Python
--------------------------

``evaluate`` needs a frame and a callback ``callback(value, error)``; ``value`` is the JSON value of the result:

.. code-block:: python

   frame = view.browser.get_main_frame()
   session.bridge.evaluate(frame, "document.getElementById('t').textContent",
                           lambda value, error: print(value, error))

Save a screenshot
-----------------

``view.snapshot(path)`` writes the last painted picture as a PNG and returns ``False`` if CEF has not painted yet:

.. code-block:: python

   view.snapshot("page.png")

Wait for something without a toolkit
------------------------------------

With the headless adapter, ``adapter.run_until(condition, "what you wait for")`` runs the loop until the condition holds and raises a ``TimeoutError`` that names what you waited for. In a toolkit the loop of the toolkit runs, so you react in the hooks (``on_ready``, ``on_title``, ``on_loading``) instead.

Know when a page has loaded
---------------------------

A hook of the view tells you the loading state: ``view.on_loading = lambda loading, can_back, can_forward: ...``. To react to a frame finishing, use a ``LoadHandler`` in window mode (see :doc:`quickstart`).

Allow the microphone for one site
---------------------------------

.. code-block:: python

   widget.view.media_permissions = ui.permissions.allow_origins("https://meet.example.org")

Set the policy before the session starts. The details, including a policy as a function, are in :doc:`media`.

Add an item to the right-click menu
-----------------------------------

.. code-block:: python

   def hook(info, items):
       items.append(ui.menu.MenuItem("Show page address", action=lambda: print(info.page_url)))
       return items

   widget.view.on_context_menu = hook

More in :doc:`context-menu`.

Change a Chromium switch or the cache folder
--------------------------------------------

.. code-block:: python

   session = ui.Session(adapter,
                        switches=[("autoplay-policy", "no-user-gesture-required")],
                        cache_path="/tmp/my-app-cache")

``session.switches`` lists what CEF got (an ``ozone-platform`` may have been added; see :doc:`wayland-gpu`).

Close cleanly
-------------

Always close the browser before ending the toolkit:

.. code-block:: python

   session.shutdown(done=root.destroy)

``shutdown`` returns at once and calls ``done`` when CEF has shut down. CEF can be initialized only once per process, so build a new process for a second session.
