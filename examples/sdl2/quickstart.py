"""The smallest program that shows a page in an SDL2 window.   uv run python quickstart.py [address]"""

import sys

from cefweaver.ui.toolkits.sdl2 import SdlBrowser

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"


class Browser(SdlBrowser):                            # the window, the browser and the event loop in one
    def browser_title(self, title):
        super().browser_title(title)
        print("title:", title, flush=True)


browser = Browser()
browser.on_ready = lambda: browser.load_url(URL)
browser.start("about:blank")
browser.run()                                         # until the window is closed
