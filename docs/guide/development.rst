Development
===========

Tests
-----

The tests target the installed wheel and run on a virtual X server. From the repository root:

.. code-block:: sh

   uv build --wheel
   env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v

- **``-P`` is required.** Without it the source ``cefweaver/`` in the repository root hides the installed wheel, the tests that use CEF are skipped silently, and the run still ends with ``OK``.
- ``env -u WAYLAND_DISPLAY`` and ``xvfb-run`` keep the tests from opening windows on the real screen.
- The tests use no external network. The answer for a fake URL comes from ``app.add_resource()``, and conditions are awaited with ``wait_until`` and not with a fixed time.
- A test that starts CEF runs in a new process each time (CEF can be initialized once per process).

The toolkit examples are checked with their own ``smoke.py``. For Qt, for example:

.. code-block:: sh

   cd examples/qt
   env -u WAYLAND_DISPLAY QT_QPA_PLATFORM=xcb xvfb-run -a uv run python smoke.py

The binding generator
---------------------

The Python bindings are generated from the CEF headers (``tools/gen/``) instead of being carried over by hand.

.. code-block:: sh

   python tools/gen/generate.py            # update the generated files
   python tools/gen/generate.py --check    # check that they are up to date (also part of the tests)
   python tools/gen/generate.py --report   # print the coverage report

Do not edit the generated files (``native/cefwrapper/generated/``, ``cefweaver/cef_api.*``, ``cefweaver/api/``, ``cefweaver/types/`` and ``cefweaver/_cefweaver.pyi``). When you change the CEF version, run ``generate.py`` after ``prepare.py``. Names follow PEP 8 (``CefResourceHandler`` becomes ``ResourceHandler``, ``GetURL`` becomes ``get_url``). The comments of the headers become the docstrings of this documentation.

Checking video and sound
------------------------

``tests/playback_check.py`` is a manual tool that checks whether a real YouTube video plays and the sound reaches the sink. It is not in the test suite (it depends on the network and on YouTube). ``--audio`` checks the sound sink and ``--loud`` checks real sound; ``--loud`` really makes sound and opens a window on the real screen.

Building this documentation
---------------------------

The documentation is made from the docstrings in the source, with Sphinx and the Read the Docs theme. English is the source and Korean is a gettext catalog (``sphinx-intl``).

.. code-block:: sh

   pip install -r docs/requirements.txt
   cd docs
   make html            # _build/html/en; fails on a warning (-W) and on a broken reference (nitpicky)
   make html-all        # English and Korean
   make update-po       # refresh the catalogs in locale/ko after the source text changed

The autodoc extension imports the compiled extension, so install the wheel into the environment first. To read the Qt modules, PyQt6 and Pillow are also needed.

``make site`` builds both languages and a start page, the way GitHub Pages serves them. The workflow ``.github/workflows/docs.yml`` builds the wheel on a Linux runner, runs ``make site`` with it and publishes ``docs/_build/html``; it needs Settings, Pages, Source set to "GitHub Actions".

The wiki
--------

The repository root has a working wiki, ``llm-wiki/``, that is kept together with an LLM. It holds the structure, the code and design decisions, verified facts (experiment records) and what could not be verified. It is an **internal record that is not published**, and it is kept in step with the code in the same change. ``python llm-wiki/lint.py`` checks it.
