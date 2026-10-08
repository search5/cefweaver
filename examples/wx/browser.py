"""A small browser: the CefPanel in a wxPython window, with a toolbar and the demo page.

    uv sync                                       # once (see README.md)
    uv run python browser.py [address | demo]
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import wx  # noqa: E402

import demo  # noqa: E402
from cefwx import CefPanel, Runtime  # noqa: E402


class BrowserWindow(wx.Frame):
    def __init__(self, runtime, url):
        super().__init__(None, title="cefweaver wxPython", size=(900, 640))
        self.runtime, self.start_url = runtime, url
        self.messages = []                              # what the page told Python (the smoke test reads it)
        bar = wx.Panel(self)
        self.back = wx.Button(bar, label="<", size=(32, -1))
        self.forward = wx.Button(bar, label=">", size=(32, -1))
        self.reload_button = wx.Button(bar, label="R", size=(32, -1))
        self.entry = wx.TextCtrl(bar, style=wx.TE_PROCESS_ENTER)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for widget in (self.back, self.forward, self.reload_button):
            row.Add(widget, 0, wx.ALL, 2)
        row.Add(self.entry, 1, wx.ALL | wx.EXPAND, 2)
        bar.SetSizer(row)
        self.view = CefPanel(self, runtime)
        column = wx.BoxSizer(wx.VERTICAL)
        column.Add(bar, 0, wx.EXPAND)
        column.Add(self.view, 1, wx.EXPAND)
        self.SetSizer(column)
        self.back.Disable()
        self.forward.Disable()
        self.back.Bind(wx.EVT_BUTTON, lambda e: self.view.go_back())
        self.forward.Bind(wx.EVT_BUTTON, lambda e: self.view.go_forward())
        self.reload_button.Bind(wx.EVT_BUTTON, lambda e: self.view.reload())
        self.entry.Bind(wx.EVT_TEXT_ENTER, lambda e: self.view.load_url(self.address(self.entry.GetValue())))
        self.view.on_title = lambda title: self.SetTitle(title or "cefweaver wxPython")
        self.view.on_address = self.entry.ChangeValue
        self.view.on_loading = self.on_loading
        self.view.on_ready = self.on_ready
        self.Bind(wx.EVT_CLOSE, self.on_close)

    @staticmethod
    def address(text):
        text = text.strip()
        if text == "demo":
            return demo.DEMO_URL
        return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text

    def on_loading(self, loading, can_back, can_forward):
        self.back.Enable(can_back)
        self.forward.Enable(can_forward)

    def on_ready(self):
        app = self.runtime.app
        app.add_resource(demo.DEMO_URL, demo.DEMO_PAGE)
        app.add_resource(demo.DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        self.view.load_url(self.address(self.start_url))

    def on_close(self, event):
        self.runtime.shutdown(self.Destroy)             # the window goes when CEF has closed the browser

    def start(self):
        self.runtime.start(self.view, "about:blank")


def make_runtime(window_holder):
    text = os.environ.get("CEFWX_SWITCHES", "")           # "name=value;name=value": Chromium switches
    switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
    runtime = Runtime(switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-wx-"))
    demo.install(runtime.bridge, lambda info: window_holder[0].messages.append(info))
    return runtime


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    app = wx.App()
    holder = []
    runtime = make_runtime(holder)
    window = BrowserWindow(runtime, argv[1] if len(argv) > 1 else "demo")
    holder.append(window)
    window.Show()
    wx.CallAfter(window.start)
    app.MainLoop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
