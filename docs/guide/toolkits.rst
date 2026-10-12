Toolkit status
==============

Seven toolkits have an adapter (pywin32 on Windows only). What follows was verified on 2026-10-09; pywin32 was verified on Windows 11 on 2026-10-11.

There are two ways of verifying.

- **Smoke**: the example application runs on a virtual X server (Xvfb) and real X events (``xdotool``) drive mouse, keys, drag and drop, the clipboard and the context menu; the result is read back. This is the ``smoke.py`` of each example, and the number in parentheses is the number of checks.
- **Real screen**: the developer used it on a real desktop. The window of the toolkit was X11 then and only CEF was Wayland. A toolkit used natively on Wayland was not tested.

At a glance
-----------

.. list-table::
   :header-rows: 1
   :widths: 18 14 16 28 24

   * - Toolkit
     - Sound
     - Right-click menu
     - Smoke
     - Real screen
   * - GTK 3
     - pygame
     - ``Gtk.Menu``
     - passes (39)
     - verified
   * - Qt
     - ``QtSink``
     - ``QMenu``
     - PyQt6 and PySide6 pass (35 each)
     - both bindings verified
   * - Tk
     - pygame
     - ``tkinter.Menu``
     - passes (30)
     - verified (except switching between Korean and English)
   * - SDL2
     - ``SdlSink``
     - none
     - passes (28)
     - sound verified
   * - wxPython
     - pygame
     - ``wx.Menu``
     - passes (33)
     - verified
   * - Kivy
     - pygame
     - none
     - passes (27)
     - sound verified
   * - pywin32 (Windows)
     - pygame
     - ``TrackPopupMenu``
     - passes (27)
     - verified at 100% scaling; a real Korean input method and sound were not verified

"Sound" is how the sound of a page is played: the playback API of the toolkit when it has one, otherwise pygame (see :doc:`media`). A YouTube video was played and heard in six toolkits (Qt with both bindings); pywin32 was not tried.

Notes per toolkit
-----------------

GTK 3 (:mod:`cefweaver.ui.toolkits.gtk3`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``GlibLoop``, ``GtkAdapter`` and ``CefWidget``. Korean input through the input method, copy and paste and drag and drop were verified on a real screen; scale 2 (HiDPI) was verified by smoke. CEF asks for the menu at the moment the right button is pressed, so the widget shows the menu from the real button event it received.

Qt (:mod:`cefweaver.ui.toolkits.qt`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``QtLoop``, ``QtAdapter``, ``CefWidget`` and ``QtSink``. PyQt6 is the default; choose PySide6 with the environment variable ``CEFQT_BINDING=pyside6``. Scale 2 was verified by smoke. Korean was not typed through a real input method (the smoke imitates the committed characters of an input method through the adapter).

Tk (:mod:`cefweaver.ui.toolkits.tk`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``TkLoop``, ``TkAdapter`` and ``CefCanvas``. Pictures are converted and drawn with Pillow. **Switching between Korean and English does not work** (Tk does not give the characters being composed by the input method; the cause was not found). GTK 3 is the toolkit where real input-method typing was verified.

SDL2 (:mod:`cefweaver.ui.toolkits.sdl2`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One ``SdlBrowser`` holds the window, the browser and the event loop. There is no right-click menu: SDL2 has no function to build a menu (only message boxes such as ``SDL_ShowMessageBox``) and only flags that name a window kind (``SDL_WINDOW_POPUP_MENU`` and so on). In this toolkit ``view.on_context_menu`` is not called either. If you need a menu, implement ``show_menu`` in the adapter yourself (see :doc:`context-menu`).

wxPython (:mod:`cefweaver.ui.toolkits.wx`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``WxLoop``, ``WxAdapter`` and ``CefPanel``. A wx menu runs an event loop of its own until it closes, so the menu is opened after the answer from CEF is complete and after the right button went up. Korean was not typed through a real input method.

Kivy (:mod:`cefweaver.ui.toolkits.kivy`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``KivyLoop``, ``KivyAdapter`` and ``CefView``. There is no right-click menu: Kivy has no native context menu widget, and ``DropDown`` opens attached to a widget, which does not fit a click position. For the same reason ``view.on_context_menu`` is not called in this toolkit either.

pywin32 (:mod:`cefweaver.ui.toolkits.pywin32`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One ``Win32Browser`` holds the window, the browser and the message loop (Windows only, ``cefweaver[pywin32]``). pywin32 handles windows and messages, and pictures are drawn with GDI ``StretchDIBits`` (a few calls that pywin32 lacks use ``ctypes``). The right-click menu is ``TrackPopupMenu``. Files dropped from the Explorer arrive as ``WM_DROPFILES``; text drops and drags out of the page are not supported. The 27 checks of ``smoke.py`` send real mouse and keyboard input with ``SendInput``; they do not use a real Korean input method (the smoke imitates the committed characters through ``view``). The scale was verified at 100% only. The same checks passed when frozen with PyInstaller (onedir, onefile), cx_Freeze and py2exe (py2exe needs the CEF runtime files copied next to the executable by hand).
