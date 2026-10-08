"""The smallest program that shows a page in a Kivy window.   uv run python quickstart.py [address]"""

import os
import sys

os.environ.setdefault("KIVY_NO_ARGS", "1")

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.config import Config  # noqa: E402

Config.set("kivy", "exit_on_escape", "0")             # Escape is a key of the page

from kivy.core.window import Window  # noqa: E402

from cefweaver import ui  # noqa: E402
from cefweaver.ui.toolkits.kivy import CefView, KivyLoop  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "https://example.org/"


class Quickstart(App):
    def build(self):
        self.session = ui.Session(KivyLoop())         # CEF, run by the Kivy clock
        self.view = CefView(self.session)             # the browser, a Widget
        self.view.bind(on_ready=lambda view: view.load_url(URL),
                       on_title=lambda view, title: print("title:", title, flush=True))
        Window.bind(on_request_close=lambda *args: self.session.shutdown(self.stop) or True)   # close the browser first
        return self.view

    def on_start(self):
        Clock.schedule_once(lambda dt: self.session.start(self.view), 0)


Quickstart().run()
