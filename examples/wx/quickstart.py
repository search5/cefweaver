"""The smallest program that shows a page in a wxPython window.   uv run python quickstart.py [address]"""

import sys

import wx

from cefweaver import ui
from cefweaver.ui.toolkits.wx import CefPanel, WxLoop

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

app = wx.App()
session = ui.Session(WxLoop())                        # CEF, run by the wx loop
frame = wx.Frame(None, title="cefweaver", size=(900, 640))
panel = CefPanel(frame, session)                      # the browser, a wx.Panel
panel.on_ready = lambda: panel.load_url(URL)
panel.on_title = lambda title: print("title:", title, flush=True)
frame.Bind(wx.EVT_CLOSE, lambda event: session.shutdown(frame.Destroy))   # close the browser first
frame.Show()
wx.CallAfter(session.start, panel)
app.MainLoop()
