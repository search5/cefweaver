"""Open the window of CEF (CefApp, window mode) for two seconds and shut down."""
import tempfile
import time

import cefweaver

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp())
app.initialize("about:blank")
print("initialize() returned")
end = time.monotonic() + 2
while app.is_running and time.monotonic() < end:
    app.do_message_loop_work()
app.shutdown()
print("shut down")
