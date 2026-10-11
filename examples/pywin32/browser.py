"""A small browser in a Win32 window (pywin32; no toolbar), with the demo page.

    uv sync                                     # once (see README.md)
    uv run python browser.py [address | demo]

Keys: Alt+Left and Alt+Right go back and forward, F5 reloads. Links and the page do the rest.
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))

import demo  # noqa: E402
from cefweaver.ui.toolkits.pywin32 import Win32Browser  # noqa: E402


def address(text):
    text = text.strip()
    if text == "demo":
        return demo.DEMO_URL
    return text if "://" in text or text.startswith(("about:", "data:")) else "https://" + text


def make_browser(url="demo"):
    text = os.environ.get("CEFWIN32_SWITCHES", "")           # "name=value;name=value": Chromium switches
    switches = [tuple(item.split("=", 1)) if "=" in item else (item, "") for item in text.split(";") if item]
    win = Win32Browser(switches, cache_path=tempfile.mkdtemp(prefix="cefweaver-win32-"))
    win.messages = []                                      # what the page told Python (the smoke test reads it)
    demo.install(win.bridge, win.messages.append)

    def on_ready():
        win.app.add_resource(demo.DEMO_URL, demo.DEMO_PAGE)
        win.app.add_resource(demo.DEMO_URL + "other", "<h1>another page</h1><a href='/'>back</a>")
        win.load_url(address(url))
    win.on_ready = on_ready
    return win


def main(argv=None):
    argv = list(sys.argv if argv is None else argv)
    win = make_browser(argv[1] if len(argv) > 1 else "demo")
    win.start("about:blank")
    win.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
