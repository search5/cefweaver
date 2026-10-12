import base64
import tempfile
import threading
import time

import cefweaver

ThreadId = cefweaver.types.ThreadId
PAGE = "<script>hello('the page has run');</script>"
main = threading.get_ident()
woken = threading.Event()
said = []
ran = []


class FromAThread(cefweaver.Task):
    def execute(self):
        ran.append(("task from a thread, on the initialize() thread:", threading.get_ident() == main))


app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp())
app.add_command_line_switch("ozone-platform", "x11")
app.add_javascript_binding("hello", said.append)

# The pump sets external_message_pump and installs itself as the app handler. wake() may be called from any thread
# of CEF: here it only sets an event, which is what an event loop of a toolkit would do to leave its sleep.
pump = cefweaver.MessagePump(app, wake=lambda delay: woken.set())
print("external_message_pump:", app.settings.external_message_pump)
app.initialize("data:text/html;base64," + base64.b64encode(PAGE.encode()).decode())

# Our own event loop: sleep until CEF asks for work (or until the deadline), then run it. No polling interval.
runs, longest = 0, 0.0
posted = False
end = time.monotonic() + 30
while not (said and ran):
    assert time.monotonic() < end, "timed out"
    if said and not posted:
        posted = True
        threading.Timer(0.2, cefweaver.post_task, args=(ThreadId.UI, FromAThread())).start()
    wait = pump.timeout()
    longest = max(longest, wait)
    if wait > 0:
        woken.wait(wait)
        woken.clear()
    if pump.run():
        runs += 1
print(said)
print(ran)
print("runs:", runs > 0, "- longest wait <= 1/30 s:", longest <= cefweaver.pump.MAX_DELAY + 0.005)
app.shutdown()
print("shut down")
