Context menu
============

An offscreen browser does not get a menu drawn by CEF. So :mod:`cefweaver.ui` reads the menu model of CEF and shows it with the **menu widget of the toolkit**. This works in toolkits whose adapter has ``show_menu``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Toolkit
     - Menu
   * - GTK 3
     - ``Gtk.Menu``
   * - Qt
     - ``QMenu``
   * - Tk
     - ``tkinter.Menu``
   * - wxPython
     - ``wx.Menu``
   * - SDL2, Kivy
     - none (see :doc:`toolkits`)

Who runs an item
----------------

Most items are standard commands defined by CEF (back, forward, copy, paste, spelling suggestions, ...). Which items appear depends on where you clicked: whether text is selected, an input field, a link or a misspelled word. The labels follow the locale (``뒤로(B)`` in Korean).

The one that runs the chosen item depends on the item, because while the menu is open the menu of the toolkit takes the keyboard focus, and some commands do nothing when CEF is told afterwards.

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Item
     - Run by
   * - Copy, cut, paste, paste as plain text
     - The view, through **the clipboard of the toolkit** (the same path as Ctrl+C and so on). On Wayland the clipboard of CEF belongs to the compositor and does not reach the toolkit.
   * - Undo, redo, delete, select all
     - The view, directly through the edit API of the clicked frame.
   * - Spelling suggestions, add to dictionary
     - The view, with ``BrowserHost.replace_misspelling()`` and ``add_word_to_dictionary()``.
   * - Other standard commands (back, forward, reload, ...)
     - CEF, handed over with ``continue_``.
   * - Items the application added
     - The function the application gave (``action``).

Changing the menu from the application
--------------------------------------

Hang a hook on ``view.on_context_menu`` to remove or add items.

.. code-block:: python

   from cefweaver import ui

   def hook(info, items):
       # remove the spelling items and add one of the application
       spelling = set(ui.menu.SPELLING_SUGGESTIONS) | {ui.menu.ADD_TO_DICTIONARY}
       items = [item for item in items if item.command_id not in spelling]
       items.append(ui.menu.MenuItem("Show page address", action=lambda: print(info.page_url)))
       return items                                  # returning None shows no menu

   widget.view.on_context_menu = hook                # give it before the session starts

- ``info`` describes where you clicked: ``x`` and ``y`` (view coordinates), ``link_url``, ``source_url``, ``page_url``, ``selection_text``, ``is_editable``, ``misspelled_word``, ``dictionary_suggestions`` and the original ``params`` of CEF.
- ``items`` is a list of ``ui.menu.MenuItem``. An item has ``kind`` (``command``, ``check``, ``radio``, ``separator`` or ``submenu``), ``label``, ``enabled``, ``checked``, ``children`` and ``command_id``. Separators at the start, at the end and in a row are cleaned up in the list the hook returns.
- ``MenuItem("label", action=function)`` is an item of the application. When chosen only the function runs and CEF is not told.
- If the hook or the ``show_menu`` of the adapter raises, the menu is cancelled and the error goes to ``sys.excepthook``.

Adding a menu to a new toolkit
------------------------------

Implement ``show_menu(items, x, y, done)`` in the adapter. ``items`` is the list of ``MenuItem`` above and ``(x, y)`` are view coordinates. When the user picks an item call ``done(command_id of the item)``; when the menu just closes call ``done(None)``. Call it **exactly once**.

Some traps appeared only on a real desktop:

- CEF asks for the menu at the moment the right button is **pressed**. In some toolkits (wx) a menu that appears with the button still down is closed by the release that follows. Wait until the button goes up before opening it. In GTK 3 show the menu from the real button event the widget got.
- While the menu is open the widget can lose focus and CEF can be told "no focus". The view takes this into account when it runs commands, as in the table above, so the adapter has nothing to do.

Known limits
------------

- The menu item ``Print`` is shown, but printing does not work (see :doc:`limitations`).
- A misspelled English word gets suggestions and an ``Add to dictionary`` item. Filter them with the hook above if you do not want them.
