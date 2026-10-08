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

from cefweaver.settings import Settings as _Settings

from libc.stdint cimport int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t
from libcpp cimport bool as cpp_bool
from libcpp.string cimport string

from cefweaver.cef_api cimport *
from cefweaver.cefwrapper cimport (cef_version_info, CefValueWrapper, CefWrapper, PythonQueryHandler,
                                   QueryCallbackHolder, SchemeRegistrarProxy)


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


class QueryHandler:
    """Answers the queries a page sends with ``window.cefQuery({request, persistent,
    onSuccess, onFailure})`` (CEF's message router, as in java-cef).

    Subclass it and add an instance with ``CefApp.add_query_handler()`` before
    ``initialize()``. The names of the two JavaScript functions can be changed with
    ``CefApp.set_query_functions()``. All methods run on the thread that called
    ``initialize()``, inside ``do_message_loop_work()``; exceptions go to ``sys.excepthook``
    and count as "not handled".
    """

    def on_query(self, browser, frame, query_id, request, persistent, callback):
        """A page sent a query. ``request`` is a ``str``, or ``bytes`` if the page sent an
        ``ArrayBuffer``. Return True to take the query and answer it with
        ``callback.success()`` or ``callback.failure()``, now or later (from any thread);
        return False to leave it to the next handler. If no handler takes it, the page's
        ``onFailure`` gets the error code -1."""
        return False

    def on_query_canceled(self, browser, frame, query_id):
        """The page canceled a query this handler took (``cefQueryCancel``), left the page,
        or went away, or the handler was removed. ``callback`` answers nothing any more."""


cdef class QueryCallback:
    """The answer to one query, given to ``QueryHandler.on_query()``. It can be used from
    any thread. A query is answered once (a persistent one many times, until it fails or
    is canceled); the methods return whether the answer was sent. A callback that is
    dropped without an answer fails the query (error code -1)."""

    cdef CefRefPtr[QueryCallbackHolder] _holder

    def __dealloc__(self):
        if _cef_was_shut_down:
            _g_forget(<void*>&self._holder)

    def __init__(self):
        raise TypeError("QueryCallback objects are created by CEF")

    def success(self, response):
        """Answer the page's ``onSuccess`` with a ``str``, or with ``bytes`` (an
        ``ArrayBuffer`` in the page)."""
        cdef string text
        cdef bytes data
        cdef const char* raw
        cdef size_t size
        cdef bint done
        if isinstance(response, str):
            text = _utf8(response)
            with nogil:
                done = self._holder.get().Success(text)
        elif isinstance(response, (bytes, bytearray, memoryview)):
            data = bytes(response)
            raw = data
            size = len(data)
            with nogil:
                done = self._holder.get().SuccessData(<const void*>raw, size)
        else:
            raise TypeError("response must be str or bytes, not %s" % type(response).__name__)
        return done

    def failure(self, int error_code, message=""):
        """Answer the page's ``onFailure`` with an error code and a message."""
        cdef string text = _utf8(message)
        cdef bint done
        with nogil:
            done = self._holder.get().Failure(error_code, text)
        return done


cdef cpp_bool _query_on_query(void* handler, CefRefPtr[CefBrowser] browser,
                              CefRefPtr[CefFrame] frame, int64_t query_id, cpp_bool binary,
                              const void* request, size_t size, cpp_bool persistent,
                              QueryCallbackHolder* holder) noexcept with gil:
    cdef QueryCallback callback
    try:
        if binary:
            value = (<const char*>request)[:size] if size else b""
        else:
            value = (<const char*>request)[:size].decode("utf-8", "replace") if size else ""
        callback = QueryCallback.__new__(QueryCallback)
        callback._holder = CefRefPtr[QueryCallbackHolder](holder)
        return bool((<object>handler).on_query(
            _wrap_Browser(browser), _wrap_Frame(frame), query_id, value, bool(persistent),
            callback))
    except BaseException:
        _g_report()
        return False


cdef void _query_on_canceled(void* handler, CefRefPtr[CefBrowser] browser,
                             CefRefPtr[CefFrame] frame, int64_t query_id) noexcept with gil:
    try:
        (<object>handler).on_query_canceled(_wrap_Browser(browser), _wrap_Frame(frame),
                                            query_id)
    except BaseException:
        _g_report()


cdef class _QueryBridge:
    """The C++ handler that calls one QueryHandler."""

    cdef PythonQueryHandler* _ptr
    cdef public bint registered

    def __cinit__(self, handler):
        self._ptr = new PythonQueryHandler(<void*>handler, _query_on_query, _query_on_canceled)
        self.registered = False

    def __dealloc__(self):
        # The router must not keep a pointer to a deleted handler; after shutdown the
        # handler is left alone, like the other objects that CEF may still know.
        if self._ptr != NULL and not self.registered and not _cef_was_shut_down:
            del self._ptr
        self._ptr = NULL


class AppHandler:
    """Hooks into the start of the application, as java-cef's ``CefAppHandler``.

    Subclass it and give an instance to ``CefApp.set_app_handler()`` before ``initialize()``.
    The methods run on the thread that called ``initialize()``.
    """

    def on_before_command_line_processing(self, process_type, command_line):
        """The command line of the browser process (``process_type`` is ``""``, as java-cef
        calls it for the browser process only) can be changed here, before the switches of
        ``CefApp.add_command_line_switch()`` are added. ``command_line`` is a ``CommandLine``."""

    def on_register_custom_schemes(self, registrar):
        """Register custom schemes with ``registrar.add_custom_scheme(name, options)``
        (``types.SchemeOptions``). The renderer processes get the same schemes."""

    def on_context_initialized(self):
        """CEF is ready for browsers (the first browser is created right after this)."""

    def on_schedule_message_pump_work(self, delay_ms):
        """CEF wants ``do_message_loop_work()`` to run in ``delay_ms`` milliseconds (0: now); with
        ``CefApp.settings.external_message_pump = True``. Unlike the other methods this one is
        called on **any thread** of CEF, so it must only note the request and wake the event loop
        of the application, which then calls ``do_message_loop_work()`` on the thread that called
        ``initialize()``. Without the setting CEF does not ask and the application polls."""

    def on_already_running_app_relaunch(self, command_line, current_directory):
        """A second start of the application with the same user data (the same ``cache_path``)
        reached this one; ``command_line`` is the second one's. Return True if it was handled
        (False: CEF opens a new window)."""
        return False


cdef class SchemeRegistrar:
    """Registers custom schemes; given to ``AppHandler.on_register_custom_schemes()`` and valid
    only during that call."""

    cdef SchemeRegistrarProxy* _proxy

    def __init__(self):
        raise TypeError("SchemeRegistrar objects are created by CEF")

    def add_custom_scheme(self, scheme_name, int options):
        """Register a scheme. Returns False if CEF refuses it."""
        if self._proxy == NULL:
            raise RuntimeError("the registrar is valid only during on_register_custom_schemes()")
        return bool(self._proxy.Add(_utf8(scheme_name), options))


cdef void _app_on_command_line(void* handler, CefRefPtr[CefCommandLine] command_line) noexcept with gil:
    try:
        (<object>handler).on_before_command_line_processing("", _wrap_CommandLine(command_line))
    except BaseException:
        _g_report()


cdef void _app_on_schemes(void* handler, SchemeRegistrarProxy* proxy) noexcept with gil:
    cdef SchemeRegistrar registrar = SchemeRegistrar.__new__(SchemeRegistrar)
    registrar._proxy = proxy
    try:
        (<object>handler).on_register_custom_schemes(registrar)
    except BaseException:
        _g_report()
    registrar._proxy = NULL  # the registrar of CEF is gone after this call


cdef void _app_on_context(void* handler) noexcept with gil:
    try:
        (<object>handler).on_context_initialized()
    except BaseException:
        _g_report()


cdef void _app_on_schedule(void* handler, long long delay_ms) noexcept with gil:
    try:
        (<object>handler).on_schedule_message_pump_work(int(delay_ms))
    except BaseException:
        _g_report()


cdef cpp_bool _app_on_relaunch(void* handler, CefRefPtr[CefCommandLine] command_line,
                               const string& current_directory) noexcept with gil:
    try:
        return bool((<object>handler).on_already_running_app_relaunch(
            _wrap_CommandLine(command_line), current_directory.decode("utf-8", "replace")))
    except BaseException:
        _g_report()
        return False


# CEF can be initialized once per process: a second CefInitialize() after CefShutdown()
# crashes the process (segmentation fault), so it is refused here. (`_cef_was_shut_down`
# is declared in cef_api.pxi, where the library objects use it as well.)


def _cef_version_info(int entry):
    """One entry of cef_version_info(): the CEF major, minor, patch, commit, then the Chromium
    major, minor, build, patch."""
    return cef_version_info(entry)


cdef class CefApp:
    """An embedded Chromium (CEF) instance.

    Usage::

        app = CefApp()
        app.add_javascript_binding("hello", print)   # window.hello(...) in pages
        app.initialize("https://example.com")
        while app.is_running:
            app.do_message_loop_work()
        app.shutdown()

    CEF can be initialized only once per process, also after ``shutdown()``.
    """

    cdef CefWrapper* _wrapper
    cdef bint _initialized
    cdef bint _shut_down
    cdef list _callbacks  # keeps the bound callables alive: C++ holds raw pointers
    cdef object _resources  # _StaticResourceFactory, created by add_resource()
    cdef set _resource_hosts
    cdef set _switch_names  # the names given to add_command_line_switch()
    cdef dict _query_bridges  # QueryHandler -> _QueryBridge
    cdef object _client  # the client of set_client()
    cdef object _app_handler  # the AppHandler of set_app_handler()
    cdef object _settings  # the Settings (see settings.py)

    def __cinit__(self):
        self._wrapper = new CefWrapper()
        self._initialized = False
        self._shut_down = False
        self._callbacks = []
        self._resources = None
        self._resource_hosts = set()
        self._switch_names = set()
        self._query_bridges = {}
        self._client = None
        self._app_handler = None
        self._settings = _Settings()

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

    def create_browser(self, url="about:blank", offscreen=None, transparent=None,
                       request_context=None):
        """Create a further browser (java-cef's ``CefClient.createBrowser()``) and return it as a
        ``Browser``. It uses the app's client, JavaScript bindings and message router.

        ``offscreen`` and ``transparent`` (``True`` or ``False``) decide for this browser; ``None``
        takes ``CefApp.offscreen`` and ``CefApp.transparent``. ``request_context`` is a
        ``RequestContext`` for it (``None``: the global one). Call it on the thread that called
        ``initialize()``, after the first browser exists. A windowed browser gets a window of its
        own. ``load_url()`` and ``execute_javascript()`` address the first browser only; use the
        returned ``Browser``'s frames for the others. Closing the browsers ends ``is_running``."""
        cdef string value
        cdef int osr = -1
        cdef int clear = -1
        cdef CefRefPtr[CefRequestContext] context
        cdef CefRefPtr[CefBrowser] ref
        if not isinstance(url, str):
            raise TypeError("url must be a str")
        if offscreen is not None:
            if not isinstance(offscreen, bool):
                raise TypeError("offscreen must be a bool or None")
            osr = 1 if offscreen else 0
        if transparent is not None:
            if not isinstance(transparent, bool):
                raise TypeError("transparent must be a bool or None")
            clear = 1 if transparent else 0
        if request_context is not None:
            if not isinstance(request_context, RequestContext):
                raise TypeError("request_context must be a RequestContext or None")
            context = (<RequestContext>request_context)._ref
        self._require_running()
        value = _utf8(url)
        ref = self._wrapper.CreateBrowser(value, osr, clear, context)
        if not ref.get():
            raise RuntimeError("a browser can be created on the thread of initialize() once the "
                               "first browser exists")
        return _wrap_Browser(ref)

    @staticmethod
    def get_version():
        """The ``Version`` of cefweaver, CEF and Chromium; the same as ``cefweaver.get_version()``."""
        import cefweaver
        return cefweaver.get_version()

    @property
    def settings(self):
        """The ``Settings`` of CEF (java-cef's ``CefSettings``); change its fields before
        ``initialize()``, which reads them."""
        return self._settings

    @settings.setter
    def settings(self, value):
        self._require_not_initialized()
        if not isinstance(value, _Settings):
            raise TypeError("settings must be a cefweaver.Settings")
        self._settings = value

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
        self._switch_names.add(str(name).lstrip("-"))
        self._wrapper.AddCommandLineSwitch(_utf8(name), _utf8(value))

    def set_client(self, client):
        """Receive the browser events in the handlers of ``client`` (a ``Client``).

        ``client.get_load_handler()``, ``get_life_span_handler()`` and
        ``get_display_handler()`` are asked each time CEF needs the handler, and the
        handlers they return get the events (``on_load_end``, ``on_title_change``,
        ...), on the thread that called ``initialize()``, inside
        ``do_message_loop_work()``. What the wrapper does for itself (the ready flag, the
        error page, the JavaScript bindings) keeps working. ``None`` removes the client.
        """
        self._require_not_initialized()
        self._client = client
        self._wrapper.SetClient(_g_make_Client(client))

    def set_app_handler(self, handler):
        """Hooks into the start of the application (an ``AppHandler``), as java-cef's
        ``CefAppHandler``: the command line, custom schemes, the initialized context and a
        second start of the application. Before ``initialize()`` only; ``None`` removes it."""
        self._require_not_initialized()
        if handler is not None and not isinstance(handler, AppHandler):
            raise TypeError("handler must be an AppHandler, not %s" % type(handler).__name__)
        self._app_handler = handler
        if handler is None:
            self._wrapper.SetAppHooks(NULL, NULL, NULL, NULL, NULL, NULL)
        else:
            self._wrapper.SetAppHooks(<void*>handler, _app_on_command_line, _app_on_schemes,
                                      _app_on_context, _app_on_relaunch, _app_on_schedule)

    @property
    def devtools_menu(self):
        """Whether the context menu has the items "Show DevTools", "Close DevTools" and
        "Inspect Element" (off by default). It can be changed at any time and applies to
        the menus that are built afterwards. Turning it on or off changes nothing else: the
        handler of ``set_client()`` gets the same events and menu either way, and the
        items only come after what it put in the menu."""
        return bool(self._wrapper.DevToolsMenuEnabled())

    @devtools_menu.setter
    def devtools_menu(self, value):
        self._wrapper.SetDevToolsMenuEnabled(bool(value))

    def set_query_functions(self, query="cefQuery", cancel="cefQueryCancel"):
        """The names of the JavaScript functions of the message router: ``window.<query>(...)``
        sends a query and ``window.<cancel>(id)`` cancels it. They are ``cefQuery`` and
        ``cefQueryCancel`` unless changed here, before ``initialize()``."""
        for value in (query, cancel):
            if not isinstance(value, str):
                raise TypeError("the names must be str, not %s" % type(value).__name__)
            if not value.isidentifier():
                raise ValueError("%r is not a name for a JavaScript function" % (value,))
        self._require_not_initialized()
        self._wrapper.SetQueryFunctions(_utf8(query), _utf8(cancel))

    def add_query_handler(self, handler, first=False):
        """Let a ``QueryHandler`` answer the queries of pages (``window.cefQuery``).

        The pages get ``window.cefQuery`` only if a handler was added before
        ``initialize()``; after it, further handlers can be added. The handlers are asked
        in the order they were added (``first=True`` puts this one in front) until one takes
        the query."""
        if not isinstance(handler, QueryHandler):
            raise TypeError("handler must be a QueryHandler, not %s" % type(handler).__name__)
        if handler in self._query_bridges:
            raise ValueError("this handler was added already")
        if self._initialized:
            self._require_running()
            if not self._wrapper.QueryRouterExists():
                raise RuntimeError("the pages have no window.cefQuery: add the first query "
                                   "handler before initialize()")
        bridge = _QueryBridge(handler)
        if not self._wrapper.AddQueryHandler((<_QueryBridge>bridge)._ptr, bool(first)):
            raise ValueError("this handler was added already")
        (<_QueryBridge>bridge).registered = True
        self._query_bridges[handler] = bridge

    def remove_query_handler(self, handler):
        """Remove a handler. The queries it took are canceled (``on_query_canceled()`` is
        called and the page's ``onFailure`` gets -1). Returns False if it was not added."""
        bridge = self._query_bridges.pop(handler, None)
        if bridge is None:
            return False
        done = self._wrapper.RemoveQueryHandler((<_QueryBridge>bridge)._ptr)
        (<_QueryBridge>bridge).registered = False
        return bool(done)

    @property
    def offscreen(self):
        """Whether the browser is rendered offscreen (off by default): it has no window, and CEF
        draws into the buffer that ``RenderHandler.on_paint()`` of the client receives. The
        client must have a render handler (``get_view_rect()`` gives the size). Popups are
        blocked, as in java-cef. It can be changed before ``initialize()`` only."""
        return bool(self._wrapper.Offscreen())

    @offscreen.setter
    def offscreen(self, value):
        self._require_not_initialized()
        self._wrapper.SetOffscreen(bool(value))

    @property
    def transparent(self):
        """Whether an offscreen browser paints transparent pixels where the page draws nothing
        (the default; java-cef's ``isTransparent``). ``False`` paints them in the opaque
        ``settings.background_color``, white if there is none. Before ``initialize()`` only."""
        return bool(self._wrapper.Transparent())

    @transparent.setter
    def transparent(self, value):
        self._require_not_initialized()
        self._wrapper.SetTransparent(bool(value))

    @property
    def windowless_frame_rate(self):
        """Frames per second of an offscreen browser (1 to 60, 30 by default); it is the
        upper bound of the ``on_paint()`` calls. Before ``initialize()`` only."""
        return int(self._wrapper.WindowlessFrameRate())

    @windowless_frame_rate.setter
    def windowless_frame_rate(self, value):
        self._require_not_initialized()
        value = int(value)
        if not 1 <= value <= 60:
            raise ValueError("the frame rate must be from 1 to 60, not %d" % value)
        self._wrapper.SetWindowlessFrameRate(value)

    def set_request_context(self, RequestContext context):
        """Use ``context`` (see ``RequestContext.create_context()``) for the first browser, so its
        ``RequestContextHandler`` is asked about the requests of that browser. Call it from
        ``AppHandler.on_context_initialized()``, before the browser exists. Returns None."""
        if self._shut_down:
            raise RuntimeError("CEF has been shut down")
        self._wrapper.SetRequestContext(context._ref if context is not None else CefRefPtr[CefRequestContext]())

    def cancel_pending_queries(self, Browser browser=None, handler=None):
        """Cancel the pending queries of ``browser`` and/or of ``handler`` (both ``None``: all of
        them). ``QueryHandler.on_query_canceled()`` is called and the page's ``onFailure`` gets
        -1. Returns None. Call it on the thread that called ``initialize()``."""
        self._require_running()
        cdef CefRefPtr[CefBrowser] ref
        cdef PythonQueryHandler* ptr = NULL
        if handler is not None:
            bridge = self._query_bridges.get(handler)
            if bridge is None:
                return None  # a handler that was never added has no queries
            ptr = (<_QueryBridge>bridge)._ptr
        if browser is not None:
            ref = browser._ref
        self._wrapper.CancelPendingQueries(ref, ptr)

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
        """Start CEF and create the browser window (once per process).

        On Linux the browser uses X11 (XWayland on a Wayland desktop) unless
        ``ozone-platform`` (or ``ozone-platform-hint``) was given with
        ``add_command_line_switch()``: an Alloy style browser ends the process inside CEF on
        native Wayland, which Chromium would pick when ``WAYLAND_DISPLAY`` is set. Without an
        X display (``DISPLAY``) the choice is left to Chromium.
        """
        cdef string url = _utf8(start_url)
        cdef bint ok
        if self._initialized:
            raise RuntimeError("initialize() was already called")
        if self._client is not None and "disable-chrome-login-prompt" not in self._switch_names:
            # Without this switch CEF shows Chrome's own login window and never asks the
            # client's request handler for credentials; the handler gets them only if it
            # answers (it overrides get_auth_credentials).
            handler = self._client.get_request_handler()
            if (handler is not None
                    and type(handler).get_auth_credentials is not RequestHandler.get_auth_credentials):
                self._wrapper.AddCommandLineSwitch(b"disable-chrome-login-prompt", b"")
        if (sys.platform.startswith("linux") and os.environ.get("DISPLAY")
                and "ozone-platform" not in self._switch_names
                and "ozone-platform-hint" not in self._switch_names):
            self._wrapper.AddCommandLineSwitch(b"ozone-platform", b"x11")
        for name, value in self._settings._given().items():
            if isinstance(value, str):
                self._wrapper.SetStringSetting(_utf8(name), _utf8(value))
            else:
                self._wrapper.SetIntSetting(_utf8(name), int(value))
        self._settings._freeze()
        if _cef_was_shut_down:
            raise RuntimeError("CEF can be initialized only once per process, "
                               "and it was shut down already")
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
        global _cef_was_shut_down
        _cef_was_shut_down = True

    # -- browser ---------------------------------------------------------------

    def load_url(self, url):
        """Navigate to ``url``. Returns False if the browser does not exist yet."""
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


__all__ = ["CefApp", "QueryHandler", "QueryCallback", "AppHandler",
           "SchemeRegistrar"] + __generated_all__
