"""Print through a PrintHandler on Linux and look at the PDF CEF hands over.

Nothing is sent to a printer: on_print_job copies the PDF and finishes the job.
Run it as `python -P print_handler.py [empty | no-switch | no-handler | cancel | instance]`.
"""
import os
import re
import shutil
import sys
import tempfile

import cefweaver
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

MODE = sys.argv[1] if len(sys.argv) > 1 else ""         # "" | "empty" (no settings filled) | "no-switch" | "no-handler" | "cancel" | "instance"
PAGE = ("<style>@page{margin:0} .p{height:1000px;page-break-after:always;font:20px sans-serif}</style>"
        + "".join("<div class=p>PAGE-%d</div>" % n for n in (1, 2, 3)))
DPI = 300
A4 = (int(8.27 * DPI), int(11.69 * DPI))                # device units: 1/DPI inch

tmp = tempfile.mkdtemp()
events, pdfs, paper_size_calls = [], [], []
choice = {"landscape": False, "ranges": None}


def fill(settings):
    width, height = A4[::-1] if choice["landscape"] else A4
    settings.set_device_name("demo-printer")            # CEF has no printer list; any non-empty name goes
    settings.set_dpi(DPI)
    settings.set_orientation(choice["landscape"])
    settings.set_printer_printable_area((width, height), (0, 0, width, height), False)
    settings.set_copies(1)
    if choice["ranges"]:
        settings.set_page_ranges(choice["ranges"])


def pdf_info(path):
    """(pages, width_pt, height_pt) read from the PDF without a PDF library."""
    data = open(path, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    x0, y0, x1, y1 = (float(v) for v in re.search(
        rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", data).groups())
    return pages, round(x1 - x0, 2), round(y1 - y0, 2)


class Printing(cefweaver.PrintHandler):
    def on_print_start(self, browser):
        events.append("start")

    def on_print_settings(self, browser, settings, get_defaults):
        events.append("settings(get_defaults=%s)" % get_defaults)
        if get_defaults and MODE != "empty":
            fill(settings)

    def on_print_dialog(self, browser, has_selection, callback):
        events.append("dialog")
        if MODE == "cancel":
            return False                                # cancel at once
        settings = cefweaver.PrintSettings.create()
        fill(settings)
        callback.continue_(settings)                    # no dialog: take the settings as they are
        return True

    def on_print_job(self, browser, document_name, pdf_file_path, callback):
        events.append("job")
        copy = os.path.join(tmp, "job%d.pdf" % len(pdfs))
        shutil.copy(pdf_file_path, copy)                # CEF deletes its file once the job is finished
        pdfs.append(copy)
        callback.continue_()
        return True

    def on_print_reset(self, browser):
        events.append("reset")

    def get_pdf_paper_size(self, browser, device_units_per_inch):
        paper_size_calls.append(device_units_per_inch)
        return (A4[0] * device_units_per_inch // DPI, A4[1] * device_units_per_inch // DPI)


adapter = HeadlessAdapter(size=(640, 360))
switches = [] if MODE == "no-switch" else [("disable-features", "EnableOopPrintDrivers")]
session = ui.Session(adapter, switches=switches, cache_path=os.path.join(tmp, "cache"))
view = ui.BrowserView(adapter)
printing = Printing()


class ClientWithPrinting(type(view.client)):            # the handler must be found on the class, not the instance
    def get_print_handler(self):
        return printing


if MODE == "instance":
    view.client.get_print_handler = lambda: printing    # on the instance: CEF does not find it
elif MODE != "no-handler":
    view.client.__class__ = ClientWithPrinting
loaded = []
view.on_loading = lambda loading, back, forward: loading or loaded.append(1)


def ready():
    session.app.add_resource("http://app.test/doc.html", PAGE)
    view.load_url("http://app.test/doc.html")


view.on_ready = ready
session.start(view)
adapter.run_until(lambda: loaded, "the page")


def cycle(label, **options):
    choice.update(landscape=False, ranges=None)
    choice.update(options)
    events.clear()
    count = len(pdfs)
    view.browser.get_host().print()
    try:
        adapter.run_until(lambda: "reset" in events, "the end of the print cycle", timeout=5)
    except TimeoutError:
        events.append("(no end within 5 s)")
    print("%s: %s" % (label, " > ".join(events) or "no callback"))
    if len(pdfs) > count:
        print("    pdf (pages, width pt, height pt):", pdf_info(pdfs[-1]))


cycle("default")
if not MODE:
    cycle("landscape", landscape=True)
    cycle("zero-based range (1, 1)", ranges=[(1, 1)])
    out = os.path.join(tmp, "direct.pdf")
    finished = []

    class Finished(cefweaver.PdfPrintCallback):
        def on_pdf_print_finished(self, path, ok):
            finished.append(ok)

    view.browser.get_host().print_to_pdf(out, cefweaver.types.PdfPrintSettings(), Finished())
    adapter.run_until(lambda: finished, "print_to_pdf")
    print("print_to_pdf:", finished[0], "get_pdf_paper_size calls:", len(paper_size_calls))
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
