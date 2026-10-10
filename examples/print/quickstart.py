"""A page in a Tk window and a print dialog of the application (CUPS, Linux).

    uv run python quickstart.py            # a dry run: the PDF is made, nothing goes to the printer
    REALLY_PRINT=1 uv run python quickstart.py     # the job is sent to the printer with lp
"""

import base64
import os
import tkinter
from tkinter import ttk

from cefweaver import ui
from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

import printing

REALLY_PRINT = os.environ.get("REALLY_PRINT") == "1"
PAGE = ("<html><head><title>Quarterly report</title></head><body style='font-family:sans-serif;margin:30px'>"
        "<h1>Quarterly report</h1><p id=s>Select this paragraph and print only the selection.</p>"
        "<p>Second paragraph.</p><div style='page-break-before:always'><h2>Page two</h2></div></body></html>")

root = tkinter.Tk()
root.title("print example")
root.geometry("900x560")
status = tkinter.StringVar(value="ready")
bar = ttk.Frame(root, padding=6)
bar.pack(fill="x")
print_button = ttk.Button(bar, text="Print...")
print_button.pack(side="left")
ttk.Label(bar, textvariable=status).pack(side="left", padx=12)

session = ui.Session(TkLoop(root), switches=printing.SWITCHES)     # CEF, run by the Tk loop
canvas = CefCanvas(root, session, width=900, height=500)
canvas.pack(fill="both", expand=True)


def job_done(pdf_path, choice):
    pages, width, height = printing.pdf_info(pdf_path)
    text = "job: %d page(s), %.0f x %.0f pt (%s %s), %d copies" % (
        pages, width, height, choice["paper_name"], "landscape" if choice["landscape"] else "portrait",
        choice["copies"])
    if REALLY_PRINT:
        result = printing.send_to_cups(pdf_path, choice)
        text += "  |  lp: " + (result.stdout + result.stderr).strip()
    else:
        text += "  |  dry run: nothing sent to the printer"
    status.set(text)


printing.attach(canvas, printing.Printing(root, status.set, job_done))
canvas.on_ready = lambda: canvas.load_url("data:text/html;base64," + base64.b64encode(PAGE.encode()).decode())
print_button.config(command=lambda: canvas.view.host(lambda host: host.print()))
root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(root.destroy))   # close the browser, then the window
root.after(0, lambda: session.start(canvas))
root.mainloop()
