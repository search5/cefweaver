"""A cefweaver browser as a child NSView of a Cocoa window (macOS).

The browser is a native view that fills the content view of the window and follows its size;
CEF draws it (GPU, native input and IME). The same works for the NSView a SwiftUI
NSViewRepresentable makes, or any other NSView: give its address to ``CefApp.parent_view``.

    uv run python quickstart.py [URL] [--seconds N]      # --seconds closes the window by itself
"""

import sys
import tempfile

import objc
from AppKit import (NSApplication, NSApplicationActivationPolicyRegular, NSBackingStoreBuffered,
                    NSMakeRect, NSObject, NSWindow, NSWindowStyleMaskClosable,
                    NSWindowStyleMaskMiniaturizable, NSWindowStyleMaskResizable,
                    NSWindowStyleMaskTitled)
from Foundation import NSTimer

import cefweaver

args = [a for a in sys.argv[1:] if not a.startswith("--")]
URL = args[0] if args and not args[0].isdigit() else "https://example.org/"
SECONDS = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 0


class Delegate(NSObject):
    """Closes the browser and CEF with the window, then ends the application."""

    def initWithApp_(self, app):
        self = objc.super(Delegate, self).init()
        self.app = app
        self.closing = False
        return self

    def windowShouldClose_(self, window):
        # The first request (the close button) starts the shutdown, outside of this call, and the
        # window stays; closing the browser makes CEF ask to close the window once more, which is
        # let through.
        if self.closing:
            return True
        self.closing = True
        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(0.0, False, self.finishTimer_)
        return False

    def finishTimer_(self, timer):
        self.app.shutdown()                     # closes the browser (its view leaves the window) and CEF
        NSApplication.sharedApplication().terminate_(None)


def main():
    nsapp = NSApplication.sharedApplication()
    nsapp.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    style = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
             | NSWindowStyleMaskMiniaturizable | NSWindowStyleMaskResizable)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(200, 200, 900, 640), style, NSBackingStoreBuffered, False)
    window.setTitle_("cefweaver in a Cocoa window")

    app = cefweaver.CefApp()
    app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-cocoa-"))
    pump = cefweaver.MessagePump(app)           # CEF asks when it needs the loop
    app.parent_view = objc.pyobjc_id(window.contentView())     # the NSView the browser fills

    delegate = Delegate.alloc().initWithApp_(app)
    window.setDelegate_(delegate)
    window.makeKeyAndOrderFront_(None)
    nsapp.activateIgnoringOtherApps_(True)

    app.initialize(URL)                         # the browser is made inside, as a child view
    # The Cocoa loop runs the application; a timer gives CEF its turns.
    def tick(_timer):                           # a timer block must return None
        if app.is_running:
            pump.run()

    timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(0.005, True, tick)
    if SECONDS:
        def close_window(_timer):
            window.performClose_(None)          # as the close button does
        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(SECONDS, False, close_window)
    nsapp.run()
    return timer


if __name__ == "__main__":
    main()
