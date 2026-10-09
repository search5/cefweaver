"""The context menu of a page (right click): CEF describes it, the toolkit shows it.

CEF gives a menu model (the standard items such as Back, Copy and Select all, with their command ids). A toolkit
adapter that has ``show_menu(items, x, y, done)`` shows it with the menu widget of the toolkit and calls
``done(command_id)`` for the item that the user picked, or ``done(None)`` if the menu was left. CEF runs the standard
commands itself. The application can change the menu: ``view.on_context_menu = hook``, where ``hook(info, items)``
returns the list of items to show (add ``MenuItem("My item", action=function)``, take items out) or None for no menu.
"""

import itertools
import re
import sys

from cefweaver import types

_KINDS = {types.MenuItemType.COMMAND: "command", types.MenuItemType.CHECK: "check", types.MenuItemType.RADIO: "radio",
          types.MenuItemType.SEPARATOR: "separator", types.MenuItemType.SUBMENU: "submenu"}
# the commands of the menu that the view does with the clipboard of the toolkit (the clipboard of CEF is another one)
CLIPBOARD_COMMANDS = {int(types.MenuId.CUT): "cut", int(types.MenuId.COPY): "copy", int(types.MenuId.PASTE): "paste",
                      int(types.MenuId.PASTE_MATCH_STYLE): "paste"}
# the edit commands that the view runs in the frame (CEF would run them as the page was when the menu opened, and after
# the menu of the toolkit took the focus they do nothing); the methods of the frame
FRAME_COMMANDS = {int(types.MenuId.UNDO): "undo", int(types.MenuId.REDO): "redo", int(types.MenuId.DELETE): "delete",
                  int(types.MenuId.SELECT_ALL): "select_all"}
# the spelling commands (suggestions of the checker and Add to dictionary): the view runs them through the browser host for
# the same reason, and CEF gives the word and the suggestions in the parameters of the menu
SPELLING_SUGGESTIONS = range(int(types.MenuId.SPELLCHECK_SUGGESTION_0), int(types.MenuId.SPELLCHECK_SUGGESTION_LAST) + 1)
ADD_TO_DICTIONARY = int(types.MenuId.ADD_TO_DICTIONARY)
APP_FIRST = 1_000_000                       # command ids of the items of the application (CEF's are far below)


class MenuItem:
    """One item of a menu. ``kind``: ``"command"``, ``"check"``, ``"radio"``, ``"separator"`` or ``"submenu"``.

    An item of the application has an ``action`` (called when it is picked, CEF is not told) and no ``command_id``;
    the view gives it one when the menu is shown.
    """

    def __init__(self, label="", action=None, command_id=None, kind="command", enabled=True, checked=False, children=None):
        self.label, self.action, self.command_id, self.kind = label, action, command_id, kind
        self.enabled, self.checked, self.children = enabled, checked, list(children or [])

    def __repr__(self):
        return "MenuItem(%r, %s, id=%s)" % (self.label, self.kind, self.command_id)


class ContextMenuInfo:
    """Where the page was clicked and on what (``view.on_context_menu`` gets it)."""

    def __init__(self, params):
        self.params = params
        self.x, self.y = params.get_x_coord(), params.get_y_coord()
        self.link_url = params.get_link_url()
        self.source_url = params.get_source_url()
        self.page_url = params.get_page_url()
        self.selection_text = params.get_selection_text()
        self.is_editable = params.is_editable()
        self.misspelled_word = params.get_misspelled_word()                      # "" if the word is spelled right
        found, suggestions = params.get_dictionary_suggestions()
        self.dictionary_suggestions = list(suggestions) if found else []


def _clean(label):
    """``&Back`` is Back (a mnemonic mark); ``&&`` is a real ampersand."""
    return re.sub(r"&(&)?", lambda m: "&" if m.group(1) else "", label)


def items_from_model(model):
    """The visible items of a CEF ``MenuModel`` (separators tidied: none first, last or twice in a row)."""
    items = []
    for index in range(model.get_count()):
        if not model.is_visible_at(index):
            continue
        kind = _KINDS.get(model.get_type_at(index))
        if kind is None:
            continue
        if kind == "separator":
            items.append(MenuItem(kind="separator", enabled=False))
            continue
        item = MenuItem(_clean(model.get_label_at(index)), command_id=model.get_command_id_at(index), kind=kind,
                        enabled=model.is_enabled_at(index), checked=model.is_checked_at(index))
        if kind == "submenu":
            item.children = items_from_model(model.get_sub_menu_at(index))
        items.append(item)
    return tidy(items)


def tidy(items):
    """Without a separator at the start or the end, or two in a row."""
    result = []
    for item in items:
        if item.kind == "separator" and (not result or result[-1].kind == "separator"):
            continue
        result.append(item)
    while result and result[-1].kind == "separator":
        result.pop()
    return result


def give_ids(items, numbers=None, actions=None):
    """Give the items of the application a command id; returns ``{command_id: action}``."""
    numbers = itertools.count(APP_FIRST) if numbers is None else numbers
    actions = {} if actions is None else actions
    for item in items:
        if item.action is not None:
            if item.command_id is None:
                item.command_id = next(numbers)
            actions[item.command_id] = item.action
        give_ids(item.children, numbers, actions)
    return actions


def report():
    """An error of the application or of the toolkit is reported like the error of any handler."""
    sys.excepthook(*sys.exc_info())
