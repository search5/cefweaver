import base64
import sys
import tempfile
import threading
import time

import cefweaver
from cefweaver import types

ui_thread = threading.get_ident()
ThreadId = types.ThreadId
log = []
resource_threads = set()


def wait_until(condition, what, timeout=30):
    end = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > end:
            raise TimeoutError("timed out waiting for " + what)
        app.do_message_loop_work()
        time.sleep(0.005)


# A JavaScript binding runs on the thread that called initialize(), inside do_message_loop_work().
def on_hello(*args):
    log.append(("binding on the initialize() thread", threading.get_ident() == ui_thread))


def on_fail(*args):
    raise ValueError("raised in a handler")


# A resource handler runs on a thread of CEF. Its methods return the output arguments after the return value.
class Page(cefweaver.ResourceHandler):
    def open(self, request, callback):
        resource_threads.add(threading.get_ident() == ui_thread)     # (a page can be asked for more than once)
        return True, True                       # (handled, handle_request)

    def get_response_headers(self, response):
        response.set_mime_type("text/html")
        response.set_status(200)
        return -1, ""                           # (response_length, redirect_url)

    def read(self, data_out, callback):
        if "sent" in log:
            return False, 0                     # (still data, bytes_read): finished
        log.append("sent")
        body = b"<script>hello(); fail(); hello();</script>"
        data_out[:len(body)] = body
        return True, len(body)


class Factory(cefweaver.SchemeHandlerFactory):
    def create(self, browser, frame, scheme_name, request):
        return Page()


class Record(cefweaver.Task):
    def __init__(self, name):
        self.name = name

    def execute(self):
        log.append((self.name, threading.get_ident() == ui_thread,
                    cefweaver.currently_on(ThreadId.UI), cefweaver.currently_on(ThreadId.IO)))


reported = []
sys.excepthook = lambda kind, value, tb: reported.append("%s: %s" % (kind.__name__, value))

app = cefweaver.CefApp()
app.set_cache_path(tempfile.mkdtemp())
app.add_command_line_switch("ozone-platform", "x11")
app.add_javascript_binding("hello", on_hello)
app.add_javascript_binding("fail", on_fail)
try:
    cefweaver.Request()
except TypeError as error:
    print("Request():", type(error).__name__)
app.initialize("about:blank")
cefweaver.register_scheme_handler_factory("http", "concepts.test", Factory())
app.load_url("http://concepts.test/")
wait_until(lambda: sum(1 for item in log if item[0] == "binding on the initialize() thread") == 2, "both hello() calls")
print("resource handler on the initialize() thread:", resource_threads)
print(*[item for item in log if item != "sent"], sep="\n")
print("reported by sys.excepthook:", reported)

# A task posted from any thread runs where you name, never inside post_task().
cefweaver.post_task(ThreadId.UI, Record("UI task"))
worker = threading.Thread(target=cefweaver.post_task, args=(ThreadId.UI, Record("UI task from a Python thread")))
worker.start()
worker.join()
cefweaver.post_task(ThreadId.IO, Record("IO task"))
wait_until(lambda: sum(1 for item in log if str(item[0]).endswith("task") or "task from" in str(item[0])) == 3, "the tasks")
print(*sorted(item for item in log if "task" in str(item[0])), sep="\n")

app.shutdown()
print("is_running after shutdown():", app.is_running)
for step in (app.do_message_loop_work, lambda: app.add_javascript_binding("late", print), lambda: cefweaver.CefApp().initialize()):
    try:
        step()
    except RuntimeError as error:
        print("RuntimeError:", error)
app.shutdown()                                   # does nothing
