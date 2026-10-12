"""Tables that translate a toolkit's keys, modifiers and cursors to CEF values.

A toolkit states its own names, and the tables apply the common rules: a table of special
keys, function keys as a range, the key of a character; modifiers as bits, names or event
queries; cursors with a default.
"""

from . import keys


def function_range(first):
    """Create a function key detector for ``KeyTable(function=...)``.

    Args:
        first (int): The toolkit's key code of F1; F12 is ``first + 11``.

    Returns:
        callable: A function that maps a key to its function key number (1 to 12), or ``None``.
    """
    def number(key):
        return key - first + 1 if isinstance(key, int) and first <= key < first + 12 else None
    return number


class KeyTable:
    """Map a toolkit's key to a virtual key code (``keys.VK_*``).

    Args:
        special (dict): ``{toolkit key: code}`` for keys that follow no rule (arrows, Enter,
            modifiers).
        function (callable, optional): ``function(key)`` returns the function key number 1 to
            12 for a function key, otherwise ``None``. See :func:`function_range`.
        char (callable, optional): ``char(key)`` returns the character the key produces, or a
            false value. The code is that of the character's key, see
            :func:`~cefweaver.ui.keys.vk_for_char`.
        others_as_code_point (bool, optional): If true, a character without a virtual key
            (e.g. Hangul) yields its code point instead of 0. Defaults to ``False``.

    Attributes:
        special (dict): The special key table.
        function (callable or None): The function key detector.
        char (callable or None): The character function.
        others_as_code_point (bool): See above.
    """

    def __init__(self, special, function=None, char=None, others_as_code_point=False):
        self.special = dict(special)
        self.function = function
        self.char = char
        self.others_as_code_point = others_as_code_point

    def code(self, key):
        """Return the virtual key code of a toolkit key.

        Args:
            key: The toolkit's key.

        Returns:
            int: The virtual key code, or 0 if the key has none.
        """
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
    """Base class that converts a toolkit's modifier state to CEF modifier flags.

    A subclass implements :meth:`has`.
    """

    _FLAGS = (("shift", keys.SHIFT), ("control", keys.CONTROL), ("alt", keys.ALT))
    _BUTTON_FLAGS = (("left", keys.LEFT_BUTTON), ("middle", keys.MIDDLE_BUTTON), ("right", keys.RIGHT_BUTTON))

    def has(self, state, name):
        """Return whether a modifier is down in a state.

        Args:
            state: The toolkit's modifier state.
            name (str): ``"shift"``, ``"control"``, ``"alt"``, ``"left"``, ``"middle"`` or
                ``"right"``.

        Returns:
            bool: ``True`` if the modifier or button is down.
        """
        raise NotImplementedError

    def flags(self, state, buttons=None):
        """Return the CEF modifier flags of a state.

        Args:
            state: The toolkit's modifier state.
            buttons (optional): A separate state for the mouse buttons, for toolkits that
                report them apart from the keys. Defaults to ``state``.

        Returns:
            int: The sum of the ``keys`` flags.
        """
        flags = 0
        for name, flag in self._FLAGS:
            if self.has(state, name):
                flags |= flag
        for name, flag in self._BUTTON_FLAGS:
            if self.has(state if buttons is None else buttons, name):
                flags |= flag
        return flags


class MaskModifiers(ModifierTable):
    """Modifiers that are bits of a number or of a flags enumeration.

    Example: ``MaskModifiers(shift=1, control=4)``.

    Args:
        shift: The mask of Shift, or ``None`` if the toolkit has none.
        control: The mask of Control.
        alt: The mask of Alt.
        left: The mask of the left mouse button.
        middle: The mask of the middle mouse button.
        right: The mask of the right mouse button.
    """

    def __init__(self, shift=None, control=None, alt=None, left=None, middle=None, right=None):
        self.masks = {"shift": shift, "control": control, "alt": alt, "left": left, "middle": middle, "right": right}

    def has(self, state, name):
        """Return whether the mask of a modifier is set in a state.

        Args:
            state (int): The toolkit's modifier state, a bit mask.
            name (str): ``"shift"``, ``"control"``, ``"alt"``, ``"left"``, ``"middle"`` or ``"right"``.

        Returns:
            bool: ``False`` if no mask was given for ``name``.
        """
        mask = self.masks.get(name)
        return mask is not None and bool(state & mask)


class NamedModifiers(ModifierTable):
    """Modifiers that are names in a collection, e.g. Kivy's ``["ctrl", "shift"]``.

    Attributes:
        NAMES (dict): The toolkit name of each modifier.
    """

    NAMES = {"shift": "shift", "control": "ctrl", "alt": "alt", "left": "left", "middle": "middle", "right": "right"}

    def has(self, state, name):
        """Return whether the toolkit name of a modifier is in a state.

        Args:
            state (collection): The toolkit's modifier names.
            name (str): ``"shift"``, ``"control"``, ``"alt"``, ``"left"``, ``"middle"`` or ``"right"``.

        Returns:
            bool: Whether ``NAMES[name]`` is in ``state``.
        """
        return self.NAMES[name] in state


class EventModifiers(ModifierTable):
    """Modifiers that an event object answers by methods, e.g. wx's ``event.ShiftDown()``.

    The state is the event. A missing method counts as not down.

    Attributes:
        QUESTIONS (dict): The method name for each modifier.
    """

    QUESTIONS = {"shift": "ShiftDown", "control": "ControlDown", "alt": "AltDown",
                 "left": "LeftIsDown", "middle": "MiddleIsDown", "right": "RightIsDown"}

    def has(self, state, name):
        """Return whether an event reports a modifier as down.

        Args:
            state: The toolkit's event object.
            name (str): ``"shift"``, ``"control"``, ``"alt"``, ``"left"``, ``"middle"`` or ``"right"``.

        Returns:
            bool: ``False`` if the event has no such question method.
        """
        question = getattr(state, self.QUESTIONS[name], None)
        return bool(question()) if question is not None else False


class CursorTable:
    """Map a ``types.CursorType`` to a toolkit's cursor.

    Args:
        cursors (dict): ``{CursorType: toolkit cursor}``.
        default: The cursor for types not in ``cursors``.

    Attributes:
        cursors (dict): The cursor table.
        default: The default cursor.
    """

    def __init__(self, cursors, default):
        self.cursors = dict(cursors)
        self.default = default

    def get(self, cursor):
        """Return the toolkit cursor for a cursor type.

        Args:
            cursor (CursorType): The CEF cursor type.

        Returns:
            The toolkit cursor, or the default if there is none for ``cursor``.
        """
        return self.cursors.get(cursor, self.default)
