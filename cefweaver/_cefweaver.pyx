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

from libc.stdint cimport int8_t, uint8_t, int16_t, uint16_t, int32_t, uint32_t, int64_t, uint64_t, uintptr_t
from libcpp cimport bool as cpp_bool
from libcpp.string cimport string

from cefweaver.cef_api cimport *
from cefweaver.cefwrapper cimport (CefWeaverLoadRuntime, cef_version_info, CefValueWrapper, CefWrapper, PythonQueryHandler,
                                   QueryCallbackHolder, SchemeRegistrarProxy, PreferenceRegistrarProxy,
                                   CefWeaverShowDevTools, CefWeaverSharedMemoryRead, CefWeaverSharedBuilderWrite)


cdef int64_t _check_parent_view(object value) except -1:
    """A parent view: the address of an NSView, an int (macOS only)."""
    if sys.platform != "darwin":
        raise NotImplementedError("parent_view is implemented on macOS only")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError("parent_view must be the address of an NSView (a non-negative int)")
    return <int64_t>value


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


# On macOS libcef is loaded here, before the first CEF call (the generated code below makes
# one while it is imported).
if not CefWeaverLoadRuntime():
    raise ImportError("the CEF runtime could not be loaded (see the message above)")

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
    """Base class for handlers of the queries a page sends with ``window.cefQuery``.

    A page sends a query with ``window.cefQuery({request, persistent, onSuccess,
    onFailure})`` (CEF's message router, as in java-cef). Subclass this class and
    register an instance with :meth:`~cefweaver.CefApp.add_query_handler`. The names of
    the two JavaScript functions can be changed with
    :meth:`~cefweaver.CefApp.set_query_functions`.

    Note:
        All methods run on the thread that called :meth:`~cefweaver.CefApp.initialize`,
        inside :meth:`~cefweaver.CefApp.do_message_loop_work`. An exception goes to
        ``sys.excepthook`` and counts as "not handled".
    """

    def on_query(self, browser, frame, query_id, request, persistent, callback):
        """Handle a query sent by a page.

        Args:
            browser (~cefweaver.Browser): The browser that holds the page.
            frame (~cefweaver.Frame): The frame that sent the query.
            query_id (int): The identifier of the query.
            request (str | bytes): The request; ``bytes`` if the page sent an ``ArrayBuffer``.
            persistent (bool): Whether the query stays open for further answers.
            callback (~cefweaver.QueryCallback): Answers the query.

        Returns:
            bool: ``True`` to take the query and answer it with ``callback``, now or later
            (from any thread); ``False`` to leave it to the next handler. If no handler
            takes it, the ``onFailure`` of the page gets the error code -1. The default
            implementation returns ``False``.
        """
        return False

    def on_query_canceled(self, browser, frame, query_id):
        """Handle the end of a query this handler took.

        Called when the page canceled the query (``cefQueryCancel``), left the page or went
        away, or when the handler was removed. The callback of the query answers nothing any
        more.

        Args:
            browser (~cefweaver.Browser): The browser that held the page.
            frame (~cefweaver.Frame): The frame that sent the query.
            query_id (int): The identifier of the query.
        """


cdef class QueryCallback:
    """The answer to one query, given to :meth:`QueryHandler.on_query`.

    Instances are created by CEF; constructing one raises ``TypeError``. A query is
    answered once (a persistent one many times, until it fails or is canceled). A
    callback that is dropped without an answer fails the query with the error code -1.

    Note:
        It can be used from any thread.
    """

    cdef CefRefPtr[QueryCallbackHolder] _holder

    def __dealloc__(self):
        if _cef_was_shut_down:
            _g_forget(<void*>&self._holder)

    def __init__(self):
        raise TypeError("QueryCallback objects are created by CEF")

    def success(self, response):
        """Answer the ``onSuccess`` of the page.

        Args:
            response (str | bytes | bytearray | memoryview): The response; the page gets a
                string for ``str`` and an ``ArrayBuffer`` for the other types.

        Returns:
            bool: Whether the answer was sent.

        Raises:
            TypeError: If ``response`` is none of the accepted types.
        """
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
        """Answer the ``onFailure`` of the page.

        Args:
            error_code (int): The error code.
            message (str, optional): The error message. Defaults to ``""``.

        Returns:
            bool: Whether the answer was sent.
        """
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
    """Base class for hooks into the start of the application.

    Corresponds to java-cef's ``CefAppHandler``. Subclass it and give an instance to
    :meth:`~cefweaver.CefApp.set_app_handler`. An exception raised by a method goes to
    ``sys.excepthook``.

    Note:
        The methods run on the thread that called :meth:`~cefweaver.CefApp.initialize`,
        except :meth:`on_schedule_message_pump_work`.
    """

    def on_before_command_line_processing(self, process_type, command_line):
        """Change the command line of the browser process.

        Called before the switches of :meth:`~cefweaver.CefApp.add_command_line_switch` are
        added.

        Args:
            process_type (str): Always ``""`` (the browser process).
            command_line (~cefweaver.CommandLine): The command line, which may be changed.
        """

    def on_register_custom_schemes(self, registrar):
        """Register custom schemes.

        The renderer processes get the same schemes.

        Args:
            registrar (~cefweaver.SchemeRegistrar): Registers a scheme with
                ``add_custom_scheme(name, options)``, where ``options`` combines
                :class:`~cefweaver.types.SchemeOptions` values. Valid during this call only.
        """

    def on_before_child_process_launch(self, command_line):
        """Change the command line of a child process before it starts.

        Called for the renderer, GPU and utility processes, after the switches of cefweaver
        itself (the custom schemes, the JavaScript bridge) were added.

        Args:
            command_line (~cefweaver.CommandLine): The command line, which may be changed.
                ``get_switch_value("type")`` gives the kind of process.
        """

    def on_register_custom_preferences(self, type, registrar):
        """Register preferences of the application.

        Args:
            type (~cefweaver.types.PreferencesType): ``GLOBAL`` (called once, for the global
                preferences) or ``REQUEST_CONTEXT`` (called for each request context).
            registrar (~cefweaver.PreferenceRegistrar): Registers a preference with
                ``add_preference(name, default_value)``. Valid during this call only.
        """

    def on_context_initialized(self):
        """Handle the initialization of the CEF context.

        The first browser is created right after this call.
        """

    def on_schedule_message_pump_work(self, delay_ms):
        """Handle CEF's request to run the message loop later.

        Called only when ``Settings.external_message_pump`` is ``True``. An implementation
        should note the request and wake the event loop of the application, which then calls
        :meth:`~cefweaver.CefApp.do_message_loop_work`.

        Args:
            delay_ms (int): The delay in milliseconds; 0 means now.

        Note:
            Unlike the other methods, this one is called on any thread of CEF.
        """

    def on_already_running_app_relaunch(self, command_line, current_directory):
        """Handle a second start of the application with the same user data.

        Called when a second process with the same ``cache_path`` reaches this one.

        Args:
            command_line (~cefweaver.CommandLine): The command line of the second start.
            current_directory (str): The current directory of the second start.

        Returns:
            bool: ``True`` if the start was handled; ``False`` to let CEF open a new window.
            The default implementation returns ``False``.
        """
        return False


cdef class SchemeRegistrar:
    """Registers custom schemes.

    Instances are created by CEF and given to
    :meth:`AppHandler.on_register_custom_schemes`; constructing one raises ``TypeError``.

    Note:
        Valid during that call only.
    """

    cdef SchemeRegistrarProxy* _proxy

    def __init__(self):
        raise TypeError("SchemeRegistrar objects are created by CEF")

    def add_custom_scheme(self, scheme_name, int options):
        """Register a custom scheme.

        Args:
            scheme_name (str): The name of the scheme.
            options (int): A combination of :class:`~cefweaver.types.SchemeOptions` values.

        Returns:
            bool: ``False`` if CEF refuses the scheme.

        Raises:
            RuntimeError: If called outside :meth:`AppHandler.on_register_custom_schemes`.
        """
        if self._proxy == NULL:
            raise RuntimeError("the registrar is valid only during on_register_custom_schemes()")
        return bool(self._proxy.Add(_utf8(scheme_name), options))


cdef class PreferenceRegistrar:
    """Registers preferences of the application.

    Instances are created by CEF and given to
    :meth:`AppHandler.on_register_custom_preferences`; constructing one raises
    ``TypeError``.

    Note:
        Valid during that call only.
    """

    cdef PreferenceRegistrarProxy* _proxy

    def __init__(self):
        raise TypeError("PreferenceRegistrar objects are created by CEF")

    def add_preference(self, name, Value default_value not None):
        """Register a preference with its default value.

        Args:
            name (str): The name of the preference.
            default_value (~cefweaver.Value): The default value; not ``None``.

        Returns:
            bool: ``False`` if CEF refuses the preference (the name is taken, or the value
            has a type that a preference cannot have).

        Raises:
            RuntimeError: If called outside :meth:`AppHandler.on_register_custom_preferences`.
        """
        if self._proxy == NULL:
            raise RuntimeError("the registrar is valid only during on_register_custom_preferences()")
        return bool(self._proxy.Add(_utf8(name), default_value._ref))


cdef void _app_on_child_launch(void* handler, CefRefPtr[CefCommandLine] command_line) noexcept with gil:
    try:
        (<object>handler).on_before_child_process_launch(_wrap_CommandLine(command_line))
    except BaseException:
        _g_report()


cdef void _app_on_preferences(void* handler, int type, PreferenceRegistrarProxy* proxy) noexcept with gil:
    cdef PreferenceRegistrar registrar = PreferenceRegistrar.__new__(PreferenceRegistrar)
    registrar._proxy = proxy
    try:
        (<object>handler).on_register_custom_preferences(_g_enum(_types.PreferencesType, type), registrar)
    except BaseException:
        _g_report()
    registrar._proxy = NULL  # the registrar of CEF is gone after this call


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

    The constructor takes no arguments. Configure the instance, call :meth:`initialize`,
    and run :meth:`do_message_loop_work` regularly until :attr:`is_running` is false.

    Example:
        ::

            app = CefApp()
            app.add_javascript_binding("hello", print)   # window.hello(...) in pages
            app.initialize("https://example.com")
            while app.is_running:
                app.do_message_loop_work()
            app.shutdown()

    Note:
        CEF can be initialized only once per process, also after :meth:`shutdown`. The
        thread that calls :meth:`initialize` is the CEF UI thread, and every UI-thread
        callback runs inside :meth:`do_message_loop_work`.
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
    cdef object _browser_settings  # the BrowserSettings of the browsers (types.py)

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
        self._browser_settings = _types.BrowserSettings()

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
                       request_context=None, settings=None, shared_texture=None, parent_view=None):
        """Create a further browser.

        The browser uses the client, JavaScript bindings and message router of the app
        (java-cef's ``CefClient.createBrowser()``). A windowed browser gets a window of its
        own. :meth:`load_url` and :meth:`execute_javascript` address the first browser only;
        use the frames of the returned browser for the others. Closing the browsers ends
        :attr:`is_running`.

        Args:
            url (str, optional): The URL to load. Defaults to ``"about:blank"``.
            offscreen (bool, optional): Whether this browser is offscreen; ``None`` takes
                :attr:`offscreen`.
            transparent (bool, optional): Whether this browser is transparent; ``None`` takes
                :attr:`transparent`.
            request_context (~cefweaver.RequestContext, optional): The request context of
                the browser; ``None`` means the global one.
            settings (~cefweaver.types.BrowserSettings, optional): The settings of this
                browser; ``None`` takes :attr:`browser_settings`.
            shared_texture (bool, optional): Whether this browser gives shared textures;
                ``None`` takes :attr:`shared_texture`.
            parent_view (int, optional): macOS only. The address of the ``NSView`` that this
                windowed browser becomes a child of; ``0`` means a window of its own;
                ``None`` takes :attr:`parent_view`.

        Returns:
            ~cefweaver.Browser: The new browser.

        Raises:
            TypeError: If an argument has the wrong type.
            NotImplementedError: If ``parent_view`` is given on a platform other than macOS.
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down, or if
                the browser cannot be created.

        Note:
            Call it on the thread that called :meth:`initialize`, after the first browser
            exists.
        """
        cdef string value
        cdef int osr = -1
        cdef int clear = -1
        cdef int shared = -1
        cdef CefRefPtr[CefRequestContext] context
        cdef CefRefPtr[CefBrowser] ref
        cdef CefBrowserSettings cpp_settings
        cdef const CefBrowserSettings* settings_ptr = NULL
        cdef int64_t parent = -1
        if parent_view is not None:
            parent = _check_parent_view(parent_view)
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
        if shared_texture is not None:
            if not isinstance(shared_texture, bool):
                raise TypeError("shared_texture must be a bool or None")
            shared = 1 if shared_texture else 0
        if request_context is not None:
            if not isinstance(request_context, RequestContext):
                raise TypeError("request_context must be a RequestContext or None")
            context = (<RequestContext>request_context)._ref
        if settings is not None:
            if not isinstance(settings, _types.BrowserSettings):
                raise TypeError("settings must be a types.BrowserSettings or None")
            _g_to_BrowserSettings(settings, &cpp_settings)
            settings_ptr = &cpp_settings
        self._require_running()
        value = _utf8(url)
        ref = self._wrapper.CreateBrowser(value, osr, clear, context, settings_ptr, shared, parent)
        if not ref.get():
            raise RuntimeError("a browser can be created on the thread of initialize() once the "
                               "first browser exists")
        return _wrap_Browser(ref)

    @staticmethod
    def get_version():
        """Return the versions of cefweaver, CEF and Chromium.

        Returns:
            ~cefweaver.Version: The same value as :func:`cefweaver.get_version`.
        """
        import cefweaver
        return cefweaver.get_version()

    @property
    def browser_settings(self):
        """~cefweaver.types.BrowserSettings: The settings of the browsers.

        They apply to the first browser and to the browsers that :meth:`create_browser` makes
        without settings of their own. A field left at its default is CEF's choice.

        Note:
            Assigning is possible before :meth:`initialize` only (``RuntimeError`` after it;
            ``TypeError`` for another type).
        """
        return self._browser_settings

    @browser_settings.setter
    def browser_settings(self, value):
        self._require_not_initialized()
        if not isinstance(value, _types.BrowserSettings):
            raise TypeError("browser_settings must be a types.BrowserSettings")
        self._browser_settings = value

    @property
    def settings(self):
        """~cefweaver.Settings: The settings of CEF (java-cef's ``CefSettings``).

        :meth:`initialize` reads them and freezes them.

        Note:
            Assigning is possible before :meth:`initialize` only (``RuntimeError`` after it;
            ``TypeError`` for another type).
        """
        return self._settings

    @settings.setter
    def settings(self, value):
        self._require_not_initialized()
        if not isinstance(value, _Settings):
            raise TypeError("settings must be a cefweaver.Settings")
        self._settings = value

    def set_subprocess_path(self, path):
        """Set the path of the ``cefsubprocess`` executable.

        Args:
            path (str | bytes | os.PathLike): The path.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        self._require_not_initialized()
        self._wrapper.SetCustomCefSubprocessPath(_utf8(path))

    def set_cache_path(self, path):
        """Set the directory for the browser cache and profile data.

        Args:
            path (str | bytes | os.PathLike): The directory.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        self._require_not_initialized()
        self._wrapper.SetCustomCefCachePath(_utf8(path))

    def set_resources_path(self, path):
        """Set ``CefSettings.resources_dir_path`` (``locales/`` is looked up below it).

        Optional.

        Args:
            path (str | bytes | os.PathLike): The directory.

        Raises:
            RuntimeError: If called after :meth:`initialize`.

        Note:
            On Linux, CEF looks for ``icudtl.dat`` next to ``libcef.so`` regardless of this
            setting, so the runtime files must be deployed together with ``libcef.so``.
        """
        self._require_not_initialized()
        self._wrapper.SetCustomCefResourcesPath(_utf8(path))

    def add_command_line_switch(self, name, value=""):
        """Add a Chromium command line switch.

        Args:
            name (str): The switch, for example ``"disable-gpu"``.
            value (str, optional): The value of the switch. Defaults to ``""``, which adds a
                bare switch.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        self._require_not_initialized()
        self._switch_names.add(str(name).lstrip("-"))
        self._wrapper.AddCommandLineSwitch(_utf8(name), _utf8(value))

    def set_client(self, client):
        """Set the client that receives the browser events.

        ``client.get_load_handler()``, ``get_life_span_handler()`` and
        ``get_display_handler()`` are asked each time CEF needs the handler, and the handlers
        they return get the events (``on_load_end``, ``on_title_change``, ...). What the
        wrapper does for itself (the ready flag, the error page, the JavaScript bindings)
        keeps working.

        Args:
            client (~cefweaver.Client | None): The client; ``None`` removes it.

        Raises:
            RuntimeError: If called after :meth:`initialize`.

        Note:
            The events arrive on the thread that called :meth:`initialize`, inside
            :meth:`do_message_loop_work`.
        """
        self._require_not_initialized()
        self._client = client
        self._wrapper.SetClient(_g_make_Client(client))

    def set_app_handler(self, handler):
        """Set the hooks into the start of the application.

        Args:
            handler (AppHandler | None): The handler; ``None`` removes it.

        Raises:
            TypeError: If ``handler`` is neither an :class:`AppHandler` nor ``None``.
            RuntimeError: If called after :meth:`initialize`.
        """
        self._require_not_initialized()
        if handler is not None and not isinstance(handler, AppHandler):
            raise TypeError("handler must be an AppHandler, not %s" % type(handler).__name__)
        self._app_handler = handler
        if handler is None:
            self._wrapper.SetAppHooks(NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL)
        else:
            self._wrapper.SetAppHooks(<void*>handler, _app_on_command_line, _app_on_schemes,
                                      _app_on_context, _app_on_relaunch, _app_on_schedule,
                                      _app_on_child_launch, _app_on_preferences)

    def enable_renderer_events(self, int stack_size=10):
        """Make the renderer processes report what happens in them.

        The browser process gets an uncaught JavaScript error, the node that has the focus,
        and the V8 contexts that are created and released, as process messages that
        :class:`cefweaver.RendererEvents` decodes.

        Args:
            stack_size (int, optional): The value for
                ``Settings.uncaught_exception_stack_size`` (the frames of the stack of an
                error; CEF sends no error with 0), unless the program set that setting.
                Defaults to 10.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        self._require_not_initialized()
        if self._settings.uncaught_exception_stack_size is None:
            self._settings.uncaught_exception_stack_size = stack_size
        self._wrapper.SetRendererEvents(True)

    @property
    def devtools_menu(self):
        """bool: Whether the context menu has "Show DevTools", "Close DevTools" and "Inspect Element".

        Off by default. It can be changed at any time and applies to the menus built
        afterwards. The items come after what the handler of :meth:`set_client` put in the
        menu; the handler gets the same events either way.
        """
        return bool(self._wrapper.DevToolsMenuEnabled())

    @devtools_menu.setter
    def devtools_menu(self, value):
        self._wrapper.SetDevToolsMenuEnabled(bool(value))

    def set_query_functions(self, query="cefQuery", cancel="cefQueryCancel"):
        """Set the names of the JavaScript functions of the message router.

        ``window.<query>(...)`` sends a query and ``window.<cancel>(id)`` cancels it.

        Args:
            query (str, optional): The name of the query function. Defaults to
                ``"cefQuery"``.
            cancel (str, optional): The name of the cancel function. Defaults to
                ``"cefQueryCancel"``.

        Raises:
            TypeError: If a name is not a ``str``.
            ValueError: If a name is not a valid JavaScript identifier.
            RuntimeError: If called after :meth:`initialize`.
        """
        for value in (query, cancel):
            if not isinstance(value, str):
                raise TypeError("the names must be str, not %s" % type(value).__name__)
            if not value.isidentifier():
                raise ValueError("%r is not a name for a JavaScript function" % (value,))
        self._require_not_initialized()
        self._wrapper.SetQueryFunctions(_utf8(query), _utf8(cancel))

    def _set_bridge_names(self, names):
        """The names ``JavascriptBridge`` exposes, a JSON array (``cefweaver/bridge.py``)."""
        self._require_not_initialized()
        self._wrapper.SetBridgeNames(_utf8(names))

    def add_query_handler(self, handler, first=False):
        """Add a handler for the queries of pages.

        The handlers are asked in the order they were added until one takes the query.

        Args:
            handler (QueryHandler): The handler.
            first (bool, optional): Whether to put the handler in front of the others.
                Defaults to ``False``.

        Raises:
            TypeError: If ``handler`` is not a :class:`QueryHandler`.
            ValueError: If ``handler`` was added already.
            RuntimeError: If called after :meth:`initialize` without a handler added before
                it (the pages then have no ``window.cefQuery``), or after CEF was shut down.
        """
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
        """Remove a query handler.

        The queries it took are canceled: :meth:`QueryHandler.on_query_canceled` is called
        and the ``onFailure`` of the page gets -1.

        Args:
            handler (QueryHandler): The handler.

        Returns:
            bool: ``False`` if the handler was not added.
        """
        bridge = self._query_bridges.pop(handler, None)
        if bridge is None:
            return False
        done = self._wrapper.RemoveQueryHandler((<_QueryBridge>bridge)._ptr)
        (<_QueryBridge>bridge).registered = False
        return bool(done)

    @property
    def parent_view(self):
        """int: macOS only. The address of the ``NSView`` that the windowed browser becomes a child of.

        ``0`` (the default) lets CEF make a window of its own. The browser fills the view and
        follows its size. The view is the content view of a Cocoa window, of SwiftUI's
        ``NSViewRepresentable`` or of a toolkit (Qt's ``winId()`` is one). It is not used for
        an offscreen browser.

        Note:
            Assigning is possible before :meth:`initialize` only, and the view must exist
            then, on the main thread. It raises ``NotImplementedError`` off macOS and
            ``TypeError`` for a value that is not a non-negative ``int``.
        """
        return int(self._wrapper.ParentView())

    @parent_view.setter
    def parent_view(self, value):
        self._require_not_initialized()
        self._wrapper.SetParentView(<uintptr_t>_check_parent_view(value))

    @property
    def offscreen(self):
        """bool: Whether the browser is rendered offscreen.

        Off by default. An offscreen browser has no window; CEF draws into the buffer that
        ``RenderHandler.on_paint()`` of the client receives, and the render handler of the
        client must give the size with ``get_view_rect()``. Popups are blocked, as in
        java-cef.

        Note:
            Assigning is possible before :meth:`initialize` only.
        """
        return bool(self._wrapper.Offscreen())

    @offscreen.setter
    def offscreen(self, value):
        self._require_not_initialized()
        self._wrapper.SetOffscreen(bool(value))

    @property
    def transparent(self):
        """bool: Whether an offscreen browser paints transparent pixels where the page draws nothing.

        On by default (java-cef's ``isTransparent``). ``False`` paints them in the opaque
        ``Settings.background_color``, white if there is none.

        Note:
            Assigning is possible before :meth:`initialize` only.
        """
        return bool(self._wrapper.Transparent())

    @transparent.setter
    def transparent(self, value):
        self._require_not_initialized()
        self._wrapper.SetTransparent(bool(value))

    @property
    def shared_texture(self):
        """bool: Whether an offscreen browser gives shared textures instead of pixels.

        If ``True``, CEF's shared textures (GPU memory; dmabuf file descriptors on Linux) go
        to ``RenderHandler.on_accelerated_paint()`` instead of pixels to ``on_paint()``. Off
        by default. Needs a GPU.

        Note:
            Assigning is possible before :meth:`initialize` only (``TypeError`` for a value
            that is not a ``bool``).
        """
        return bool(self._wrapper.SharedTexture())

    @shared_texture.setter
    def shared_texture(self, value):
        self._require_not_initialized()
        if not isinstance(value, bool):
            raise TypeError("shared_texture must be a bool")
        self._wrapper.SetSharedTexture(value)

    @property
    def windowless_frame_rate(self):
        """int: The frames per second of an offscreen browser, from 1 to 60.

        Defaults to 30. It is the upper bound of the ``on_paint()`` calls.

        Note:
            Assigning is possible before :meth:`initialize` only (``ValueError`` outside
            1 to 60).
        """
        return int(self._wrapper.WindowlessFrameRate())

    @windowless_frame_rate.setter
    def windowless_frame_rate(self, value):
        self._require_not_initialized()
        value = int(value)
        if not 1 <= value <= 60:
            raise ValueError("the frame rate must be from 1 to 60, not %d" % value)
        self._wrapper.SetWindowlessFrameRate(value)

    def set_request_context(self, RequestContext context):
        """Set the request context of the first browser.

        Its ``RequestContextHandler`` is asked about the requests of that browser.

        Args:
            context (~cefweaver.RequestContext | None): A context, for example from
                ``RequestContext.create_context()``; ``None`` clears it.

        Raises:
            RuntimeError: If CEF was shut down.

        Note:
            Call it from :meth:`AppHandler.on_context_initialized`, before the browser exists.
        """
        if self._shut_down:
            raise RuntimeError("CEF has been shut down")
        self._wrapper.SetRequestContext(context._ref if context is not None else CefRefPtr[CefRequestContext]())

    def cancel_pending_queries(self, Browser browser=None, handler=None):
        """Cancel pending queries.

        :meth:`QueryHandler.on_query_canceled` is called and the ``onFailure`` of the page
        gets -1.

        Args:
            browser (~cefweaver.Browser, optional): Cancel the queries of this browser.
            handler (QueryHandler, optional): Cancel the queries of this handler. With neither
                argument all pending queries are canceled.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.

        Note:
            Call it on the thread that called :meth:`initialize`.
        """
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
        """Expose a Python callable to pages as ``window.<name>(...)``.

        The arguments of the call that are ``int``, ``bool``, ``float`` or ``str`` are passed
        on; an argument of another type (``null``, an array, an object) is left out, so the
        callable receives fewer arguments. An exception raised by the callable goes to
        ``sys.excepthook``.

        Args:
            name (str): The name of the JavaScript function.
            callback (Callable[..., Any]): Called with the converted arguments.

        Raises:
            TypeError: If ``callback`` is not callable.
            RuntimeError: If called after :meth:`initialize`.

        Note:
            The callable runs inside :meth:`do_message_loop_work` on the thread that called
            :meth:`initialize`.
        """
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._require_not_initialized()
        self._callbacks.append(callback)
        self._wrapper.AddJavascriptPythonBinding(_utf8(name), _dispatch, <void*>callback)

    # -- lifecycle -------------------------------------------------------------

    def initialize(self, start_url="about:blank"):
        """Start CEF and create the first browser.

        If ``start_url`` is ``None`` CEF starts without a first browser: the application makes
        its own (a Views ``BrowserView`` in a ``Window``, :meth:`create_browser`), and
        :attr:`is_running` stays true until :meth:`shutdown`. The first browser, if any, is
        created inside this call and its handlers run before it returns.

        On Linux with ``DISPLAY`` set, the browser uses X11 (XWayland on a Wayland desktop)
        unless ``ozone-platform`` or ``ozone-platform-hint`` was given with
        :meth:`add_command_line_switch`. If the request handler of the client overrides
        ``get_auth_credentials``, the switch ``disable-chrome-login-prompt`` is added (unless
        given) so that the handler is asked for credentials.

        Args:
            start_url (str | None, optional): The URL of the first browser. Defaults to
                ``"about:blank"``.

        Raises:
            RuntimeError: If it was called already, if CEF was shut down earlier in this
                process, or if ``CefInitialize()`` fails.
        """
        cdef string url = _utf8("about:blank" if start_url is None else start_url)
        cdef bint ok
        if self._initialized:
            raise RuntimeError("initialize() was already called")
        self._wrapper.SetFirstBrowser(start_url is not None)
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
        cdef CefBrowserSettings browser_settings
        _g_to_BrowserSettings(self._browser_settings, &browser_settings)
        self._wrapper.SetBrowserSettings(browser_settings)
        if _cef_was_shut_down:
            raise RuntimeError("CEF can be initialized only once per process, "
                               "and it was shut down already")
        # The first browser is made inside this call and its handlers (on_after_created) run before
        # it returns: the application can use the app from there.
        self._initialized = True
        global _cef_started
        _cef_started = True                     # before the first browser: its handlers run inside this call
        with nogil:
            ok = self._wrapper.InitCefSimple(url)
        if not ok:
            _cef_started = False
            self._initialized = False
            raise RuntimeError("CefInitialize() failed")

    def do_message_loop_work(self):
        """Run one iteration of the CEF message loop.

        Call it regularly. On macOS, when ``Settings.external_message_pump`` is not set, it
        also handles the pending events of the application (the windows CEF made need them
        for input, title and closing). An application with an event loop of its own uses
        :class:`~cefweaver.MessagePump` and keeps its loop.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        self._require_running()
        with nogil:
            self._wrapper.DoCefMessageLoopWork()
        if sys.platform == "darwin" and not self._wrapper.ExternalMessagePump():
            self._wrapper.PumpApplicationEvents()

    def shutdown(self):
        """Shut CEF down.

        Does nothing if CEF is not running.
        """
        if not self._initialized or self._shut_down:
            return
        with nogil:
            self._wrapper.ShutdownCefSimple()
        self._shut_down = True
        global _cef_was_shut_down
        _cef_was_shut_down = True

    # -- browser ---------------------------------------------------------------

    def load_url(self, url):
        """Navigate the first browser to a URL.

        Args:
            url (str): The URL.

        Returns:
            bool: ``False`` if the browser does not exist yet.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        cdef string value = _utf8(url)
        cdef bint done
        self._require_running()
        with nogil:
            done = self._wrapper.LoadUrl(value)
        return done

    def execute_javascript(self, code):
        """Run JavaScript in the main frame of the first browser.

        Args:
            code (str): The JavaScript.

        Returns:
            bool: ``False`` if the code was not run because there is no browser yet or the
            page is still loading.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        cdef string value = _utf8(code)
        cdef bint done
        self._require_running()
        with nogil:
            done = self._wrapper.ExecuteJavascript(value)
        return done

    def add_resource(self, url, content, mime_type="text/html", headers=None, int status=200):
        """Serve content for a URL without network access.

        The query and fragment of a requested URL are ignored.

        Args:
            url (str): An absolute ``http`` or ``https`` URL.
            content (str | bytes): The body; a ``str`` is encoded as UTF-8.
            mime_type (str, optional): The MIME type. Defaults to ``"text/html"``.
            headers (dict[str, str], optional): Further response headers.
            status (int, optional): The HTTP status. Defaults to 200.

        Raises:
            ValueError: If ``url`` is not an absolute ``http`` or ``https`` URL.
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down, or if
                CEF does not accept the scheme handler.

        Note:
            Call it after :meth:`initialize` and before the page is loaded.
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
        """bool: Whether CEF is running.

        ``True`` from :meth:`initialize` until all browsers are closed or :meth:`shutdown`
        is called (a popup closing alone leaves it running).
        """
        return self._initialized and not self._shut_down and self._wrapper.IsRunning()

    @property
    def is_ready_to_execute_javascript(self):
        """bool: Whether the first browser has finished loading and can run JavaScript."""
        return (self._initialized and not self._shut_down
                and self._wrapper.IsReadyToExecuteJavascript())


__all__ = ["CefApp", "QueryHandler", "QueryCallback", "AppHandler",
           "SchemeRegistrar", "PreferenceRegistrar"] + __generated_all__
