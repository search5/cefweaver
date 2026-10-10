"""Printing from cefweaver on Linux: a print dialog drawn by the application (Tk), CUPS through pycups.

CEF has no print dialog and no list of printers on Linux. The application

* asks CUPS for the printers and the papers (``printers()``, ``paper_sizes()``),
* gives CEF the default settings in ``PrintHandler.on_print_settings``,
* shows its own dialog in ``PrintHandler.on_print_dialog`` and answers with ``callback.continue_(settings)``
  (or ``callback.cancel()``),
* takes the PDF CEF made in ``PrintHandler.on_print_job`` and sends it to CUPS (``send_to_cups()``).

CEF must also be started with ``disable-features=EnableOopPrintDrivers`` (``SWITCHES``): with the printing
service of Chromium in its own process the job fails with ``kFailed`` and ``on_print_job`` never comes.
"""

import os
import re
import shutil
import subprocess
import tempfile
import tkinter
from tkinter import ttk

import cups

import cefweaver

SWITCHES = [("disable-features", "EnableOopPrintDrivers")]
DPI = 300                                   # device units of the print settings: 1/DPI inch

# The PPD of a driverless printer lists the names of the papers (PageSize) but not their sizes: the sizes of the
# standard names (points), and a name like "4x6" is in inches.
KNOWN = {"A4": (595.28, 841.89), "A5": (419.53, 595.28), "A6": (297.64, 419.53), "B5": (498.9, 708.66),
         "ISOB5": (498.9, 708.66), "Letter": (612, 792), "Legal": (612, 1008), "Executive": (521.86, 756),
         "FanFoldGermanLegal": (612, 936)}

_connection = None


def connection():
    global _connection
    if _connection is None:
        _connection = cups.Connection()
    return _connection


def printers():
    """The names of the printers of CUPS (``lpstat -e``)."""
    return sorted(connection().getPrinters())


def paper_sizes(printer):
    """``{name: (width_pt, height_pt)}`` of the papers in the PPD of the printer."""
    ppd = cups.PPD(connection().getPPD(printer))
    sizes = {}
    for choice in ppd.findOption("PageSize").choices:
        name = choice["choice"]
        if name in KNOWN:
            sizes[name] = KNOWN[name]
        elif "x" in name and name.replace("x", "").replace(".", "").isdigit():
            width, height = name.split("x")
            sizes[name] = (float(width) * 72, float(height) * 72)
    return sizes


def fill(settings, printer, paper, landscape, copies, selection_only=False):
    """Put the choices into a ``PrintSettings``. The page is in device units; a landscape page swaps its sides.
    ``copies`` is not part of the PDF CEF makes: it goes to the printer (``send_to_cups``)."""
    width, height = (int(round(v / 72 * DPI)) for v in paper)
    if landscape:
        width, height = height, width
    settings.set_device_name(printer)
    settings.set_dpi(DPI)
    settings.set_orientation(landscape)
    settings.set_printer_printable_area((width, height), (0, 0, width, height), False)
    settings.set_copies(copies)
    settings.set_selection_only(selection_only)


def pdf_info(path):
    """``(pages, width_pt, height_pt)`` of the first page of a PDF that Chromium wrote (no PDF library needed)."""
    data = open(path, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    box = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", data)
    if not box:
        return pages, 0.0, 0.0
    x0, y0, x1, y1 = (float(v) for v in box.groups())
    return pages, x1 - x0, y1 - y0


def send_to_cups(pdf_path, choice):
    """Send the PDF to the printer with ``lp``: the copies and the paper are options of the job."""
    command = ["lp", "-d", choice["printer"], "-n", str(choice["copies"]), "-o", "media=" + choice["paper_name"]]
    if choice["landscape"]:
        command += ["-o", "orientation-requested=4"]
    return subprocess.run(command + [pdf_path], capture_output=True, text=True)


class PrintDialog(tkinter.Toplevel):
    """The dialog of the application: printer, paper, orientation, copies, only the selection."""

    def __init__(self, master, has_selection, on_print, on_cancel, position="+300+140"):
        super().__init__(master)
        self.title("Print")
        self.geometry(position)
        self.resizable(False, False)
        self.on_print, self.on_cancel = on_print, on_cancel
        names = printers()
        self.printer = tkinter.StringVar(value=names[0])
        self.sizes = paper_sizes(self.printer.get())
        self.paper = tkinter.StringVar(value="A4" if "A4" in self.sizes else next(iter(self.sizes)))
        self.landscape = tkinter.BooleanVar(value=False)
        self.copies = tkinter.IntVar(value=1)
        self.selection = tkinter.BooleanVar(value=False)
        body = ttk.Frame(self, padding=14)
        body.grid()
        body.columnconfigure(0, minsize=96)
        ttk.Label(body, text="Printer").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(body, textvariable=self.printer, values=names, state="readonly", width=42).grid(
            row=0, column=1, columnspan=2)
        ttk.Label(body, text="Paper size").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(body, textvariable=self.paper, values=list(self.sizes), state="readonly", width=14).grid(
            row=1, column=1, sticky="w")
        self.size_label = ttk.Label(body, text="")
        self.size_label.grid(row=1, column=2, sticky="w")
        ttk.Label(body, text="Orientation").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Radiobutton(body, text="Portrait", variable=self.landscape, value=False).grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(body, text="Landscape", variable=self.landscape, value=True).grid(row=2, column=2, sticky="w")
        ttk.Label(body, text="Copies").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Spinbox(body, from_=1, to=99, textvariable=self.copies, width=5).grid(row=3, column=1, sticky="w")
        self.selection_box = ttk.Checkbutton(body, text="Only the selection", variable=self.selection)
        self.selection_box.grid(row=4, column=0, columnspan=3, sticky="w", pady=4)
        if not has_selection:                       # CEF says whether the page has a selection
            self.selection_box.state(["disabled"])
        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        self.print_button = ttk.Button(buttons, text="Print", command=self.accept)
        self.print_button.pack(side="right", padx=(8, 0))
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel)
        self.cancel_button.pack(side="right")
        self.paper.trace_add("write", lambda *args: self.show_size())
        self.show_size()
        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def show_size(self):
        width, height = self.sizes.get(self.paper.get(), (0, 0))
        self.size_label.config(text="%.0f x %.0f mm" % (width / 72 * 25.4, height / 72 * 25.4))

    def choice(self):
        return dict(printer=self.printer.get(), paper=self.sizes[self.paper.get()], paper_name=self.paper.get(),
                    landscape=self.landscape.get(), copies=self.copies.get(), selection_only=self.selection.get())

    def accept(self):
        choice = self.choice()
        self.destroy()
        self.on_print(choice)

    def cancel(self):
        self.destroy()
        self.on_cancel()


class Printing(cefweaver.PrintHandler):
    """CEF's print handler for Linux. ``status(text)`` tells what happens, ``job_done(pdf_path, choice)`` is
    called with a copy of the PDF CEF made (CEF deletes its own file once the job is completed)."""

    def __init__(self, master, status=lambda text: None, job_done=None, keep_dir=None):
        super().__init__()
        self.master, self.status = master, status
        self.job_done = job_done or (lambda path, choice: None)
        self.keep_dir = keep_dir or tempfile.mkdtemp(prefix="cefweaver-print-")
        self.choice = {}
        self.jobs = 0

    def on_print_settings(self, browser, settings, get_defaults):
        if get_defaults:                            # the defaults: the first printer, A4, portrait
            first = printers()[0]
            sizes = paper_sizes(first)
            fill(settings, first, sizes.get("A4") or next(iter(sizes.values())), False, 1)

    def on_print_dialog(self, browser, has_selection, callback):
        def go(choice):
            settings = cefweaver.PrintSettings.create()
            fill(settings, choice["printer"], choice["paper"], choice["landscape"], choice["copies"],
                 choice["selection_only"])
            self.choice = choice
            callback.continue_(settings)            # CEF makes the PDF, on_print_job follows

        def cancelled():
            callback.cancel()
            self.status("cancelled")

        self.status("dialog open")
        PrintDialog(self.master, has_selection, go, cancelled)
        return True                                 # the dialog is shown and answered later

    def on_print_job(self, browser, document_name, pdf_file_path, callback):
        self.jobs += 1
        kept = os.path.join(self.keep_dir, "job%d.pdf" % self.jobs)
        shutil.copy(pdf_file_path, kept)            # the file of CEF goes away after callback.continue_()
        try:
            self.job_done(kept, self.choice)
        finally:
            callback.continue_()
        return True


def attach(canvas, handler):
    """Give the client of a ``cefweaver.ui`` view the print handler. The client of the view has none and CEF
    finds the handlers of a client by the class, not by the instance: an attribute on the instance is not seen."""

    class ClientWithPrinting(type(canvas.view.client)):
        def get_print_handler(self):
            return handler

    canvas.view.client.__class__ = ClientWithPrinting
