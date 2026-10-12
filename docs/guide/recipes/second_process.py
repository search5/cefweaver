"""Start a second process with the same cache_path as this one and see what each side gets."""
import os
import subprocess
import sys
import tempfile

import cefweaver
from cefweaver import ui
from cefweaver.ui.headless import HeadlessAdapter

cache = tempfile.mkdtemp()
relaunched = []


class Hooks(cefweaver.AppHandler):
    def on_already_running_app_relaunch(self, command_line, current_directory):
        relaunched.append((command_line.get_switch_value("second"), os.path.realpath(current_directory) == os.path.realpath(cache)))
        return True                                     # handled: no new window


SECOND = """
import cefweaver
app = cefweaver.CefApp()
app.offscreen = True
app.set_cache_path(%r)
app.add_command_line_switch("second", "yes")
try:
    app.initialize("about:blank")
    print("second: initialize() returned")
except RuntimeError as error:
    print("second: RuntimeError:", error)
""" % cache

adapter = HeadlessAdapter(size=(320, 200))
session = ui.Session(adapter, cache_path=cache)
session.app.set_app_handler(Hooks())
view = ui.BrowserView(adapter)
ready = []
view.on_ready = lambda: ready.append(1)
session.start(view)
adapter.run_until(lambda: ready, "the browser")
second = subprocess.Popen([sys.executable, "-P", "-c", SECOND], cwd=cache, stdout=subprocess.PIPE, text=True)
adapter.run_until(lambda: relaunched and second.poll() is not None, "the second process")
print(second.stdout.read().strip())
print("first: on_already_running_app_relaunch(second=%r, same directory=%s)" % relaunched[0])
done = []
session.shutdown(done=lambda: done.append(1))
adapter.run_until(lambda: done, "shutdown")
