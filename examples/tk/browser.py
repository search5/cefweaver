"""A small browser: the CefCanvas in a Tk window, with a toolbar and the demo page.

    uv sync                                       # once (see README.md)
    uv run python browser.py [address | demo]
"""

import os
import sys
import tempfile
import tkinter
from tkinter import ttk

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import demo  # noqa: E402
from cefweaver import ui  # noqa: E402
from ceftk import CefCanvas, TkLoop  # noqa: E402

RootClass = tkinter.Tk


class BrowserWindow:
    def __init__(self, root, runtime, url):
        self.root, self.runtime, self.start_url = root, runtime, url
        self.messages = []                              # what the page told Python (the smoke test reads it)
        root.title("cefweaver Tk")
        root.geometry("900x640")
        bar = ttk.Frame(root)
        bar.pack(side="top", fill="x")
        self.back = ttk.Button(bar, text="◀", width=3, command=lambda: self.view.go_back(), state="disabled")
        self.forward = ttk.Button(bar, text="▶", width=3, command=lambda: self.view.go_forward(), state="disabled")
        self.reload_button = ttk.Button(bar, text="⟳", width=3, command=lambda: self.view.reload())
        self.entry = ttk.Entry(bar)
        for widget in (self.back, self.forward, self.reload_button):
            widget.pack(side="left", padx=2, pady=2)
        self.entry.pack(side="left", fill="x", expand=True, padx=2)
        self.entry.bind("<Return>", lambda e: self.view.load_url(self.address(self.entry.get())))
        self.view = CefCanvas(root, runtime)
        self.view.pack(side="top", fill="both", expand=True)
        self.view.on_title = lambda title: root.title(title or "cefweaver Tk")
        self.view.on_address = self.show_address
        self.view.on_loading = self.on_loading
        self.view.on_ready = self.on_ready
        root.protocol("WM_DELETE_WINDOW", self.on_close)

    @staticmethod
    def address(text):
        text = text.strip()
        if text == "demo":
            return demo.DEMO_URL
        return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text

    def show_address(self, url):
        self.entry.delete(0, "end")
        self.entry.insert(0, url)

    def on_loading(self, loading, can_back, can_forward):
        self.back.configure(state="normal" if can_back else "disabled")
        self.forward.configure(state="normal" if can_forward else "disabled")

    def on_ready(self):
        app = self.runtime.app
        app.add_resource(demo.DEMO_URL, demo.DEMO_PAGE)
        app.add_resource(demo.DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        self.view.load_url(self.address(self.start_url))

    def on_close(self):
        self.runtime.shutdown(self.root.destroy)        # the window goes when CEF has closed the browser

    def start(self):
        self.runtime.start(self.view, "about:blank")


def make_runtime(root, window_holder):
    text = os.environ.get("CEFTK_SWITCHES", "")           # "name=value;name=value": Chromium switches
    switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
    runtime = ui.Session(TkLoop(root), switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-tk-"))
    demo.install(runtime.bridge, lambda info: window_holder[0].messages.append(info))
    return runtime


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    root = RootClass()
    holder = []
    runtime = make_runtime(root, holder)
    window = BrowserWindow(root, runtime, argv[1] if len(argv) > 1 else "demo")
    holder.append(window)
    root.after(0, window.start)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
