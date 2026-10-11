"""A Win32 window that shows a cefweaver offscreen browser (pywin32), built on ``cefweaver.ui``.

The Win32 API gives windows, messages and GDI but no widgets, so ``Win32Browser`` is the toolkit side as a whole, like
``SdlBrowser``: the adapter (size, place, drawing the frames, cursor, clipboard, context menu, candidate window) and
the message loop. ``step(timeout_ms)`` waits for a message, dispatches what there is, runs what ``post`` and
``call_later`` were given and returns.

* The window procedure is a table of pywin32 (``WNDCLASS.lpfnWndProc`` as a dict); a message not in it goes to
  ``DefWindowProc``.
* CEF asks to run from any of its threads: ``post`` appends to a queue and sends ``WM_APP`` (``PostMessage`` is thread
  safe). ``call_later`` is one ``SetTimer`` for the earliest deadline. Both are handled in the window procedure, so CEF
  keeps running while Windows runs a loop of its own (dragging the window by its title bar, a popup menu).
* The picture is drawn with GDI ``StretchDIBits`` (pywin32 has no call for it, so ``ctypes`` does that one) from a
  buffer that keeps the last frame; the part of a frame that changed is copied into it.
* The keys are the Windows key codes CEF wants, so a table is not needed. Typed characters arrive as ``WM_CHAR``; what an
  input method composes arrives as ``WM_IME_COMPOSITION`` (the preedit is drawn by the page, the candidate window
  by the IME). Files dropped from the Explorer arrive as ``WM_DROPFILES``; text cannot be dropped (that would need OLE).
* The process is made per-monitor DPI aware before the window exists, and ``scale()`` is the DPI of the window / 96.

Checked: Windows 11 (100 % scale), CPython 3.13, pywin32 312: the 27 checks of examples/pywin32/smoke.py (real input from SendInput), also frozen
with PyInstaller, cx_Freeze and py2exe.
Not checked: a scale other than 1, a real input method (the checks call the same ``view`` methods the IME messages
call), more than one monitor, dropping files from the Explorer (the checks post ``WM_DROPFILES`` themselves).
"""

import collections
import ctypes
import heapq
import itertools
import sys
import time
from ctypes import wintypes

import pywintypes
import win32api
import win32clipboard
import win32con
import win32event
import win32gui

from cefweaver import types, ui
from cefweaver.ui import keys

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_imm32 = ctypes.WinDLL("imm32", use_last_error=True)

# <winuser.h> and <imm.h> values that win32con does not have (or has under another name)
WM_MOUSELEAVE = 0x02A3
WM_MOUSEHWHEEL = 0x020E
WM_DPICHANGED = 0x02E0
WM_IME_STARTCOMPOSITION, WM_IME_ENDCOMPOSITION, WM_IME_COMPOSITION = 0x010D, 0x010E, 0x010F
GCS_COMPSTR, GCS_CURSORPOS, GCS_RESULTSTR = 0x0008, 0x0080, 0x0800
CFS_POINT, CFS_CANDIDATEPOS = 0x0002, 0x0040
TME_LEAVE = 0x00000002
MK_LBUTTON, MK_RBUTTON, MK_SHIFT, MK_CONTROL, MK_MBUTTON = 0x1, 0x2, 0x4, 0x8, 0x10
SIZE_MINIMIZED = 1
TIMER_ID = 1
BI_RGB, DIB_RGB_COLORS, SRCCOPY = 0, 0, 0x00CC0020

_CURSOR_IDS = {
    "POINTER": win32con.IDC_ARROW, "HAND": win32con.IDC_HAND, "IBEAM": win32con.IDC_IBEAM, "CROSS": win32con.IDC_CROSS,
    "WAIT": win32con.IDC_WAIT, "PROGRESS": win32con.IDC_APPSTARTING, "HELP": win32con.IDC_HELP,
    "MOVE": win32con.IDC_SIZEALL, "NOTALLOWED": win32con.IDC_NO, "NODROP": win32con.IDC_NO, "DND_NONE": win32con.IDC_NO,
    "COLUMNRESIZE": win32con.IDC_SIZEWE, "ROWRESIZE": win32con.IDC_SIZENS,
    "EASTRESIZE": win32con.IDC_SIZEWE, "WESTRESIZE": win32con.IDC_SIZEWE, "EASTWESTRESIZE": win32con.IDC_SIZEWE,
    "NORTHRESIZE": win32con.IDC_SIZENS, "SOUTHRESIZE": win32con.IDC_SIZENS, "NORTHSOUTHRESIZE": win32con.IDC_SIZENS,
    "NORTHEASTRESIZE": win32con.IDC_SIZENESW, "SOUTHWESTRESIZE": win32con.IDC_SIZENESW,
    "NORTHEASTSOUTHWESTRESIZE": win32con.IDC_SIZENESW,
    "NORTHWESTRESIZE": win32con.IDC_SIZENWSE, "SOUTHEASTRESIZE": win32con.IDC_SIZENWSE,
    "NORTHWESTSOUTHEASTRESIZE": win32con.IDC_SIZENWSE,
}
_CURSORS = {getattr(types.CursorType, name): cursor for name, cursor in _CURSOR_IDS.items()}
_CURSOR_SHAPES = ui.CursorTable(_CURSORS, default=win32con.IDC_ARROW)


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class _TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("hwndTrack", wintypes.HWND),
                ("dwHoverTime", wintypes.DWORD)]


class _COMPOSITIONFORM(ctypes.Structure):
    _fields_ = [("dwStyle", wintypes.DWORD), ("ptCurrentPos", wintypes.POINT), ("rcArea", wintypes.RECT)]


class _CANDIDATEFORM(ctypes.Structure):
    _fields_ = [("dwIndex", wintypes.DWORD), ("dwStyle", wintypes.DWORD), ("ptCurrentPos", wintypes.POINT),
                ("rcArea", wintypes.RECT)]


_gdi32.StretchDIBits.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p,
                                 wintypes.UINT, wintypes.DWORD]
_gdi32.StretchDIBits.restype = ctypes.c_int
_user32.TrackMouseEvent.argtypes = [ctypes.POINTER(_TRACKMOUSEEVENT)]
_imm32.ImmGetContext.argtypes = [wintypes.HWND]
_imm32.ImmGetContext.restype = wintypes.HANDLE
_imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
_imm32.ImmGetCompositionStringW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
_imm32.ImmGetCompositionStringW.restype = wintypes.LONG
_imm32.ImmSetCompositionWindow.argtypes = [wintypes.HANDLE, ctypes.POINTER(_COMPOSITIONFORM)]
_imm32.ImmSetCandidateWindow.argtypes = [wintypes.HANDLE, ctypes.POINTER(_CANDIDATEFORM)]


_user32.AdjustWindowRectEx.argtypes = [ctypes.POINTER(wintypes.RECT), wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_user32.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p]
_user32.SetTimer.restype = ctypes.c_size_t
_user32.KillTimer.argtypes = [wintypes.HWND, ctypes.c_size_t]
_user32.GetDpiForWindow.argtypes = [wintypes.HWND]
_user32.GetDpiForWindow.restype = wintypes.UINT
_shell32 = ctypes.WinDLL("shell32", use_last_error=True)
_shell32.DragQueryPoint.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.POINT)]


# (pywin32 has no AdjustWindowRectEx, SetTimer, KillTimer and DragQueryPoint: ctypes does those)
def _window_rect_for_client(width, height, style):
    rect = wintypes.RECT(0, 0, width, height)
    _user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, 0)
    return rect.right - rect.left, rect.bottom - rect.top


def _set_timer(hwnd, milliseconds):
    _user32.SetTimer(hwnd, TIMER_ID, milliseconds, None)


def _kill_timer(hwnd):
    _user32.KillTimer(hwnd, TIMER_ID)


def _signed(value):
    """A signed 16 bit number (the x and y of ``lParam`` are)."""
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def modifier_flags(state=0):
    """CEF event flags of the ``MK_*`` bits of a mouse message and of the keys that are down now."""
    flags = 0
    if state & MK_SHIFT or win32api.GetKeyState(win32con.VK_SHIFT) < 0:
        flags |= keys.SHIFT
    if state & MK_CONTROL or win32api.GetKeyState(win32con.VK_CONTROL) < 0:
        flags |= keys.CONTROL
    if win32api.GetKeyState(win32con.VK_MENU) < 0:
        flags |= keys.ALT
    if state & MK_LBUTTON:
        flags |= keys.LEFT_BUTTON
    if state & MK_MBUTTON:
        flags |= keys.MIDDLE_BUTTON
    if state & MK_RBUTTON:
        flags |= keys.RIGHT_BUTTON
    return flags


def _buttons_down():
    """The ``MK_*`` bits of the mouse buttons that are down (a keyboard message does not tell)."""
    state = 0
    for virtual_key, bit in ((win32con.VK_LBUTTON, MK_LBUTTON), (win32con.VK_RBUTTON, MK_RBUTTON),
                             (win32con.VK_MBUTTON, MK_MBUTTON)):
        if win32api.GetAsyncKeyState(virtual_key) & 0x8000:
            state |= bit
    return state


class _Timer:
    def __init__(self, function):
        self.function = function

    def cancel(self):
        self.function = None


class Win32Browser(ui.BrowserWidget):
    """The window, the browser and the message loop. It is the ``ui.ToolkitAdapter`` of its own ``BrowserView``."""

    capabilities = frozenset()      # no drag source and no clipboard CEF could use: the view does both
    _classes = itertools.count()

    def __init__(self, switches=(), cache_path=None, width=900, height=640, title="cefweaver pywin32", audio=None):
        if sys.platform != "win32":
            raise RuntimeError("cefweaver.ui.toolkits.pywin32 runs on Windows only")
        try:                                                    # per-monitor v2: the window gets the real DPI
            _user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            pass
        self.title, self.url = title, ""
        self.can_back = self.can_forward = False
        self.scale_factor = 1.0
        self.picture = (0, 0)                                   # size of the picture of the view, in device pixels
        self.popup_size = (0, 0)
        self._bits = self._popup_bits = None                    # the last frames (bytearray, BGRA)
        self._cursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        self._posted = collections.deque()
        self._timers = []
        self._sequence = itertools.count()
        self._tracking = False
        self._high_surrogate = 0
        self._composing = False
        self.quit = False
        self._closing = False
        self._destroyed = False
        # the window
        instance = win32api.GetModuleHandle(None)
        window_class = win32gui.WNDCLASS()
        window_class.hInstance = instance
        window_class.lpszClassName = "CefweaverWin32Browser%d" % next(self._classes)
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = 0                          # WM_ERASEBKGND is answered, the picture covers all
        window_class.lpfnWndProc = self._procedures()
        atom = win32gui.RegisterClass(window_class)
        style = win32con.WS_OVERLAPPEDWINDOW
        outer_width, outer_height = _window_rect_for_client(width, height, style)
        self.hwnd = win32gui.CreateWindow(atom, title, style, win32con.CW_USEDEFAULT, win32con.CW_USEDEFAULT,
                                          outer_width, outer_height, 0, 0, instance, None)
        self._class_name = window_class.lpszClassName
        self._instance = instance
        win32gui.DragAcceptFiles(self.hwnd, True)
        self.scale_factor = self._dpi() / 96.0
        self.width, self.height = width, height                 # logical pixels, replaced by _update_size()
        self._update_size()
        self.screen = self._screen_size()
        # CEF
        self.attach_view(self, audio=audio)
        self.on_ready = lambda: None                            # set by the application: the browser exists, load a page
        self.session = ui.Session(self, switches, cache_path)
        self.app, self.bridge = self.session.app, self.session.bridge
        win32gui.ShowWindow(self.hwnd, win32con.SW_SHOW)
        win32gui.UpdateWindow(self.hwnd)

    # -- the toolkit side of ui.ToolkitAdapter ---------------------------------------------------------

    def post(self, function):                                   # any thread of CEF
        self._posted.append(function)
        try:
            win32gui.PostMessage(self.hwnd, win32con.WM_APP, 0, 0)
        except pywintypes.error:                                # the window is gone
            pass

    def call_later(self, seconds, function):
        timer = _Timer(function)
        heapq.heappush(self._timers, (time.monotonic() + seconds, next(self._sequence), timer))
        self._arm_timer()
        return timer

    def view_size(self):
        return self.width, self.height

    def scale(self):
        return self.scale_factor

    def screen_origin(self):
        x, y = win32gui.ClientToScreen(self.hwnd, (0, 0))
        return x, y

    def screen_size(self):
        return self.screen

    def present(self, frame):
        if frame.kind == ui.Frame.POPUP_HIDDEN:
            self._popup_bits = None
            self._invalidate()
            return
        width, height = frame.width, frame.height
        data = frame.buffer                                     # valid during this call only
        if frame.kind == ui.Frame.POPUP:
            self._popup_bits = bytearray(data)
            self.popup_size = (width, height)
            self._invalidate()
            return
        pitch = width * 4
        if self._bits is None or self.picture != (width, height):
            self._bits = bytearray(data)
            self.picture = (width, height)
        else:
            for rect in frame.dirty_rects:                      # only what changed
                x0, y0 = max(0, rect.x), max(0, rect.y)
                x1, y1 = min(width, rect.x + rect.width), min(height, rect.y + rect.height)
                if x1 > x0:
                    for row in range(y0, y1):
                        start = row * pitch + x0 * 4
                        self._bits[start:row * pitch + x1 * 4] = data[start:row * pitch + x1 * 4]
        self._invalidate()

    def set_cursor(self, cursor):
        self._cursor = win32gui.LoadCursor(0, _CURSOR_SHAPES.get(cursor))
        if self._pointer_in_client():
            win32gui.SetCursor(self._cursor)

    def set_ime_rect(self, x, y, width, height):                # where the candidate window goes
        context = _imm32.ImmGetContext(self.hwnd)
        if not context:
            return
        try:
            scale = self.scale_factor
            point = wintypes.POINT(int(x * scale), int((y + height) * scale))
            composition = _COMPOSITIONFORM(CFS_POINT, point, wintypes.RECT())
            candidate = _CANDIDATEFORM(0, CFS_CANDIDATEPOS, point, wintypes.RECT())
            _imm32.ImmSetCompositionWindow(context, ctypes.byref(composition))
            _imm32.ImmSetCandidateWindow(context, ctypes.byref(candidate))
        finally:
            _imm32.ImmReleaseContext(self.hwnd, context)

    def clipboard_get(self):
        for _ in range(10):                                     # another program may hold the clipboard for a moment
            try:
                win32clipboard.OpenClipboard(self.hwnd)
                break
            except pywintypes.error:
                time.sleep(0.01)
        else:
            return None
        try:
            if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
            return None
        finally:
            win32clipboard.CloseClipboard()

    def clipboard_set(self, text):
        for _ in range(10):
            try:
                win32clipboard.OpenClipboard(self.hwnd)
                break
            except pywintypes.error:
                time.sleep(0.01)
        else:
            raise OSError("the clipboard is held by another program")
        try:
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            win32clipboard.CloseClipboard()

    def show_menu(self, items, x, y, done):
        """The context menu of the page as a popup menu at (x, y) of the view. ``done`` gets the command id of the
        picked item, or None. ``TrackPopupMenu`` runs Windows' own loop until the menu is left; ``post`` and
        ``call_later`` go on in it (the window procedure handles them)."""
        ids = {}

        def fill(menu, entries):
            for entry in entries:
                flags = win32con.MF_STRING | (win32con.MF_ENABLED if entry.enabled else win32con.MF_GRAYED)
                if entry.kind == "separator":
                    win32gui.AppendMenu(menu, win32con.MF_SEPARATOR, 0, None)
                elif entry.kind == "submenu":
                    sub = win32gui.CreatePopupMenu()
                    fill(sub, entry.children)
                    win32gui.AppendMenu(menu, flags | win32con.MF_POPUP, sub, entry.label)
                else:
                    ids[len(ids) + 1] = entry.command_id        # 0 would mean "nothing picked"
                    if entry.kind in ("check", "radio") and entry.checked:
                        flags |= win32con.MF_CHECKED
                    win32gui.AppendMenu(menu, flags, len(ids), entry.label)

        menu = win32gui.CreatePopupMenu()
        try:
            fill(menu, items)
            self.last_menu_ids = ids                            # (for tests)
            px, py = win32gui.ClientToScreen(self.hwnd, (int(x * self.scale_factor), int(y * self.scale_factor)))
            win32gui.SetForegroundWindow(self.hwnd)             # else the menu does not close when it is clicked away
            picked = win32gui.TrackPopupMenu(menu, win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY, px, py, 0,
                                             self.hwnd, None)
            win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
        finally:
            win32gui.DestroyMenu(menu)
        done(ids.get(picked))

    # -- the application ---------------------------------------------------------------------------------

    @property
    def started(self):
        return self.session.started

    def browser_title(self, title):
        self.title = title or "cefweaver pywin32"
        win32gui.SetWindowText(self.hwnd, self.title)

    def browser_address(self, url):
        self.url = url

    def browser_loading(self, loading, can_back, can_forward):
        self.can_back, self.can_forward = can_back, can_forward

    def browser_ready(self):
        self.on_ready()

    def start(self, url):
        self.session.start(self.view, url)

    def close(self):
        """Close the browser and shut CEF down; ``step()`` goes on until that is done."""
        if not self._closing:
            self._closing = True
            self.session.shutdown()

    # -- the loop ------------------------------------------------------------------------------------

    def step(self, timeout_ms=None):
        """One turn: wait for a message (at most ``timeout_ms``), dispatch all there are. What ``post`` and
        ``call_later`` were given runs in the window procedure."""
        wait = 50 if timeout_ms is None else max(0, int(timeout_ms))
        if not self._posted:
            win32event.MsgWaitForMultipleObjects([], False, wait, win32con.QS_ALLINPUT)
        while True:
            found, message = win32gui.PeekMessage(0, 0, 0, win32con.PM_REMOVE)
            if not found:
                break
            if message[1] == win32con.WM_QUIT:
                self.quit = True
                break
            win32gui.TranslateMessage(message)
            win32gui.DispatchMessage(message)
        self._run_posted()
        self._run_timers()

    def run(self):
        while not self.quit and not (self._closing and not self.started):
            self.step()
        self.destroy()

    def destroy(self):
        if self._destroyed:
            return
        self._destroyed = True
        _kill_timer(self.hwnd)
        win32gui.DestroyWindow(self.hwnd)
        try:
            win32gui.UnregisterClass(self._class_name, self._instance)
        except pywintypes.error:
            pass

    # -- timers and posted functions -----------------------------------------------------------------

    def _run_posted(self):
        while self._posted:
            self._posted.popleft()()

    def _run_timers(self):
        now = time.monotonic()
        while self._timers and self._timers[0][0] <= now:
            timer = heapq.heappop(self._timers)[2]
            if timer.function is not None:
                timer.function()
        self._arm_timer()

    def _arm_timer(self):
        """One Windows timer for the earliest deadline (it also fires in loops of Windows' own)."""
        while self._timers and self._timers[0][2].function is None:
            heapq.heappop(self._timers)
        if self._destroyed:
            return
        if not self._timers:
            _kill_timer(self.hwnd)
            return
        _set_timer(self.hwnd, max(1, int((self._timers[0][0] - time.monotonic()) * 1000)))

    # -- geometry --------------------------------------------------------------------------------------

    def _dpi(self):
        try:
            return _user32.GetDpiForWindow(self.hwnd) or 96
        except (AttributeError, OSError):
            return 96

    def _screen_size(self):
        return win32api.GetSystemMetrics(win32con.SM_CXSCREEN), win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

    def _update_size(self):
        left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
        self.client = (right - left, bottom - top)               # device pixels
        self.scale_factor = self._dpi() / 96.0
        self.width = max(1, round(self.client[0] / self.scale_factor))
        self.height = max(1, round(self.client[1] / self.scale_factor))

    def _pointer_in_client(self):
        x, y = win32gui.ScreenToClient(self.hwnd, win32gui.GetCursorPos())
        return 0 <= x < self.client[0] and 0 <= y < self.client[1]

    def _logical(self, lparam):
        scale = self.scale_factor
        return int(_signed(lparam) / scale), int(_signed(lparam >> 16) / scale)

    def _invalidate(self):
        if not self._destroyed:
            win32gui.InvalidateRect(self.hwnd, None, False)

    # -- the window procedure ---------------------------------------------------------------------------

    def _procedures(self):
        table = {
            win32con.WM_APP: self._on_wake, win32con.WM_TIMER: self._on_timer,
            win32con.WM_SIZE: self._on_size, win32con.WM_PAINT: self._on_paint,
            win32con.WM_ERASEBKGND: lambda hwnd, msg, wparam, lparam: 1,
            win32con.WM_CLOSE: self._on_close, win32con.WM_SETFOCUS: self._on_focus,
            win32con.WM_KILLFOCUS: self._on_focus, win32con.WM_SETCURSOR: self._on_set_cursor,
            win32con.WM_MOUSEMOVE: self._on_mouse_move, WM_MOUSELEAVE: self._on_mouse_leave,
            win32con.WM_MOUSEWHEEL: self._on_wheel, WM_MOUSEHWHEEL: self._on_wheel,
            win32con.WM_KEYDOWN: self._on_key, win32con.WM_KEYUP: self._on_key,
            win32con.WM_SYSKEYDOWN: self._on_key, win32con.WM_SYSKEYUP: self._on_key,
            win32con.WM_CHAR: self._on_char, win32con.WM_SYSCHAR: self._on_syschar,
            win32con.WM_DROPFILES: self._on_drop_files,
            win32con.WM_CAPTURECHANGED: self._on_capture_lost, WM_DPICHANGED: self._on_dpi_changed,
            WM_IME_STARTCOMPOSITION: self._on_ime_start, WM_IME_COMPOSITION: self._on_ime_composition,
            WM_IME_ENDCOMPOSITION: self._on_ime_end,
        }
        for button, (down, up) in {"left": (win32con.WM_LBUTTONDOWN, win32con.WM_LBUTTONUP),
                                   "middle": (win32con.WM_MBUTTONDOWN, win32con.WM_MBUTTONUP),
                                   "right": (win32con.WM_RBUTTONDOWN, win32con.WM_RBUTTONUP)}.items():
            table[down] = lambda hwnd, msg, wparam, lparam, button=button: self._on_button(button, True, wparam, lparam)
            table[up] = lambda hwnd, msg, wparam, lparam, button=button: self._on_button(button, False, wparam, lparam)
        return table

    def _on_wake(self, hwnd, msg, wparam, lparam):
        self._run_posted()
        return 0

    def _on_timer(self, hwnd, msg, wparam, lparam):
        if wparam == TIMER_ID:
            _kill_timer(hwnd)
            self._run_timers()
        return 0

    def _on_size(self, hwnd, msg, wparam, lparam):
        if self.view is None:
            return 0
        if wparam == SIZE_MINIMIZED:
            self.view.shown(False)
            return 0
        self._update_size()
        self.view.shown(True)
        self.view.resized()
        self._invalidate()
        return 0

    def _on_dpi_changed(self, hwnd, msg, wparam, lparam):
        rect = wintypes.RECT.from_address(lparam)               # the size Windows suggests for the new DPI
        win32gui.SetWindowPos(hwnd, 0, rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top,
                              win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE)
        self._update_size()
        if self.view is not None:
            self.view.resized()
        return 0

    def _on_close(self, hwnd, msg, wparam, lparam):
        self.close()
        return 0

    def _on_focus(self, hwnd, msg, wparam, lparam):
        if self.view is not None:
            self.view.focus(msg == win32con.WM_SETFOCUS)
        return 0

    def _on_set_cursor(self, hwnd, msg, wparam, lparam):
        if (lparam & 0xFFFF) == win32con.HTCLIENT:
            win32gui.SetCursor(self._cursor)
            return 1
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def _on_paint(self, hwnd, msg, wparam, lparam):
        hdc, paint = win32gui.BeginPaint(hwnd)
        try:
            self._draw(hdc)
        finally:
            win32gui.EndPaint(hwnd, paint)
        return 0

    def _draw(self, hdc):
        client_width, client_height = self.client
        bits = self._bits
        width, height = self.picture
        if bits is not None:
            self._blit(hdc, bits, width, height, 0, 0)
        white = win32gui.GetStockObject(win32con.WHITE_BRUSH)
        if width < client_width:                                # the window grew and CEF has not painted yet
            win32gui.FillRect(hdc, (width, 0, client_width, client_height), white)
        if height < client_height:
            win32gui.FillRect(hdc, (0, height, client_width, client_height), white)
        rect = self.view.popup_rect if self.view is not None else None
        if self._popup_bits is not None and self.view.popup_visible and rect is not None:
            self._blit(hdc, self._popup_bits, self.popup_size[0], self.popup_size[1],
                       int(rect.x * self.scale_factor), int(rect.y * self.scale_factor))

    @staticmethod
    def _blit(hdc, bits, width, height, x, y):
        header = _BITMAPINFOHEADER(ctypes.sizeof(_BITMAPINFOHEADER), width, -height, 1, 32, BI_RGB, 0, 0, 0, 0, 0)
        buffer = (ctypes.c_char * len(bits)).from_buffer(bits)
        _gdi32.StretchDIBits(hdc, x, y, width, height, 0, 0, width, height, buffer, ctypes.byref(header),
                             DIB_RGB_COLORS, SRCCOPY)

    # -- the mouse -------------------------------------------------------------------------------------

    def _on_mouse_move(self, hwnd, msg, wparam, lparam):
        if not self._tracking:                                  # tell me when the pointer leaves the window
            _user32.TrackMouseEvent(ctypes.byref(_TRACKMOUSEEVENT(ctypes.sizeof(_TRACKMOUSEEVENT), TME_LEAVE, hwnd, 0)))
            self._tracking = True
        x, y = self._logical(lparam)
        self.view.mouse_move(x, y, modifier_flags(wparam))
        return 0

    def _on_mouse_leave(self, hwnd, msg, wparam, lparam):
        self._tracking = False
        self.view.mouse_move(0, 0, 0, leave=True)
        return 0

    def _on_button(self, button, pressed, wparam, lparam):
        x, y = self._logical(lparam)
        if pressed:
            win32gui.SetFocus(self.hwnd)
            win32gui.SetCapture(self.hwnd)                      # moves and the release come even outside the window
        self.view.mouse_button(x, y, button, pressed, modifier_flags(wparam))
        if not pressed and not wparam & (MK_LBUTTON | MK_RBUTTON | MK_MBUTTON):
            win32gui.ReleaseCapture()
        return 0

    def _on_capture_lost(self, hwnd, msg, wparam, lparam):
        return 0

    def _on_wheel(self, hwnd, msg, wparam, lparam):
        delta = _signed(wparam >> 16)                           # 120 for a notch, as CEF has it
        x, y = win32gui.ScreenToClient(hwnd, (_signed(lparam), _signed(lparam >> 16)))   # (wheel messages give screen coordinates)
        x, y = int(x / self.scale_factor), int(y / self.scale_factor)
        mods = modifier_flags(wparam & 0xFFFF)
        if msg == WM_MOUSEHWHEEL:
            self.view.wheel(x, y, delta, 0, mods)
        else:
            self.view.wheel(x, y, 0, delta, mods)
        return 0

    def _on_drop_files(self, hwnd, msg, wparam, lparam):
        try:
            files = [win32api.DragQueryFile(wparam, index) for index in range(win32api.DragQueryFile(wparam, -1))]
            point = wintypes.POINT()
            _shell32.DragQueryPoint(wparam, ctypes.byref(point))
            x, y = point.x, point.y
        finally:
            win32api.DragFinish(wparam)
        self.view.drop(int(x / self.scale_factor), int(y / self.scale_factor), files=files)
        return 0

    # -- the keyboard ----------------------------------------------------------------------------------

    def _on_key(self, hwnd, msg, wparam, lparam):
        down = msg in (win32con.WM_KEYDOWN, win32con.WM_SYSKEYDOWN)
        system = msg in (win32con.WM_SYSKEYDOWN, win32con.WM_SYSKEYUP)
        mods = modifier_flags(_buttons_down())
        if down and system and wparam == win32con.VK_F4:
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)           # Alt+F4 closes the window
        if down and system and mods & keys.ALT and wparam in (win32con.VK_LEFT, win32con.VK_RIGHT):
            (self.go_back if wparam == win32con.VK_LEFT else self.go_forward)()
            return 0
        if down and wparam == win32con.VK_F5:
            self.reload()
            return 0
        if wparam == win32con.VK_PROCESSKEY:                    # an input method has the key (WM_IME_COMPOSITION follows)
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        native = ctypes.c_int32(lparam & 0xFFFFFFFF).value      # the native key code of Windows is lParam (bit 31: key up)
        self.view.key(down, wparam, native, mods)
        if system and wparam == win32con.VK_SPACE:
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)           # Alt+Space: the system menu of the window
        return 0                                                # (not Alt alone or F10: DefWindowProc would start the menu mode, a loop that waits for keys)

    def _on_syschar(self, hwnd, msg, wparam, lparam):
        """Alt and a character: no menu here to take it as a mnemonic (DefWindowProc would only beep)."""
        if wparam == win32con.VK_SPACE:
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        return 0

    def _on_char(self, hwnd, msg, wparam, lparam):
        """Typed characters. Control codes belong to their keys (the view sends those with the key down)."""
        code = wparam
        if 0xD800 <= code < 0xDC00:                             # the first half of a surrogate pair
            self._high_surrogate = code
            return 0
        if 0xDC00 <= code < 0xE000 and self._high_surrogate:
            code = 0x10000 + ((self._high_surrogate - 0xD800) << 10) + (code - 0xDC00)
        self._high_surrogate = 0
        if code < 0x20 or code == 0x7F:
            return 0
        self.view.text(chr(code))
        return 0

    # -- the input method ------------------------------------------------------------------------------

    def _on_ime_start(self, hwnd, msg, wparam, lparam):
        self._composing = True
        return 0

    def _on_ime_end(self, hwnd, msg, wparam, lparam):
        self._composing = False
        self.view.preedit("", 0)
        return 0

    def _on_ime_composition(self, hwnd, msg, wparam, lparam):
        context = _imm32.ImmGetContext(hwnd)
        if not context:
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
        try:
            if lparam & GCS_RESULTSTR:
                result = self._ime_string(context, GCS_RESULTSTR)
                self.view.preedit("", 0)
                self.view.commit_text(result)                   # the text is the application's: no WM_CHAR follows
            if lparam & GCS_COMPSTR:
                text = self._ime_string(context, GCS_COMPSTR)
                cursor = _imm32.ImmGetCompositionStringW(context, GCS_CURSORPOS, None, 0) & 0xFFFF
                self.view.preedit(text, cursor if text else 0)
        finally:
            _imm32.ImmReleaseContext(hwnd, context)
        return 0

    @staticmethod
    def _ime_string(context, kind):
        size = _imm32.ImmGetCompositionStringW(context, kind, None, 0)       # bytes
        if size <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(size // 2 + 1)
        _imm32.ImmGetCompositionStringW(context, kind, buffer, size)
        return buffer.value[:size // 2]

    def handle_drop(self, text=None, files=None):
        """A drop from another program at the pointer (``WM_DROPFILES`` brings files itself)."""
        x, y = win32gui.ScreenToClient(self.hwnd, win32gui.GetCursorPos())
        self.view.drop(int(x / self.scale_factor), int(y / self.scale_factor), text=text, files=files)
