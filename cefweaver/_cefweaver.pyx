# cython: language_level=3
# distutils: language = c++
"""Python binding of the CEF wrapper in native/cefwrapper.

Threading and the GIL
---------------------
The wrapper runs CEF with an external message pump, so the CEF UI thread is the
Python thread that calls ``initialize()``, and every UI-thread callback (including
the JavaScript bindings below) is delivered inside ``do_message_loop_work()``.

* Calls into CEF that can block, or that run callbacks, release the GIL
  (``with nogil``). CEF's other threads (IO, ...) may need the GIL for their own
  callbacks, so holding it while waiting inside CEF could deadlock.
* Callbacks coming from CEF are ``with gil``: they may arrive from a thread that
  does not hold the GIL, and reacquiring it is harmless if it is already held.
"""

import os
import sys
from urllib.parse import urlsplit

from libc.stdint cimport int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t
from libcpp cimport bool as cpp_bool
from libcpp.string cimport string

from cefweaver.cef_api cimport *
from cefweaver.cefwrapper cimport CefValueWrapper, CefWrapper


cdef bytes _utf8(object value):
    """str, bytes or os.PathLike -> UTF-8 bytes (converted to std::string by Cython)."""
    if hasattr(value, "__fspath__"):
        value = os.fspath(value)
    if isinstance(value, bytes):
        return <bytes>value
    if not isinstance(value, str):
        raise TypeError(f"expected str, bytes or os.PathLike, not {type(value).__name__}")
    return (<str>value).encode("utf-8")


cdef object _to_python(CefValueWrapper* value):
    cdef int kind = value.Type
    if kind == 0:
        return value.IntValue
    if kind == 1:
        return bool(value.BoolValue)
    if kind == 2:
        return value.DoubleValue
    if kind == 3:
        return (<bytes>value.StringValue).decode("utf-8", "replace")
    return None  # a JavaScript type the wrapper does not convert


cdef void _dispatch(void* callback, int args_size, CefValueWrapper* args) noexcept with gil:
    """Called by CEF for a JavaScript -> Python binding.

    Nothing may propagate into C++, so every exception goes to sys.excepthook.
    """
    cdef int i
    try:
        py_args = []
        for i in range(args_size):
            py_args.append(_to_python(&args[i]))
        (<object>callback)(*py_args)
    except BaseException:
        try:
            sys.excepthook(*sys.exc_info())
        except BaseException:
            pass


# The wrappers generated from the CEF headers by tools/gen/generate.py: Request, Response,
# ResourceHandler, SchemeHandlerFactory, register_scheme_handler_factory(), ...
include "cef_api.pxi"


class _StaticResource(ResourceHandler):
    """Serves one in-memory resource (used by CefApp.add_resource)."""

    def __init__(self, data, mime_type, status, headers):
        self._data = data
        self._mime_type = mime_type
        self._status = status
        self._headers = headers
        self._offset = 0

    def open(self, request, callback):
        return True, True  # handled, and the response can be read right away

    def get_response_headers(self, response):
        response.set_mime_type(self._mime_type)
        response.set_status(self._status)
        for name, value in self._headers.items():
            response.set_header_by_name(name, value, True)
        return len(self._data), ""

    def read(self, data_out, callback):
        count = min(len(data_out), len(self._data) - self._offset)
        if count <= 0:
            return False, 0  # the end of the resource
        data_out[:count] = self._data[self._offset:self._offset + count]
        self._offset += count
        return True, count

    def cancel(self):
        pass


def _resource_key(url):
    parts = urlsplit(url)
    return "%s://%s%s" % (parts.scheme, parts.netloc, parts.path or "/")


class _StaticResourceFactory(SchemeHandlerFactory):
    def __init__(self):
        self.resources = {}

    def create(self, browser, frame, scheme_name, request):
        resource = self.resources.get(_resource_key(request.get_url()))
        return _StaticResource(*resource) if resource is not None else None


cdef class CefApp:
    """An embedded Chromium (CEF) instance.

    Usage::

        app = CefApp()
        app.add_javascript_binding("hello", print)   # window.hello(...) in pages
        app.initialize("https://example.com")
        while app.is_running:
            app.do_message_loop_work()
        app.shutdown()

    Only one instance can be initialized per process.
    """

    cdef CefWrapper* _wrapper
    cdef bint _initialized
    cdef bint _shut_down
    cdef list _callbacks  # keeps the bound callables alive: C++ holds raw pointers
    cdef object _resources  # _StaticResourceFactory, created by add_resource()
    cdef set _resource_hosts

    def __cinit__(self):
        self._wrapper = new CefWrapper()
        self._initialized = False
        self._shut_down = False
        self._callbacks = []
        self._resources = None
        self._resource_hosts = set()

    def __dealloc__(self):
        # While CEF is running, the wrapper's CefApp must outlive CefShutdown().
        if self._wrapper != NULL and (not self._initialized or self._shut_down):
            del self._wrapper
        self._wrapper = NULL

    cdef _require_not_initialized(self):
        if self._initialized:
            raise RuntimeError("this must be done before initialize()")

    cdef _require_running(self):
        if not self._initialized:
            raise RuntimeError("initialize() has not been called")
        if self._shut_down:
            raise RuntimeError("CEF has been shut down")

    # -- configuration (before initialize) ------------------------------------

    def set_subprocess_path(self, path):
        """Path of the cefsubprocess executable."""
        self._require_not_initialized()
        self._wrapper.SetCustomCefSubprocessPath(_utf8(path))

    def set_cache_path(self, path):
        """Directory for the browser cache and profile data."""
        self._require_not_initialized()
        self._wrapper.SetCustomCefCachePath(_utf8(path))

    def set_resources_path(self, path):
        """Forward CefSettings.resources_dir_path (and locales/ below it).

        Optional. On Linux, CEF looks for icudtl.dat next to libcef.so regardless
        of this setting, so deploy the runtime files together with libcef.so.
        """
        self._require_not_initialized()
        self._wrapper.SetCustomCefResourcesPath(_utf8(path))

    def add_command_line_switch(self, name, value=""):
        """Add a Chromium command line switch, e.g. ``"disable-gpu"`` or
        ``("renderer-cmd-prefix", "gdb --args")``. Without a value it is a bare switch."""
        self._require_not_initialized()
        self._wrapper.AddCommandLineSwitch(_utf8(name), _utf8(value))

    def add_javascript_binding(self, name, callback):
        """Expose ``window.<name>(...)`` to pages; it calls ``callback(*args)``.

        Arguments are converted to int, bool, float or str. The callback runs
        inside ``do_message_loop_work()`` on the thread that called
        ``initialize()``. Exceptions are reported through ``sys.excepthook``.
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._require_not_initialized()
        self._callbacks.append(callback)
        self._wrapper.AddJavascriptPythonBinding(_utf8(name), _dispatch, <void*>callback)

    # -- lifecycle -------------------------------------------------------------

    def initialize(self, start_url="about:blank"):
        """Start CEF and create the browser window (once per process)."""
        cdef string url = _utf8(start_url)
        cdef bint ok
        if self._initialized:
            raise RuntimeError("initialize() was already called")
        with nogil:
            ok = self._wrapper.InitCefSimple(url)
        if not ok:
            raise RuntimeError("CefInitialize() failed")
        self._initialized = True

    def do_message_loop_work(self):
        """Run one iteration of the CEF message loop; call it regularly."""
        self._require_running()
        with nogil:
            self._wrapper.DoCefMessageLoopWork()

    def shutdown(self):
        """Shut CEF down. Does nothing if CEF is not running."""
        if not self._initialized or self._shut_down:
            return
        with nogil:
            self._wrapper.ShutdownCefSimple()
        self._shut_down = True

    # -- browser ---------------------------------------------------------------

    def load_url(self, url):
        """Navigate to ``url``. Returns False if the browser does not exist yet
        (it is created during the first calls of ``do_message_loop_work()``)."""
        cdef string value = _utf8(url)
        cdef bint done
        self._require_running()
        with nogil:
            done = self._wrapper.LoadUrl(value)
        return done

    def execute_javascript(self, code):
        """Run JavaScript in the main frame. Returns False if it was not run
        because there is no browser yet or the page is still loading."""
        cdef string value = _utf8(code)
        cdef bint done
        self._require_running()
        with nogil:
            done = self._wrapper.ExecuteJavascript(value)
        return done

    def add_resource(self, url, content, mime_type="text/html", headers=None, int status=200):
        """Serve ``content`` for ``url`` (http or https) without a network access.

        Call it after ``initialize()`` and before the page is loaded. The query
        and fragment of a requested URL are ignored.
        """
        self._require_running()
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            raise ValueError("expected an absolute http or https URL, not %r" % (url,))
        if isinstance(content, str):
            content = content.encode("utf-8")
        if self._resources is None:
            self._resources = _StaticResourceFactory()
        self._resources.resources[_resource_key(url)] = (
            bytes(content), mime_type, status, dict(headers or {}))
        host = (parts.scheme, parts.hostname)
        if host not in self._resource_hosts:
            if not register_scheme_handler_factory(parts.scheme, parts.hostname, self._resources):
                raise RuntimeError("CEF did not accept the scheme handler for %s://%s" % host)
            self._resource_hosts.add(host)

    # -- state -------------------------------------------------------------------

    @property
    def is_running(self):
        return self._initialized and not self._shut_down and self._wrapper.IsRunning()

    @property
    def is_ready_to_execute_javascript(self):
        return (self._initialized and not self._shut_down
                and self._wrapper.IsReadyToExecuteJavascript())


__all__ = ["CefApp"] + __generated_all__
