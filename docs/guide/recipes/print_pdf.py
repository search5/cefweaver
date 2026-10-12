"""Save a page as PDF with BrowserHost.print_to_pdf() and check the files (no screen, no printer)."""
import os
import re
import tempfile

import cefweaver
from cefweaver import types, ui
from cefweaver.ui.headless import HeadlessAdapter

PAGE = ("<style>@page{margin:0} .p{height:1000px;page-break-after:always;font:20px sans-serif}</style>"
        + "".join("<div class=p>PAGE-%d</div>" % n for n in (1, 2, 3)))


def pdf_info(path):
    """(pages, width_pt, height_pt) read from the PDF without a PDF library."""
    data = open(path, "rb").read()
    pages = len(re.findall(rb"/Type\s*/Page(?![s\w])", data))
    x0, y0, x1, y1 = (float(v) for v in re.search(
        rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", data).groups())
    return data[:5], pages, round(x1 - x0, 2), round(y1 - y0, 2)


class Finished(cefweaver.PdfPrintCallback):
    def __init__(self, result):
        self.result = result

    def on_pdf_print_finished(self, path, ok):
        self.result.update(path=path, ok=ok)


adapter = HeadlessAdapter(size=(640, 360))
tmp = tempfile.mkdtemp()
session = ui.Session(adapter, cache_path=os.path.join(tmp, "cache"))
view = ui.BrowserView(adapter)
loaded = []
view.on_loading = lambda loading, back, forward: loading or loaded.append(1)    # the page has loaded


def ready():
    session.app.add_resource("http://app.test/doc.html", PAGE)
    view.load_url("http://app.test/doc.html")


view.on_ready = ready
session.start(view)
adapter.run_until(lambda: loaded, "the page")


def save(name, settings, path=None):
    path = path or os.path.join(tmp, name + ".pdf")
    result = {}
    view.browser.get_host().print_to_pdf(path, settings, Finished(result))
    adapter.run_until(lambda: result, "the PDF " + name)
    info = pdf_info(path) if result["ok"] else "no file: %s" % (not os.path.exists(path))
    print("%s: ok=%s %s" % (name, result["ok"], info))


save("default", types.PdfPrintSettings())
save("a4-landscape", types.PdfPrintSettings(landscape=True, paper_width=8.27, paper_height=11.69))
save("page 2 only", types.PdfPrintSettings(page_ranges="2"))
save("pages 2-9", types.PdfPrintSettings(page_ranges="2-9"))
save("page 9", types.PdfPrintSettings(page_ranges="9"))
save("3-1", types.PdfPrintSettings(page_ranges="3-1"))
save("missing folder", types.PdfPrintSettings(), os.path.join(tmp, "nowhere", "x.pdf"))
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
