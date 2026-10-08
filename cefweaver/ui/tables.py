"""Tables that turn what a toolkit calls a key, a modifier or a cursor into what CEF wants.

Every toolkit has its own names for these, but the rules that use them are the same: a table of special keys,
the function keys as a range, the key of a character; the modifiers as bits (or names, or questions to the
event); the cursors with a default. A toolkit states its names and the tables apply the rules.
"""

from . import keys


def function_range(first):
    """For ``KeyTable(function=...)``: a toolkit whose F1 to F12 are the key codes ``first`` to ``first + 11``."""
    def number(key):
        return key - first + 1 if isinstance(key, int) and first <= key < first + 12 else None
    return number


class KeyTable:
    """The virtual key code (``keys.VK_*``) of a toolkit's key.

    ``special``: {toolkit key: code} for the keys that follow no rule (arrows, Enter, modifiers).
    ``function(key)``: the number 1 to 12 if the key is a function key, else None (see ``function_range``).
    ``char(key)``: the character the key makes, if it makes one; its capital's ASCII code is the key code.
    ``others_as_code_point``: a character with no virtual key (Hangul) gives its code point, not 0.
    """

    def __init__(self, special, function=None, char=None, others_as_code_point=False):
        self.special = dict(special)
        self.function = function
        self.char = char
        self.others_as_code_point = others_as_code_point

    def code(self, key):
        code = self.special.get(key)
        if code is not None:
            return code
        if self.function is not None:
            number = self.function(key)
            if number and 1 <= number <= 12:
                return keys.vk_for_function(number)
            if number:
                return 0
        if self.char is not None:
            character = self.char(key)
            if character:
                return keys.vk_for_char(character) or (ord(character) if self.others_as_code_point else 0)
        return 0


class ModifierTable:
    """The CEF modifier flags (``keys.SHIFT`` and so on) of a toolkit's state of the keyboard and the buttons.

    A subclass tells how the toolkit says that a modifier is down: ``has(state, name)`` with ``name`` one of
    ``"shift"``, ``"control"``, ``"alt"``, ``"left"``, ``"middle"``, ``"right"``. ``buttons`` is a second
    state for toolkits that give the mouse buttons apart from the keys.
    """

    _FLAGS = (("shift", keys.SHIFT), ("control", keys.CONTROL), ("alt", keys.ALT))
    _BUTTON_FLAGS = (("left", keys.LEFT_BUTTON), ("middle", keys.MIDDLE_BUTTON), ("right", keys.RIGHT_BUTTON))

    def has(self, state, name):
        raise NotImplementedError

    def flags(self, state, buttons=None):
        flags = 0
        for name, flag in self._FLAGS:
            if self.has(state, name):
                flags |= flag
        for name, flag in self._BUTTON_FLAGS:
            if self.has(state if buttons is None else buttons, name):
                flags |= flag
        return flags


class MaskModifiers(ModifierTable):
    """Modifiers that are bits of a number (or of a flags enumeration): ``MaskModifiers(shift=1, control=4)``."""

    def __init__(self, shift=None, control=None, alt=None, left=None, middle=None, right=None):
        self.masks = {"shift": shift, "control": control, "alt": alt, "left": left, "middle": middle, "right": right}

    def has(self, state, name):
        mask = self.masks.get(name)
        return mask is not None and bool(state & mask)


class NamedModifiers(ModifierTable):
    """Modifiers that are names in a collection (Kivy: ``["ctrl", "shift"]``)."""

    NAMES = {"shift": "shift", "control": "ctrl", "alt": "alt", "left": "left", "middle": "middle", "right": "right"}

    def has(self, state, name):
        return self.NAMES[name] in state


class EventModifiers(ModifierTable):
    """Modifiers that an event answers (wx: ``event.ShiftDown()``, ``event.LeftIsDown()``)."""

    QUESTIONS = {"shift": "ShiftDown", "control": "ControlDown", "alt": "AltDown",
                 "left": "LeftIsDown", "middle": "MiddleIsDown", "right": "RightIsDown"}

    def has(self, state, name):
        question = getattr(state, self.QUESTIONS[name], None)
        return bool(question()) if question is not None else False


class CursorTable:
    """The cursor of a toolkit for a ``types.CursorType``, with a default for those it has none for."""

    def __init__(self, cursors, default):
        self.cursors = dict(cursors)
        self.default = default

    def get(self, cursor):
        return self.cursors.get(cursor, self.default)
