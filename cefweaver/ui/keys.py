"""Key codes and modifier flags for the events a toolkit hands to ``BrowserView``.

The modifier flags are the CEF event flags: a toolkit translates its own modifiers (and mouse buttons held
down) into a sum of these. The key codes are the Windows virtual key codes that CEF wants; a toolkit gives
the code of the key (not the character it types), and ``vk_for_char`` and ``vk_for_function`` cover the
codes that follow a rule so that a toolkit needs a table only for its special keys (arrows and the like).
"""

import sys

from cefweaver.types import EventFlags

SHIFT = int(EventFlags.SHIFT_DOWN)
CONTROL = int(EventFlags.CONTROL_DOWN)
ALT = int(EventFlags.ALT_DOWN)
LEFT_BUTTON = int(EventFlags.LEFT_MOUSE_BUTTON)
MIDDLE_BUTTON = int(EventFlags.MIDDLE_MOUSE_BUTTON)
RIGHT_BUTTON = int(EventFlags.RIGHT_MOUSE_BUTTON)
COMMAND = int(EventFlags.COMMAND_DOWN)             # macOS: the Command key

VK_BACK, VK_TAB, VK_RETURN, VK_ESCAPE, VK_SPACE = 8, 9, 13, 27, 32
VK_SHIFT, VK_CONTROL, VK_ALT = 16, 17, 18
VK_CAPITAL = 20                                  # Caps Lock
VK_PRIOR, VK_NEXT, VK_END, VK_HOME = 33, 34, 35, 36
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 37, 38, 39, 40
VK_INSERT, VK_DELETE = 45, 46
VK_F1 = 112


# macOS: CEF turns a key event into a Cocoa one (checked on macOS 26, CEF 154).
#  * The editing keys are run by their native key code: a Windows key code alone types a letter
#    but does not edit (Backspace, Delete and the arrows are ignored). The codes are the Carbon
#    virtual key codes (kVK_*).
#  * A key up needs its character (MAC_KEY_CHARS for these keys; the character of the key down
#    for the others). Without one Cocoa takes the event for a key down: the page gets a second
#    keydown ("Unidentified", or the key again) and an editing key edits twice.
IS_MAC = sys.platform == "darwin"
MAC_NATIVE_CODES = {
    VK_BACK: 51, VK_TAB: 48, VK_RETURN: 36, VK_ESCAPE: 53, VK_SPACE: 49,
    VK_PRIOR: 116, VK_NEXT: 121, VK_END: 119, VK_HOME: 115,
    VK_LEFT: 123, VK_UP: 126, VK_RIGHT: 124, VK_DOWN: 125, VK_DELETE: 117,
}


# The character Cocoa gives these keys (NSDeleteCharacter, the NS...FunctionKey constants).
MAC_KEY_CHARS = {
    VK_BACK: 127, VK_TAB: 9, VK_RETURN: 13, VK_ESCAPE: 27, VK_SPACE: 32,
    VK_PRIOR: 0xF72C, VK_NEXT: 0xF72D, VK_END: 0xF72B, VK_HOME: 0xF729,
    VK_LEFT: 0xF702, VK_UP: 0xF700, VK_RIGHT: 0xF703, VK_DOWN: 0xF701, VK_DELETE: 0xF728,
}


def shortcut_modifier():
    """The modifier of the editing shortcuts (copy, paste, select all, undo): Command on macOS, else Control."""
    return COMMAND if IS_MAC else CONTROL


def native_code_for_key_down(windows_key_code, native_code):
    """The native key code to send with a key down: the toolkit's own when it gives one, else on
    macOS the code of an editing key, else 0."""
    if native_code or not IS_MAC:
        return native_code
    return MAC_NATIVE_CODES.get(windows_key_code, 0)


def vk_for_char(char):
    """The virtual key code of a printable ASCII character (the key without Shift), 0 for others."""
    if len(char) == 1 and 0x20 <= ord(char) < 0x7F:
        return ord(char.upper())
    return 0


def vk_for_function(number):
    """The code of F1 to F12."""
    if not 1 <= number <= 12:
        raise ValueError("F%d is not a function key from F1 to F12" % number)
    return VK_F1 + number - 1
