"""The smallest program that shows a page in a window made only with CEF's Views (no GUI toolkit): a toolbar with
Back, Forward and Reload buttons and an address field, and the browser. The window closes cleanly.

    uv run python quickstart.py [address]

The window, the layout, the buttons and the field are in browser.py.
"""

import sys

from browser import ViewsBrowser

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"

app = ViewsBrowser(URL, title_changed=lambda title: print("title:", title, flush=True))
app.start()
app.run()                                       # until the window is closed
