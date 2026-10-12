import base64
import tempfile
import time

import cefweaver

PAGE = "<script>setTimeout(function () { finish(); }, 100);</script>"
browsers = []
calls = []


class Life(cefweaver.LifeSpanHandler):
    def on_after_created(self, browser):
        browsers.append(browser)


class MyClient(cefweaver.Client):
    def __init__(self):
        self.life = Life()

    def get_life_span_handler(self):
        return self.life


def finish(*args):
    calls.append("finish() called by the page")
    browsers[0].get_host().close_browser(True)       # close the window; the loop below ends with it


app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp())
app.add_command_line_switch("ozone-platform", "x11")
app.set_client(MyClient())
app.add_javascript_binding("finish", finish)
app.initialize("data:text/html;base64," + base64.b64encode(PAGE.encode()).decode())

# The polling loop: nothing happens in CEF unless this thread calls do_message_loop_work().
iterations = 0
while app.is_running:
    app.do_message_loop_work()
    iterations += 1
    time.sleep(0.005)

print(calls)
print("the loop ran:", iterations > 0, "- is_running:", app.is_running)
app.shutdown()
print("shut down")
