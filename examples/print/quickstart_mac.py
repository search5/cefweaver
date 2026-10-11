"""A page in a Tk window and the ways to print it on macOS (see printing_mac.py). quickstart.py starts this on macOS.

    uv run python quickstart.py            # a dry run: the PDF is made, nothing goes to the printer
    REALLY_PRINT=1 uv run python quickstart.py     # "Send with lp" sends the job to the default printer

* Print...        the print panel of the system (host.print()): the system does the printing, the application
                  gets no callback; the panel is modal, the window waits until it is closed
* Save PDF        CEF writes the page to a PDF (host.print_to_pdf()), the status tells pages and size
* Print PDF...    that PDF to the system with NSPrintOperation, in the print panel of the system
* Send with lp    that PDF to CUPS with lp (dry run unless REALLY_PRINT=1)
"""

import base64
import os
import tempfile
import tkinter
from tkinter import ttk

from cefweaver import ui
from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

import printing_mac as printing

REALLY_PRINT = os.environ.get("REALLY_PRINT") == "1"
PAGE = ("<html><head><title>Quarterly report</title></head><body style='font-family:sans-serif;margin:30px'>"
        "<h1>Quarterly report</h1><p id=s>Select this paragraph and print only the selection.</p>"
        "<p>Second paragraph.</p><div style='page-break-before:always'><h2>Page two</h2></div></body></html>")

root = tkinter.Tk()
root.title("print example (macOS)")
root.geometry("900x560")
status = tkinter.StringVar(value="ready")
bar = ttk.Frame(root, padding=6)
bar.pack(fill="x")
buttons = {}
for name in ("Print...", "Save PDF", "Print PDF...", "Send with lp"):
    buttons[name] = ttk.Button(bar, text=name)
    buttons[name].pack(side="left", padx=(0, 6))
ttk.Label(bar, textvariable=status).pack(side="left", padx=12)

session = ui.Session(TkLoop(root), switches=printing.SWITCHES)     # CEF, run by the Tk loop
canvas = CefCanvas(root, session, width=900, height=500)
canvas.pack(fill="both", expand=True)
pdf_path = os.path.join(tempfile.mkdtemp(prefix="cefweaver-print-"), "page.pdf")
last_pdf = []                                       # the PDF CEF made last, once it is written


def pdf_done(path, ok):                             # on the thread of CEF, which is the thread of Tk
    if not ok:
        status.set("print_to_pdf failed")
        return
    last_pdf[:] = [path]
    pages, width, height = printing.pdf_info(path)
    status.set("PDF: %d page(s), %.0f x %.0f pt  |  %s" % (pages, width, height, path))


def with_pdf(action):
    """Make the PDF first (the page as it is now), then do ``action(path)`` with it."""
    def done(path, ok):
        pdf_done(path, ok)
        if ok:
            action(path)
    canvas.view.host(lambda host: printing.save_pdf(host, pdf_path, done))


def system_panel(path):
    ok = printing.print_with_system(path, show_panel=True)       # modal: returns when the panel is closed
    status.set("system print panel closed (%s)" % ("job done" if ok else "no job"))


def lp(path):
    target = printing.default_printer()
    if target is None:
        known = printing.printers()
        target = known[0] if known else None
    if target is None:
        status.set("no printer in CUPS (lpstat -e)")
        return
    result = printing.send_with_lp(path, target, really=REALLY_PRINT)
    if REALLY_PRINT:
        status.set("lp: " + (result.stdout + result.stderr).strip())
    else:
        status.set("dry run: " + " ".join(result))


buttons["Print..."].config(command=lambda: (status.set("system print panel"),
                                            canvas.view.host(lambda host: host.print())))
buttons["Save PDF"].config(command=lambda: with_pdf(lambda path: None))
buttons["Print PDF..."].config(command=lambda: with_pdf(system_panel))
buttons["Send with lp"].config(command=lambda: with_pdf(lp))

canvas.on_ready = lambda: canvas.load_url("data:text/html;base64," + base64.b64encode(PAGE.encode()).decode())
root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(root.destroy))   # close the browser, then the window
root.after(0, lambda: session.start(canvas))
root.mainloop()
