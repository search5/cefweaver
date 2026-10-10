"""Runs the print example for real on a (virtual) X display and checks what a user would get: the dialog with its
defaults, a cancel, a job with another paper, orientation and copies, a job with only the selection. Nothing is
sent to the printer: ``on_print_job`` only looks at the PDF CEF made.

    env -u WAYLAND_DISPLAY -u XDG_SESSION_TYPE xvfb-run -a -s "-screen 0 1000x640x24" uv run python smoke.py [screenshot-directory]

Needs a printer in CUPS (``lpstat -e``): the dialog lists the printers of CUPS.
"""

import base64
import os
import sys
import time
import tkinter
from tkinter import ttk

for name in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE"):
    os.environ.pop(name, None)

from cefweaver import ui  # noqa: E402
from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop  # noqa: E402

import printing  # noqa: E402

PAGE = ("<html><head><title>Quarterly report</title></head><body style='font-family:sans-serif;margin:30px'>"
        "<h1>Quarterly report</h1><p id=s>Select this paragraph and print only the selection.</p>"
        "<p>Second paragraph.</p><div style='page-break-before:always'><h2>Page two</h2></div></body></html>")
SHOTS = sys.argv[1] if len(sys.argv) > 1 else None

root = tkinter.Tk()
root.geometry("900x560+0+0")
status = tkinter.StringVar(value="ready")
bar = ttk.Frame(root, padding=6)
bar.pack(fill="x")
print_button = ttk.Button(bar, text="Print...")
print_button.pack(side="left")
ttk.Label(bar, textvariable=status).pack(side="left", padx=12)
session = ui.Session(TkLoop(root), switches=printing.SWITCHES)
canvas = CefCanvas(root, session, width=900, height=500)
canvas.pack(fill="both", expand=True)
jobs = []                                           # (pages, width, height, choice) of each job


def job_done(pdf_path, choice):
    jobs.append(printing.pdf_info(pdf_path) + (choice,))
    status.set("job received")


printing.attach(canvas, printing.Printing(root, status.set, job_done))
titles = []
canvas.on_title = titles.append
canvas.on_ready = lambda: canvas.load_url("data:text/html;base64," + base64.b64encode(PAGE.encode()).decode())
print_button.config(command=lambda: canvas.view.host(lambda host: host.print()))
closed = []
root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(lambda: (root.destroy(), closed.append(True))))
root.after(0, lambda: session.start(canvas))

failed = []


def spin(condition, what, timeout=30):
    end = time.time() + timeout
    while not condition():
        if time.time() > end:
            raise TimeoutError("timed out waiting for " + what)
        root.update()
        time.sleep(0.005)


def settle(seconds=0.4):
    end = time.time() + seconds
    while time.time() < end:
        root.update()
        time.sleep(0.005)


def check(ok, what, detail=None):
    print(("ok    " if ok else "FAIL  ") + what + ("" if ok or detail is None else "   [%r]" % (detail,)), flush=True)
    if not ok:
        failed.append(what)


def shot(name):
    if not SHOTS:
        return
    try:
        from PIL import ImageGrab
        os.makedirs(SHOTS, exist_ok=True)
        ImageGrab.grab(xdisplay=os.environ.get("DISPLAY")).save(os.path.join(SHOTS, name + ".png"))
    except Exception as error:                      # a screenshot is a bonus
        print("no screenshot:", error)


def dialog():
    return next((w for w in root.winfo_children() if isinstance(w, printing.PrintDialog)), None)


def open_dialog():
    print_button.invoke()
    spin(lambda: dialog() is not None, "the print dialog")
    settle()
    return dialog()


spin(lambda: "Quarterly report" in titles, "the page")
settle(1.0)
check(True, "the page is shown")

d = open_dialog()
shot("1-dialog-defaults")
check(d.paper.get() == "A4" and not d.landscape.get() and d.copies.get() == 1,
      "the dialog starts with A4, portrait, one copy", (d.paper.get(), d.landscape.get(), d.copies.get()))
check(d.printer.get() in printing.printers(), "the printer is one of CUPS", d.printer.get())
check("disabled" in d.selection_box.state(), "only the selection is off when nothing is selected")
d.cancel_button.invoke()
spin(lambda: status.get() == "cancelled", "the cancel")
settle()
check(not jobs, "a cancelled dialog makes no job")

d = open_dialog()
d.paper.set("A5")
d.landscape.set(True)
d.copies.set(2)
settle()
shot("2-dialog-a5-landscape")
d.print_button.invoke()
spin(lambda: len(jobs) == 1, "the job")
pages, width, height, choice = jobs[0]
check(pages == 2, "the PDF has the two pages of the document", pages)
check(abs(width - 595) < 2 and abs(height - 420) < 2, "the PDF is A5 landscape (595 x 420 pt)", (width, height))
check(choice["copies"] == 2 and choice["landscape"] and choice["paper_name"] == "A5",
      "the choices of the dialog arrive with the job", choice)
shot("3-job")

frame = canvas.view.browser.get_main_frame()
frame.execute_java_script("var r=document.createRange();r.selectNodeContents(document.getElementById('s'));"
                          "var s=getSelection();s.removeAllRanges();s.addRange(r);", "", 0)
settle(0.8)
d = open_dialog()
check("disabled" not in d.selection_box.state(), "only the selection is on when the page has a selection")
d.selection.set(True)
d.print_button.invoke()
spin(lambda: len(jobs) == 2, "the job of the selection")
pages, width, height, choice = jobs[1]
check(pages == 1 and choice["selection_only"], "only the selection makes a PDF of one page", (pages, choice))
check(abs(width - 595) < 2 and abs(height - 842) < 2, "the second job is A4 portrait again", (width, height))

root.protocol("WM_DELETE_WINDOW", lambda: None)
session.shutdown(lambda: (root.destroy(), closed.append(True)))
spin(lambda: closed, "the shutdown")
check(True, "the browser is closed and CEF is shut down")
print("ALL OK" if not failed else "FAILED: " + ", ".join(failed))
sys.exit(1 if failed else 0)
