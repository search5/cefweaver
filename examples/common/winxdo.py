"""The part of ``xdotool`` that ``checks.py`` uses, for Windows: real input events from ``SendInput`` (so the message
handling of the toolkit and the input stack are on the way, as for a user). Only the commands the checks call:

    mousemove X Y              the pointer to a point of the screen (device pixels)
    click [--repeat N] [--delay MS] BUTTON      1 left, 2 middle, 3 right, 4 wheel up, 5 wheel down (the buttons of X)
    mousedown BUTTON, mouseup BUTTON
    key NAME[+NAME...]         ``ctrl+a``, ``BackSpace``, ``Escape``, ``Tab``, ``F5``, ``alt+Left`` ...
    type [--delay MS] TEXT     the keys of the characters (a character the keyboard layout has no key for: a Unicode event)
    windowfocus HWND           bring the window to the front

The checks need the window in front and the pointer and keys to themselves: do not touch the machine while they run.
"""

import ctypes
import time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP = 0x0020, 0x0040
MOUSEEVENTF_WHEEL = 0x0800
KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_UNICODE = 0x1, 0x2, 0x4
MAPVK_VK_TO_VSC = 0

_BUTTONS = {
    "1": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP), "2": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
    "3": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
}
_MODIFIERS = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "super": 0x5B}
_NAMES = {
    "backspace": 0x08, "tab": 0x09, "return": 0x0D, "enter": 0x0D, "escape": 0x1B, "space": 0x20, "prior": 0x21,
    "page_up": 0x21, "next": 0x22, "page_down": 0x22, "end": 0x23, "home": 0x24, "left": 0x25, "up": 0x26,
    "right": 0x27, "down": 0x28, "insert": 0x2D, "delete": 0x2E,
}
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E}


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.c_size_t)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT


def _send(*inputs):
    array = (INPUT * len(inputs))(*inputs)
    if user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT)) != len(inputs):
        raise OSError("SendInput failed (is another program, run as administrator, in front?) %s" % ctypes.get_last_error())


def _mouse(flags, data=0):
    return INPUT(INPUT_MOUSE, mi=MOUSEINPUT(0, 0, data, flags, 0, 0))


def _key(vk, up=False, scan=None, unicode=False):
    flags = (KEYEVENTF_KEYUP if up else 0)
    if unicode:
        return INPUT(INPUT_KEYBOARD, ki=KEYBDINPUT(0, scan, flags | KEYEVENTF_UNICODE, 0, 0))
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC) if scan is None else scan
    if vk in _EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    return INPUT(INPUT_KEYBOARD, ki=KEYBDINPUT(vk, scan, flags, 0, 0))


def _vk_of(name):
    lowered = name.lower()
    if lowered in _NAMES:
        return _NAMES[lowered]
    if lowered in _MODIFIERS:
        return _MODIFIERS[lowered]
    if len(lowered) >= 2 and lowered[0] == "f" and lowered[1:].isdigit():
        return 0x6F + int(lowered[1:])                      # F1 is 0x70
    if len(name) == 1:
        found = user32.VkKeyScanW(ord(name)) & 0xFF
        if found != 0xFF:
            return found
    raise ValueError("no key named %r" % name)


def press(combination):
    """``ctrl+shift+a``: modifiers down, the key down and up, modifiers up."""
    parts = combination.split("+")
    codes = [_vk_of(part) for part in parts]
    inputs = [_key(code) for code in codes] + [_key(code, up=True) for code in reversed(codes)]
    _send(*inputs)


def type_text(text, delay=0.0):
    for character in text:
        code = user32.VkKeyScanW(ord(character))
        vk, shift = code & 0xFF, (code >> 8) & 0xFF
        if vk == 0xFF or shift & ~0x1:                       # no key (or one that needs more than Shift): a Unicode event
            _send(_key(0, scan=ord(character), unicode=True), _key(0, up=True, scan=ord(character), unicode=True))
        else:
            events = ([_key(0x10)] if shift else []) + [_key(vk), _key(vk, up=True)] + ([_key(0x10, up=True)] if shift else [])
            _send(*events)
        time.sleep(delay)


def run(*args):
    """The command as ``xdotool`` takes it (words, numbers as they come)."""
    words = [str(a) for a in args]
    command, rest = words[0], words[1:]
    if command == "mousemove":
        user32.SetCursorPos(int(rest[0]), int(rest[1]))
    elif command in ("mousedown", "mouseup"):
        down, up = _BUTTONS[rest[0]]
        _send(_mouse(down if command == "mousedown" else up))
    elif command == "click":
        repeat, delay = 1, 0.0
        while rest[0].startswith("--"):
            option = rest.pop(0)
            value = rest.pop(0)
            if option == "--repeat":
                repeat = int(value)
            elif option == "--delay":
                delay = int(value) / 1000
        button = rest[0]
        for _ in range(repeat):
            if button in _BUTTONS:
                down, up = _BUTTONS[button]
                _send(_mouse(down), _mouse(up))
            elif button in ("4", "5"):
                _send(_mouse(MOUSEEVENTF_WHEEL, 120 if button == "4" else (-120) & 0xFFFFFFFF))
            else:
                raise ValueError("no button " + button)
            time.sleep(delay)
    elif command == "key":
        for combination in rest:
            press(combination)
    elif command == "type":
        delay = 0.0
        if rest[0] == "--delay":
            delay = int(rest[1]) / 1000
            rest = rest[2:]
        type_text(" ".join(rest), delay)
    elif command == "windowfocus":
        focus(int(rest[0]))
    else:
        raise RuntimeError("winxdo has no command %r" % command)


def focus(hwnd):
    """Bring a window to the front. Windows lets only the foreground process do that; a tap on Alt gives the right."""
    _send(_key(0x12), _key(0x12, up=True))
    user32.ShowWindow(hwnd, 9)                              # SW_RESTORE
    user32.SetForegroundWindow(hwnd)
