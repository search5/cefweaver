"""A small browser: the CefView in a Kivy window, with a toolbar and the demo page.

    uv sync                                       # once (see README.md)
    uv run python browser.py [address | demo]
"""

import os
import sys
import tempfile

os.environ.setdefault("KIVY_NO_ARGS", "1")                        # Kivy would read our argument as its own
os.environ.setdefault("SDL_VIDEODRIVER", "x11")                   # never the real Wayland session

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

from kivy.config import Config  # noqa: E402

Config.set("graphics", "width", "900")
Config.set("graphics", "height", "640")
Config.set("graphics", "resizable", "1")
Config.set("kivy", "exit_on_escape", "0")                          # Escape is a key of the page (it closes a popup)
Config.set("input", "mouse", "mouse,disable_multitouch")          # a right click is a right click, no red dots

from kivy.app import App  # noqa: E402
from kivy.clock import Clock  # noqa: E402
from kivy.core.window import Window  # noqa: E402
from kivy.uix.boxlayout import BoxLayout  # noqa: E402
from kivy.uix.button import Button  # noqa: E402
from kivy.uix.textinput import TextInput  # noqa: E402

import demo  # noqa: E402
from cefweaver import ui  # noqa: E402
from cefweaver.ui.toolkits.kivy import CefView, KivyLoop  # noqa: E402


def address(text):
    text = text.strip()
    if text == "demo":
        return demo.DEMO_URL
    return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text


class Browser:
    """The widgets and the runtime (the App below and the smoke test both use this)."""

    def __init__(self, url="demo"):
        text = os.environ.get("CEFKIVY_SWITCHES", "")        # "name=value;name=value": Chromium switches
        switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
        self.runtime = ui.Session(KivyLoop(), switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-kivy-"))
        self.messages = []                                   # what the page told Python (the smoke test reads it)
        demo.install(self.runtime.bridge, self.messages.append)
        self.start_url = url
        self.view = CefView(self.runtime)
        self.back = Button(text="<", size_hint_x=None, width=40, disabled=True)
        self.forward = Button(text=">", size_hint_x=None, width=40, disabled=True)
        self.reload_button = Button(text="R", size_hint_x=None, width=40)
        self.entry = TextInput(multiline=False, write_tab=False)
        bar = BoxLayout(size_hint_y=None, height=36)
        for widget in (self.back, self.forward, self.reload_button, self.entry):
            bar.add_widget(widget)
        self.root = BoxLayout(orientation="vertical")
        self.root.add_widget(bar)
        self.root.add_widget(self.view)
        self.title = "cefweaver Kivy"
        self.back.bind(on_release=lambda b: self.view.go_back())
        self.forward.bind(on_release=lambda b: self.view.go_forward())
        self.reload_button.bind(on_release=lambda b: self.view.reload())
        self.entry.bind(on_text_validate=lambda e: self.view.load_url(address(e.text)))
        self.view.bind(on_title=self.on_title, on_address=self.on_address, on_loading=self.on_loading, on_ready=self.on_ready)

    def on_title(self, view, title):
        self.title = title or "cefweaver Kivy"
        Window.set_title(self.title)

    def on_address(self, view, url):
        self.entry.text = url

    def on_loading(self, view, loading, can_back, can_forward):
        self.back.disabled = not can_back
        self.forward.disabled = not can_forward

    def on_ready(self, view):
        app = self.runtime.app
        app.add_resource(demo.DEMO_URL, demo.DEMO_PAGE)
        app.add_resource(demo.DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        self.view.load_url(address(self.start_url))

    def start(self):
        self.runtime.start(self.view, "about:blank")


class BrowserApp(App):
    title = "cefweaver Kivy"

    def __init__(self, url, **kwargs):
        super().__init__(**kwargs)
        self.browser = Browser(url)

    def build(self):
        Window.bind(on_request_close=self.on_request_close)
        return self.browser.root

    def on_start(self):
        Clock.schedule_once(lambda dt: self.browser.start(), 0)

    def on_request_close(self, *args):
        self.browser.runtime.shutdown(self.stop)              # the window goes when CEF has closed the browser
        return True


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    BrowserApp(argv[1] if len(argv) > 1 else "demo").run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
