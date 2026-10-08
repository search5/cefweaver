"""Key codes and modifier flags for the events a toolkit hands to ``BrowserView``.

The modifier flags are the CEF event flags: a toolkit translates its own modifiers (and mouse buttons held
down) into a sum of these. The key codes are the Windows virtual key codes that CEF wants; a toolkit gives
the code of the key (not the character it types), and ``vk_for_char`` and ``vk_for_function`` cover the
codes that follow a rule so that a toolkit needs a table only for its special keys (arrows and the like).
"""

from cefweaver.types import EventFlags

SHIFT = int(EventFlags.SHIFT_DOWN)
CONTROL = int(EventFlags.CONTROL_DOWN)
ALT = int(EventFlags.ALT_DOWN)
LEFT_BUTTON = int(EventFlags.LEFT_MOUSE_BUTTON)
MIDDLE_BUTTON = int(EventFlags.MIDDLE_MOUSE_BUTTON)
RIGHT_BUTTON = int(EventFlags.RIGHT_MOUSE_BUTTON)

VK_BACK, VK_TAB, VK_RETURN, VK_ESCAPE, VK_SPACE = 8, 9, 13, 27, 32
VK_SHIFT, VK_CONTROL, VK_ALT = 16, 17, 18
VK_PRIOR, VK_NEXT, VK_END, VK_HOME = 33, 34, 35, 36
VK_LEFT, VK_UP, VK_RIGHT, VK_DOWN = 37, 38, 39, 40
VK_INSERT, VK_DELETE = 45, 46
VK_F1 = 112


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
