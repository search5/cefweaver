"""Checks the print example on macOS (what smoke.py does on Linux, without X and xdotool). Nothing is sent to a printer.

    uv run python smoke_mac.py              # printing_mac.py: the PDF, NSPrintOperation, lp, the system print panel
    uv run python smoke_mac.py --window     # quickstart_mac.py: the window with its buttons

CEF starts once per process, so the two parts are two runs. The system print panel (host.print()) is a modal window
that a person closes; the checks close it from outside (NSApp.abortModal()). Its Print button cannot be pressed by a
program (the panel is drawn by a service), so a real job through the panel is not checked here.
"""

import base64
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import printing_mac  # noqa: E402

PAGE = ("<html><head><title>Quarterly report</title></head><body style='font-family:sans-serif;margin:30px'>"
        "<h1>Quarterly report</h1><p>First page.</p>"
        "<div style='page-break-before:always'><h2>Page two</h2></div></body></html>")
URL = "data:text/html;base64," + base64.b64encode(PAGE.encode()).decode()
failed = []


def check(ok, what, detail=None):
    print(("ok    " if ok else "FAIL  ") + what + ("" if ok or detail is None else "   [%r]" % (detail,)), flush=True)
    if not ok:
        failed.append(what)


def finish():
    print("ALL OK" if not failed else "FAILED: " + ", ".join(failed))
    sys.exit(1 if failed else 0)


def close_panel_from_outside(delay):
    """A person closes the print panel; here a timer of the main run loop does (NSApp.abortModal()). The timer is in
    the common modes: the panel is modal, and a timer of the default mode only does not run while it is open."""
    from AppKit import NSApp
    from Foundation import NSObject, NSRunLoop, NSRunLoopCommonModes, NSTimer

    class Closer(NSObject):
        def abort_(self, _):
            self.had_panel = NSApp.modalWindow() is not None
            NSApp.abortModal()

    closer = Closer.alloc().init()
    closer.had_panel = None
    timer = NSTimer.timerWithTimeInterval_repeats_block_(delay, False, lambda _t: closer.abort_(None))
    NSRunLoop.mainRunLoop().addTimer_forMode_(timer, NSRunLoopCommonModes)
    return closer


# -- part 1: printing_mac.py -----------------------------------------------------------------------------------------

def functions():
    import cefweaver
    from AppKit import NSApp

    # no CEF needed
    names = printing_mac.printers()
    check(isinstance(names, list) and all(isinstance(n, str) for n in names), "printers() lists the destinations of CUPS", names)
    default = printing_mac.default_printer()
    check(default is None or isinstance(default, str), "default_printer() is a name or None", default)
    portrait, landscape = printing_mac.pdf_settings("A4"), printing_mac.pdf_settings("A4", landscape=True)
    check(not portrait.landscape and landscape.landscape
          and (portrait.paper_width, portrait.paper_height) == (landscape.paper_width, landscape.paper_height),
          "landscape is a flag; the paper is given upright (CEF turns it)", (portrait, landscape))
    command = printing_mac.lp_command("/tmp/x.pdf", "Printer", copies=2, paper_name="A5", landscape=True)
    check(command == ["lp", "-d", "Printer", "-n", "2", "-o", "media=A5", "-o", "orientation-requested=4", "/tmp/x.pdf"],
          "lp_command() has the copies, the paper and the orientation", command)
    check(printing_mac.send_with_lp("/tmp/x.pdf", "Printer") == printing_mac.lp_command("/tmp/x.pdf", "Printer"),
          "send_with_lp() is a dry run unless asked")

    # CEF, offscreen, with a print handler that must not be called
    handler_calls, boxes, written = [], [], []

    class Handler(cefweaver.PrintHandler):
        def on_print_start(self, browser):
            handler_calls.append("start")

        def on_print_dialog(self, browser, has_selection, callback):
            handler_calls.append("dialog")
            callback.cancel()
            return True

    class Life(cefweaver.LifeSpanHandler):
        def on_after_created(self, browser):
            boxes.append(browser)

    class Render(cefweaver.RenderHandler):
        def get_view_rect(self, browser):
            return cefweaver.Rect(0, 0, 600, 400)

        def on_paint(self, *args):
            pass

    class Client(cefweaver.Client):
        def __init__(self):
            self.handler, self.life, self.render = Handler(), Life(), Render()

        def get_print_handler(self):
            return self.handler

        def get_life_span_handler(self):
            return self.life

        def get_render_handler(self):
            return self.render

    app = cefweaver.CefApp()
    app.offscreen = True
    app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-print-"))
    app.set_client(Client())
    app.initialize(URL)

    def spin(seconds, until=None):
        end = time.time() + seconds
        while time.time() < end and not (until and until()):
            app.do_message_loop_work()
            time.sleep(0.005)

    spin(2, lambda: boxes)
    spin(1)
    host = boxes[0].get_host()
    work = tempfile.mkdtemp(prefix="cefweaver-print-")
    pdf = os.path.join(work, "page.pdf")
    printing_mac.save_pdf(host, pdf, lambda path, ok: written.append((path, ok)))
    spin(15, lambda: written)
    check(written == [(pdf, True)] and os.path.exists(pdf), "save_pdf() writes the PDF", written)
    pages, width, height = printing_mac.pdf_info(pdf)
    check(pages == 2, "the page break gives two pages", pages)
    check(abs(width - 595) < 3 and abs(height - 842) < 3, "A4 is 595 x 842 pt", (width, height))
    wide = os.path.join(work, "wide.pdf")
    printing_mac.save_pdf(host, wide, lambda path, ok: written.append((path, ok)), paper="Letter", landscape=True)
    spin(15, lambda: len(written) == 2)
    _, wide_width, wide_height = printing_mac.pdf_info(wide)
    check(abs(wide_width - 792) < 3 and abs(wide_height - 612) < 3, "Letter landscape is 792 x 612 pt", (wide_width, wide_height))

    saved = os.path.join(work, "printed.pdf")
    t = time.time()
    done = printing_mac.print_with_system(pdf, copies=1, save_to=saved)
    check(done and os.path.exists(saved) and printing_mac.pdf_info(saved)[0] == 2,
          "print_with_system() sends the PDF through NSPrintOperation (to a file) without a panel", (done, time.time() - t))
    try:
        printing_mac.print_with_system(pdf, printer="no_such_printer")
        check(False, "print_with_system() refuses a printer that is not in the print system")
    except ValueError:
        check(True, "print_with_system() refuses a printer that is not in the print system")
    result = printing_mac.send_with_lp(pdf, "no_such_printer", really=True)
    check(result.returncode != 0, "lp refuses a destination that does not exist (no job)", result.returncode)

    # host.print(): the panel of the system, and not the handler of the application
    closer = close_panel_from_outside(3)
    host.print()
    spin(1)
    panels = [w for w in NSApp.windows() if type(w).__name__ == "NSPanel" and str(w.title()) == "Print"]
    check(len(panels) == 1, "host.print() opens the print panel of the system (an NSPanel titled Print)", len(panels))
    spin(6, lambda: closer.had_panel is not None and NSApp.modalWindow() is None)
    check(closer.had_panel is True, "the panel is modal while it is open (seen from a timer of the run loop)", closer.had_panel)
    check(NSApp.modalWindow() is None, "the panel is closed from outside and the program goes on")
    check(handler_calls == [], "the PrintHandler of the application is not called on macOS", handler_calls)
    spin(0.5)
    check(app.is_running, "CEF runs after the panel")
    app.shutdown()
    check(not app.is_running, "CEF is shut down")


# -- part 2: quickstart_mac.py (the window) ------------------------------------------------------------------------

def window():
    source = open(os.path.join(HERE, "quickstart_mac.py"), encoding="utf-8").read()
    marker = "root.mainloop()"
    assert marker in source
    namespace = {"__name__": "quickstart_mac", "__file__": os.path.join(HERE, "quickstart_mac.py")}
    steps = '''
import sys as _sys, time as _time
_seen = {}
def _expect(label, test, detail):
    ok = bool(test())
    print(("ok    " if ok else "FAIL  ") + label + ("" if ok else "   [%r]" % (detail(),)), flush=True)
    if not ok:
        _smoke_failed.append(label)
def _step1():
    _expect("the window shows the page", lambda: canvas.view is not None, lambda: None)
    buttons["Save PDF"].invoke()
def _step2():
    _expect("Save PDF: the status tells two pages", lambda: "PDF: 2 page(s)" in status.get(), status.get)
    buttons["Send with lp"].invoke()
def _step3():
    text = status.get()
    _expect("Send with lp is a dry run (or says there is no printer)",
            lambda: text.startswith("dry run: lp -d ") or text.startswith("no printer"), lambda: text)
    _seen["lp"] = text
    buttons["Print..."].invoke()
def _step4():
    from AppKit import NSApp
    _expect("Print... opens the print panel of the system",
            lambda: any(type(w).__name__ == "NSPanel" and str(w.title()) == "Print" for w in NSApp.windows()), lambda: None)
def _close():
    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
_smoke_failed = []
root.after(3000, _step1)
root.after(6000, _step2)
root.after(8000, _step3)
root.after(10000, _step4)
_closer = _close_panel(11)
root.after(14000, _close)
root.mainloop()
'''
    namespace["_close_panel"] = close_panel_from_outside
    exec(compile(source.replace(marker, steps, 1), "quickstart_mac.py", "exec"), namespace)
    failed.extend(namespace["_smoke_failed"])
    check(True, "the window closed and CEF shut down")


if __name__ == "__main__":
    if "--window" in sys.argv:
        window()
    else:
        functions()
    finish()
