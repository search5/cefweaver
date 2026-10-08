"""The smallest program that shows a page in a Tk window.   uv run python quickstart.py [address]"""

import sys
import tkinter

from cefweaver import ui
from cefweaver.ui.toolkits.tk import CefCanvas, TkLoop

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

root = tkinter.Tk()
session = ui.Session(TkLoop(root))                    # CEF, run by the Tk loop
canvas = CefCanvas(root, session)                     # the browser, a Canvas
canvas.pack(fill="both", expand=True)
canvas.on_ready = lambda: canvas.load_url(URL)        # the browser exists
canvas.on_title = lambda title: print("title:", title, flush=True)
root.protocol("WM_DELETE_WINDOW", lambda: session.shutdown(root.destroy))   # close the browser, then the window
root.after(0, lambda: session.start(canvas))
root.mainloop()
