Limitations and known constraints
=================================

What does not work yet, and the known constraints. Each item says whether the cause was confirmed.

Platforms
---------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Item
     - Status
   * - Linux x86_64
     - The platform where development and tests happen.
   * - Windows 11 x86_64
     - Built and tested. There are the differences in "Windows" below.
   * - macOS arm64
     - Built and tested. There are the differences in "macOS" below.
   * - macOS x86_64
     - Built and started under Rosetta. Not a real Intel Mac.
   * - Window mode with Wayland
     - Cannot be closed from code and dies on exit. Confirmed as a limit of CEF (:doc:`wayland-gpu`).
   * - X11 with GPU
     - Video does not appear on some machines. The cause was not found (same page).

Windows
-------

The scope verified on Windows 11, Python 3.13 and CEF 154. Offscreen (including the adapters of :mod:`cefweaver.ui`), JavaScript bindings, shutdown and freezing (PyInstaller, cx_Freeze, py2exe) work. Of the tests, the ones that make sense on Linux only (X11, ``/proc``, CUPS) are skipped and the rest pass.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Item
     - Status
   * - Window mode (``parent_view`` and the window CEF creates)
     - In the tests of this repository the paths where CEF creates the window (including a Views window) open and close. **Attaching to the window of another program (``SetAsChild``) was not built** (``parent_view`` is macOS only).
   * - Character input (``CHAR`` event)
     - Windows wants the character code in ``windows_key_code`` of a ``CHAR`` event (not a virtual key code). ``BrowserView`` fills it. If you send with ``send_key_event`` yourself, fill it yourself.
   * - Shared textures
     - Not verified. ``read_plane()`` is for dmabuf only, so it raises ``NotImplementedError`` on Windows.
   * - Printing
     - ``PrintHandler`` is for Linux only. On Windows ``host.print()`` opens the system print dialog.
   * - Spelling suggestions
     - A misspelled word did not arrive in the context menu and no suggestion was obtained (cause not confirmed).
   * - Auto resize
     - A size (944x504) larger than the maximum of ``set_auto_resize_enabled`` (900x700) was reported (cause not confirmed).
   * - Build
     - The sandbox library of CEF is not linked (``no_sandbox``). The static runtime (``/MT``) is linked.
   * - Python
     - Verified on 3.13 only.

macOS
-----

The scope verified on Apple Silicon. Offscreen and native windows, ``NSView`` in a Cocoa window (``parent_view``), JavaScript bindings, shutdown, Tk widgets, the headless adapter, menus and editing keys work.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Item
     - Status
   * - Editing keys (Backspace, arrows, Delete)
     - When you send through the host API (``send_key_event``) yourself, you must give the mac virtual key code (``native_key_code``), and KEYUP needs ``character`` (the Cocoa character). Otherwise editing keys are ignored or edit twice. ``BrowserView.key()`` of :mod:`cefweaver.ui` fills them.
   * - Command combinations
     - Offscreen, Command+A/Z/Shift+Z go through ``Frame`` commands and Command+C/X/V through the clipboard of the toolkit (CEF has no Edit menu, so keys alone do not work). A native view (``parent_view``) is handled by CEF.
   * - Request for a new tab
     - Ctrl+click becomes a right click. Use Command+click.
   * - Shared textures
     - None. The planes of ``on_accelerated_paint`` are empty.
   * - Printing
     - ``host.print()`` opens **the system print panel of macOS** (modal) instead of the ``PrintHandler`` of CEF, in offscreen and window mode alike. To print without a dialog, make a PDF with ``print_to_pdf()`` and send it with ``NSPrintOperation`` or ``lp``. Printing for real from the panel was not tried.
   * - Spelling suggestions
     - No suggestions arrived. macOS checks with ``NSSpellChecker`` (cause not investigated).
   * - Context menu
     - The default menu had no back and forward.
   * - Toolkits
     - Tk, Qt, wx and SDL2 were started with the example and checked up to the page, the round trip with the demo page and closing (mouse, keys and drag and drop checks run on Linux only). Kivy shows a page on Python 3.13, but the watchdog of Chromium kills the process at shutdown (Python 3.14 is not supported by Kivy). GTK 3 is not on the system and was not checked. The ``print`` example is for Linux (CUPS) only, and on macOS ``Print...`` does not respond. For Cocoa or SwiftUI use ``parent_view`` (:doc:`quickstart`).
   * - ``parent_view``
     - Verified with a Cocoa window made with PyObjC, ``NSViewRepresentable`` of Swift, Qt (``winId()``) and wx (``GetHandle()``). The ``winfo_id()`` of Tk is not an ``NSView`` and crashes (the content view of a window works and fills the whole window).
   * - Several browsers in one window
     - Each attaches to its own view and follows its size. If only one of them is closed, ``on_before_close`` comes only at ``shutdown()``.
   * - Shutdown watchdog
     - With native arm64 Python ``shutdown()`` finishes within 0.1 seconds. Under Rosetta (x86_64) and with Python embedded in a Swift executable ``CefShutdown()`` never finishes, and the watchdog of Chromium killed the process with exit code 2 after 10 seconds (cause not confirmed).
   * - macOS x86_64
     - Built and started under Rosetta (including the shutdown problem above). Not a real Intel Mac.
   * - Window title
     - Not verified.
   * - Signing
     - The CEF framework and the helper app are signed ad hoc. To distribute, you must sign and notarize yourself.

Features
--------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Item
     - Status
   * - Printing
     - **On Linux the application handles it.** CEF has no print dialog and no printer list, so fill the settings in ``PrintHandler`` (``on_print_settings``), show a dialog of your own (``on_print_dialog``) and send the PDF you get to CUPS. ``disable-features=EnableOopPrintDrivers`` is needed. The full example is ``examples/print/``. It is not in the adapters of :mod:`cefweaver.ui`, so the menu item ``Print`` does nothing. On macOS ``print()`` did not finish.
   * - Right-click menu in SDL2 and Kivy
     - None. Neither toolkit has a native menu widget (checked in the official documentation). ``view.on_context_menu`` is not called in these toolkits either.
   * - Switching Korean and English in Tk
     - Does not work. The cause was not found.
   * - Supplying sound and video from the application
     - None. Chromium takes the microphone and the camera from the system devices.
   * - One browser per session
     - ``ui.Session`` handles one browser.
   * - CEF initialization
     - Once per process. Not again even after ``shutdown()``.

Media
-----

- **Codecs**: VP9, AV1 and Opus play, and **H.264 (``avc1``) and AAC (``mp4a``) do not.** The standard CEF build does not include proprietary codecs. YouTube serves VP9 and Opus, so it plays. A site that serves only H.264 will probably not play (this was not checked directly). If you need proprietary codecs, build CEF yourself (``python tools/prepare.py --build-cef --proprietary-codecs``).
- **Microphone**: if it is muted in the system, the device opens but no sound arrives (:doc:`media`).

API
---

- **``bridge.evaluate``**: an expression sent before the context of the page exists, and one whose page was left before it answered, ends with ``TimeoutError`` after ``timeout`` (30 seconds by default); it does not wait when you send it after a signal such as ``ready()``. An expression runs inside a block, so a ``"use strict"`` directive has no effect, and a ``Symbol`` or ``BigInt`` result arrives as ``TypeError``.
- **``DragData.get_file_name()``**: call it only for a drag that has file contents. Calling it without them kills the process: CEF calls a function of Chromium without checking, and a ``CHECK`` inside fails (confirmed as a limit of CEF).
- **Views**: **mouse and key input of the CEF window do not arrive with a ``MessagePump`` (an external message pump)**, so use a polling loop that calls ``do_message_loop_work()`` often. Verified on Linux X11 only (:doc:`views`).
- **``Image``**: you can create it only after CEF is initialized (``Image.create_image()`` raises ``RuntimeError``). Creating it before initialization kills the process when the object goes away; this was confirmed.
- **Not yet opened**: ``on_certificate_error`` does not pass ``ssl_info`` (read the certificate with ``get_visible_navigation_entry().get_ssl_status()``). ``OnBeforeDevToolsPopup``, ``ResourceBundleHandler`` and ``TaskRunner`` do not exist yet either. Running Python in the renderer is not possible by design; you receive only notices through :doc:`renderer events <events>`.
- **Cache folder**: without a cache path CEF creates ``cache/`` in the working directory.

Scope of the tests
------------------

- The macOS tests were all run including window mode (194 tests of ``test_smoke.py`` in about 3 minutes; windows open). Once, one test failed temporarily during a full run, and the cause was not found.
- The smoke of the toolkits runs on a virtual X server with real X events. Korean typing through a real input method (ibus, fcitx) was tried with GTK 3 only.
- A toolkit used natively on Wayland (the Wayland backend of GTK or Qt) was not tested. In the tests the toolkit window was X11 and CEF was Wayland.
- The desktop environment was GNOME (mutter) only, and the GPU configuration was one machine.
