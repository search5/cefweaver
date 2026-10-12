cefweaver
=========

Python bindings for the Chromium Embedded Framework (CEF) with an optional layer that puts the
browser into the widgets of GUI toolkits (Qt, GTK 3, Tk, SDL2, wxPython, Kivy, pywin32).

* The CEF API is generated from the CEF headers; its descriptions are the comments of those headers.
* :mod:`cefweaver.ui` shows an offscreen browser in a toolkit widget and handles mouse, keyboard,
  input method, clipboard and drag and drop.
* The guide explains how to use it; the reference is generated from the docstrings of the source code.

.. code-block:: python

   import tkinter

   from cefweaver import ui
   from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

   root = tkinter.Tk()
   session = ui.Session(TkLoop(root))
   canvas = CefCanvas(root, session, width=900, height=640)
   canvas.pack(fill="both", expand=True)
   canvas.on_ready = lambda: canvas.load_url("https://example.org/")
   root.after(0, lambda: session.start(canvas))
   root.mainloop()

.. toctree::
   :maxdepth: 2
   :caption: Guide

   guide/installation
   guide/quickstart
   guide/cookbook
   guide/concepts
   guide/message-loop
   guide/embedding
   guide/events
   guide/javascript-bridge
   guide/views
   guide/toolkits
   guide/context-menu
   guide/media
   guide/printing
   guide/cast
   guide/configuration
   guide/wayland-gpu
   guide/troubleshooting
   guide/limitations
   guide/development

.. toctree::
   :maxdepth: 2
   :caption: Reference

   api/core
   api/types
   api/ui
   api/toolkits
