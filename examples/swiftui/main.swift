// A cefweaver browser in a SwiftUI view (macOS).
//
// The app is Swift; it embeds Python (libpython) and gives the NSView that SwiftUI makes to
// CefApp.parent_view. CEF draws the browser in that view. Swift runs the Cocoa loop and a Timer
// gives CEF its turns (cefweaver.MessagePump).
//
//     ./build.sh && ./CefSwiftUI [URL] [--seconds N]

import AppKit
import SwiftUI

let args = Array(CommandLine.arguments.dropFirst())
let startURL = args.first(where: { !$0.hasPrefix("--") && Double($0) == nil }) ?? "https://example.org/"
let autoClose: Double = {
    if let i = args.firstIndex(of: "--seconds"), i + 1 < args.count { return Double(args[i + 1]) ?? 0 }
    return 0
}()

/// Runs Python source in __main__. Everything on the main thread: CEF's UI thread is the one
/// that called initialize().
///
/// The GIL is held only for the call. Between calls the main thread sits in the Cocoa run loop,
/// and while it kept the GIL the threads of CEF could not run their Python callbacks (they wait
/// for it and the main thread waits for them: the browser never closed).
func python(_ source: String) {
    let state = PyGILState_Ensure()
    defer { PyGILState_Release(state) }
    if PyRun_SimpleString(source) != 0 {
        fputs("python failed:\n\(source)\n", stderr)
    }
}

func pythonBool(_ expression: String) -> Bool {
    let state = PyGILState_Ensure()
    defer { PyGILState_Release(state) }
    guard let main = PyImport_AddModule("__main__"), let globals = PyModule_GetDict(main),
          let result = PyRun_String(expression, Py_eval_input, globals, globals) else {
        PyErr_Print()
        return false
    }
    defer { Py_DecRef(result) }
    return PyObject_IsTrue(result) == 1
}

let pythonSetup = """
import sys, os, tempfile
sys.path.insert(0, os.environ["CEFSWIFT_SITE"])
import cefweaver

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-swiftui-"))
pump = cefweaver.MessagePump(app)
titles = []

class Display(cefweaver.DisplayHandler):
    def on_title_change(self, browser, title):
        titles.append(title)
        print("title:", title, flush=True)

opened = []

class Life(cefweaver.LifeSpanHandler):
    def on_after_created(self, browser):
        opened.append(browser)
    def on_before_close(self, browser):
        opened[:] = [b for b in opened if b.get_identifier() != browser.get_identifier()]

class Client(cefweaver.Client):
    def __init__(self):
        self.display = Display()
        self.life = Life()
    def get_display_handler(self):
        return self.display
    def get_life_span_handler(self):
        return self.life
app.set_client(Client())

def start(view_address, url):
    app.parent_view = view_address
    app.initialize(url)
    pass

def tick():
    if app.is_running:
        pump.run()

def begin_close():
    for browser in list(opened):
        browser.get_host().close_browser(True)

def stop():
    app.shutdown()
"""

/// The NSView CEF fills. SwiftUI owns it; its address is all Python needs.
struct CefView: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let view = NSView(frame: NSRect(x: 0, y: 0, width: 800, height: 500))
        view.autoresizingMask = [.width, .height]
        // The view has to be in a window before CEF makes a child of it.
        DispatchQueue.main.async {
            let address = UInt(bitPattern: Unmanaged.passUnretained(view).toOpaque())
            python("start(\(address), '\(startURL)')")
        }
        return view
    }
    func updateNSView(_ nsView: NSView, context: Context) {}
}

struct ContentView: View {
    var body: some View {
        VStack(spacing: 0) {
            Text("SwiftUI toolbar")
                .frame(maxWidth: .infinity, minHeight: 28)
                .background(Color.gray.opacity(0.25))
            CefView()
        }
        .frame(minWidth: 640, minHeight: 400)
    }
}

final class AppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    var window: NSWindow!
    var timer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // The window is made here and holds the SwiftUI view (NSHostingView): a WindowGroup of a
        // bare executable (not an app bundle) did not always open its window.
        window = NSWindow(contentRect: NSRect(x: 200, y: 200, width: 900, height: 640),
                          styleMask: [.titled, .closable, .miniaturizable, .resizable],
                          backing: .buffered, defer: false)
        window.title = "cefweaver in SwiftUI"
        window.contentView = NSHostingView(rootView: ContentView())
        window.delegate = self
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        timer = Timer.scheduledTimer(withTimeInterval: 0.005, repeats: true) { _ in python("tick()") }
        if autoClose > 0 {
            Timer.scheduledTimer(withTimeInterval: autoClose, repeats: false) { [weak self] _ in
                self?.window.performClose(nil)      // as the close button does
            }
        }
    }

    /// The close button: close the browser, and when it is gone end the run loop. CEF is shut down
    /// after the loop, as CEF's cefsimple does, not inside a callback of the loop.
    var closing = false
    func windowShouldClose(_ sender: NSWindow) -> Bool {
        if closing { return true }
        closing = true
        python("begin_close()")
        Timer.scheduledTimer(withTimeInterval: 0.01, repeats: true) { [weak self] t in
            guard pythonBool("len(opened) == 0") else { return }
            t.invalidate()
            self?.timer?.invalidate()
            NSApp.stop(nil)
            // stop() ends the loop after the next event: send one.
            let event = NSEvent.otherEvent(with: .applicationDefined, location: .zero, modifierFlags: [],
                                           timestamp: 0, windowNumber: 0, context: nil, subtype: 0,
                                           data1: 0, data2: 0)!
            NSApp.postEvent(event, atStart: true)
        }
        return false
    }

}

Py_Initialize()
python(pythonSetup)
_ = PyEval_SaveThread()                 // let go of the GIL: python() takes it for each call
let application = NSApplication.shared
application.setActivationPolicy(.regular)
let delegate = AppDelegate()
application.delegate = delegate
application.run()

// The run loop has ended and no browser is left. CefShutdown() should take a moment; in a Swift
// executable that embeds Python it did not return here (it does in the python executable, see
// docs/limitations.md), and Chromium's watchdog ended the process with an error after 10 s. So the
// process leaves after 3 s if CEF is not down by then. The browser is closed by then; only the
// final flush of CEF's cache is cut short.
DispatchQueue.global().asyncAfter(deadline: .now() + 3) { exit(0) }
python("stop()")
_ = PyGILState_Ensure()
Py_Finalize()
