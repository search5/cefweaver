import datetime
import os
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

from .settings import Settings
from .types import PreferencesType
from .version import Version

def _cef_version_info(entry: int) -> int: ...

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

    def on_query(
        self,
        browser: Browser,
        frame: Frame,
        query_id: int,
        request: str | bytes,
        persistent: bool,
        callback: QueryCallback,
    ) -> bool:
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
    def on_query_canceled(self, browser: Browser, frame: Frame, query_id: int) -> None:
        """Handle the end of a query this handler took.

        Called when the page canceled the query (``cefQueryCancel``), left the page or went
        away, or when the handler was removed. The callback of the query answers nothing any
        more.

        Args:
            browser (~cefweaver.Browser): The browser that held the page.
            frame (~cefweaver.Frame): The frame that sent the query.
            query_id (int): The identifier of the query.
        """

class QueryCallback:
    """The answer to one query, given to :meth:`QueryHandler.on_query`.

    Instances are created by CEF; constructing one raises ``TypeError``. A query is
    answered once (a persistent one many times, until it fails or is canceled). A
    callback that is dropped without an answer fails the query with the error code -1.

    Note:
        It can be used from any thread.
    """

    def success(self, response: str | bytes | bytearray | memoryview) -> bool:
        """Answer the ``onSuccess`` of the page.

        Args:
            response (str | bytes | bytearray | memoryview): The response; the page gets a
                string for ``str`` and an ``ArrayBuffer`` for the other types.

        Returns:
            bool: Whether the answer was sent.

        Raises:
            TypeError: If ``response`` is none of the accepted types.
        """
        ...
    def failure(self, error_code: int, message: str = "") -> bool:
        """Answer the ``onFailure`` of the page.

        Args:
            error_code (int): The error code.
            message (str, optional): The error message. Defaults to ``""``.

        Returns:
            bool: Whether the answer was sent.
        """
        ...

class AppHandler:
    """Base class for hooks into the start of the application.

    Corresponds to java-cef's ``CefAppHandler``. Subclass it and give an instance to
    :meth:`~cefweaver.CefApp.set_app_handler`. An exception raised by a method goes to
    ``sys.excepthook``.

    Note:
        The methods run on the thread that called :meth:`~cefweaver.CefApp.initialize`,
        except :meth:`on_schedule_message_pump_work`.
    """

    def on_before_command_line_processing(self, process_type: str, command_line: CommandLine) -> None:
        """Change the command line of the browser process.

        Called before the switches of :meth:`~cefweaver.CefApp.add_command_line_switch` are
        added.

        Args:
            process_type (str): Always ``""`` (the browser process).
            command_line (~cefweaver.CommandLine): The command line, which may be changed.
        """
    def on_register_custom_schemes(self, registrar: SchemeRegistrar) -> None:
        """Register custom schemes.

        The renderer processes get the same schemes.

        Args:
            registrar (~cefweaver.SchemeRegistrar): Registers a scheme with
                ``add_custom_scheme(name, options)``, where ``options`` combines
                :class:`~cefweaver.types.SchemeOptions` values. Valid during this call only.
        """
    def on_before_child_process_launch(self, command_line: CommandLine) -> None:
        """Change the command line of a child process before it starts.

        Called for the renderer, GPU and utility processes, after the switches of cefweaver
        itself (the custom schemes, the JavaScript bridge) were added.

        Args:
            command_line (~cefweaver.CommandLine): The command line, which may be changed.
                ``get_switch_value("type")`` gives the kind of process.
        """
    def on_register_custom_preferences(self, type: PreferencesType, registrar: PreferenceRegistrar) -> None:
        """Register preferences of the application.

        Args:
            type (~cefweaver.types.PreferencesType): ``GLOBAL`` (called once, for the global
                preferences) or ``REQUEST_CONTEXT`` (called for each request context).
            registrar (~cefweaver.PreferenceRegistrar): Registers a preference with
                ``add_preference(name, default_value)``. Valid during this call only.
        """
    def on_context_initialized(self) -> None:
        """Handle the initialization of the CEF context.

        The first browser is created right after this call.
        """
    def on_schedule_message_pump_work(self, delay_ms: int) -> None:
        """Handle CEF's request to run the message loop later.

        Called only when ``Settings.external_message_pump`` is ``True``. An implementation
        should note the request and wake the event loop of the application, which then calls
        :meth:`~cefweaver.CefApp.do_message_loop_work`.

        Args:
            delay_ms (int): The delay in milliseconds; 0 means now.

        Note:
            Unlike the other methods, this one is called on any thread of CEF.
        """
        ...
    def on_already_running_app_relaunch(self, command_line: CommandLine, current_directory: str) -> bool:
        """Handle a second start of the application with the same user data.

        Called when a second process with the same ``cache_path`` reaches this one.

        Args:
            command_line (~cefweaver.CommandLine): The command line of the second start.
            current_directory (str): The current directory of the second start.

        Returns:
            bool: ``True`` if the start was handled; ``False`` to let CEF open a new window.
            The default implementation returns ``False``.
        """

class SchemeRegistrar:
    """Registers custom schemes.

    Instances are created by CEF and given to
    :meth:`AppHandler.on_register_custom_schemes`; constructing one raises ``TypeError``.

    Note:
        Valid during that call only.
    """

    def add_custom_scheme(self, scheme_name: str, options: int) -> bool:
        """Register a custom scheme.

        Args:
            scheme_name (str): The name of the scheme.
            options (int): A combination of :class:`~cefweaver.types.SchemeOptions` values.

        Returns:
            bool: ``False`` if CEF refuses the scheme.

        Raises:
            RuntimeError: If called outside :meth:`AppHandler.on_register_custom_schemes`.
        """
        ...

class PreferenceRegistrar:
    """Registers preferences of the application.

    Instances are created by CEF and given to
    :meth:`AppHandler.on_register_custom_preferences`; constructing one raises
    ``TypeError``.

    Note:
        Valid during that call only.
    """

    def add_preference(self, name: str, default_value: Value) -> bool:
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
        ...

class CefApp:
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

    def __init__(self) -> None: ...
    def set_subprocess_path(self, path: str | bytes | os.PathLike[str]) -> None:
        """Set the path of the ``cefsubprocess`` executable.

        Args:
            path (str | bytes | os.PathLike): The path.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        ...
    def set_cache_path(self, path: str | bytes | os.PathLike[str]) -> None:
        """Set the directory for the browser cache and profile data.

        Args:
            path (str | bytes | os.PathLike): The directory.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        ...
    def set_resources_path(self, path: str | bytes | os.PathLike[str]) -> None:
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
        ...
    def add_command_line_switch(self, name: str, value: str = "") -> None:
        """Add a Chromium command line switch.

        Args:
            name (str): The switch, for example ``"disable-gpu"``.
            value (str, optional): The value of the switch. Defaults to ``""``, which adds a
                bare switch.

        Raises:
            RuntimeError: If called after :meth:`initialize`.
        """
        ...
    def set_client(self, client: Client | None) -> None:
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
        ...
    @property
    def devtools_menu(self) -> bool:
        """bool: Whether the context menu has "Show DevTools", "Close DevTools" and "Inspect Element".

        Off by default. It can be changed at any time and applies to the menus built
        afterwards. The items come after what the handler of :meth:`set_client` put in the
        menu; the handler gets the same events either way.
        """
        ...
    @devtools_menu.setter
    def devtools_menu(self, value: bool) -> None: ...
    def set_query_functions(self, query: str = "cefQuery", cancel: str = "cefQueryCancel") -> None:
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
        ...
    def create_browser(self, url: str = "about:blank", offscreen: bool | None = None,
                       transparent: bool | None = None,
                       request_context: RequestContext | None = None,
                       settings: BrowserSettings | None = None,
                       shared_texture: bool | None = None,
                       parent_view: int | None = None) -> Browser:
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
        ...
    @staticmethod
    def get_version() -> Version:
        """Return the versions of cefweaver, CEF and Chromium.

        Returns:
            ~cefweaver.Version: The same value as :func:`cefweaver.get_version`.
        """
        ...
    @property
    def browser_settings(self) -> BrowserSettings:
        """~cefweaver.types.BrowserSettings: The settings of the browsers.

        They apply to the first browser and to the browsers that :meth:`create_browser` makes
        without settings of their own. A field left at its default is CEF's choice.

        Note:
            Assigning is possible before :meth:`initialize` only (``RuntimeError`` after it;
            ``TypeError`` for another type).
        """
        ...
    @browser_settings.setter
    def browser_settings(self, value: BrowserSettings) -> None: ...
    @property
    def shared_texture(self) -> bool:
        """bool: Whether an offscreen browser gives shared textures instead of pixels.

        If ``True``, CEF's shared textures (GPU memory; dmabuf file descriptors on Linux) go
        to ``RenderHandler.on_accelerated_paint()`` instead of pixels to ``on_paint()``. Off
        by default. Needs a GPU.

        Note:
            Assigning is possible before :meth:`initialize` only (``TypeError`` for a value
            that is not a ``bool``).
        """
        ...
    @shared_texture.setter
    def shared_texture(self, value: bool) -> None: ...
    @property
    def transparent(self) -> bool:
        """bool: Whether an offscreen browser paints transparent pixels where the page draws nothing.

        On by default (java-cef's ``isTransparent``). ``False`` paints them in the opaque
        ``Settings.background_color``, white if there is none.

        Note:
            Assigning is possible before :meth:`initialize` only.
        """
        ...
    @transparent.setter
    def transparent(self, value: bool) -> None: ...
    @property
    def settings(self) -> Settings:
        """~cefweaver.Settings: The settings of CEF (java-cef's ``CefSettings``).

        :meth:`initialize` reads them and freezes them.

        Note:
            Assigning is possible before :meth:`initialize` only (``RuntimeError`` after it;
            ``TypeError`` for another type).
        """
        ...
    @settings.setter
    def settings(self, value: Settings) -> None: ...
    def set_request_context(self, context: RequestContext | None) -> None:
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
        ...
    def set_app_handler(self, handler: AppHandler | None) -> None:
        """Set the hooks into the start of the application.

        Args:
            handler (AppHandler | None): The handler; ``None`` removes it.

        Raises:
            TypeError: If ``handler`` is neither an :class:`AppHandler` nor ``None``.
            RuntimeError: If called after :meth:`initialize`.
        """
        ...
    def enable_renderer_events(self, stack_size: int = 10) -> None:
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
        ...
    def add_query_handler(self, handler: QueryHandler, first: bool = False) -> None:
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
        ...
    def remove_query_handler(self, handler: QueryHandler) -> bool:
        """Remove a query handler.

        The queries it took are canceled: :meth:`QueryHandler.on_query_canceled` is called
        and the ``onFailure`` of the page gets -1.

        Args:
            handler (QueryHandler): The handler.

        Returns:
            bool: ``False`` if the handler was not added.
        """
        ...
    def cancel_pending_queries(self, browser: Browser | None = None, handler: QueryHandler | None = None) -> None:
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
        ...
    @property
    def parent_view(self) -> int:
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
        ...
    @parent_view.setter
    def parent_view(self, value: int) -> None: ...
    @property
    def offscreen(self) -> bool:
        """bool: Whether the browser is rendered offscreen.

        Off by default. An offscreen browser has no window; CEF draws into the buffer that
        ``RenderHandler.on_paint()`` of the client receives, and the render handler of the
        client must give the size with ``get_view_rect()``. Popups are blocked, as in
        java-cef.

        Note:
            Assigning is possible before :meth:`initialize` only.
        """
        ...
    @offscreen.setter
    def offscreen(self, value: bool) -> None: ...
    @property
    def windowless_frame_rate(self) -> int:
        """int: The frames per second of an offscreen browser, from 1 to 60.

        Defaults to 30. It is the upper bound of the ``on_paint()`` calls.

        Note:
            Assigning is possible before :meth:`initialize` only (``ValueError`` outside
            1 to 60).
        """
        ...
    @windowless_frame_rate.setter
    def windowless_frame_rate(self, value: int) -> None: ...
    def add_javascript_binding(self, name: str, callback: Callable[..., Any]) -> None:
        """Expose a Python callable to pages as ``window.<name>(...)``.

        The arguments of the call are converted to ``int``, ``bool``, ``float`` or ``str``;
        other JavaScript types arrive as ``None``. An exception raised by the callable goes
        to ``sys.excepthook``.

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
        ...
    def initialize(self, start_url: str | None = "about:blank") -> None:
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
        ...
    def do_message_loop_work(self) -> None:
        """Run one iteration of the CEF message loop.

        Call it regularly. On macOS, when ``Settings.external_message_pump`` is not set, it
        also handles the pending events of the application (the windows CEF made need them
        for input, title and closing). An application with an event loop of its own uses
        :class:`~cefweaver.MessagePump` and keeps its loop.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        ...
    def shutdown(self) -> None:
        """Shut CEF down.

        Does nothing if CEF is not running.
        """
        ...
    def load_url(self, url: str) -> bool:
        """Navigate the first browser to a URL.

        Args:
            url (str): The URL.

        Returns:
            bool: ``False`` if the browser does not exist yet.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        ...
    def execute_javascript(self, code: str) -> bool:
        """Run JavaScript in the main frame of the first browser.

        Args:
            code (str): The JavaScript.

        Returns:
            bool: ``False`` if the code was not run because there is no browser yet or the
            page is still loading.

        Raises:
            RuntimeError: If :meth:`initialize` was not called or CEF was shut down.
        """
        ...
    def add_resource(
        self,
        url: str,
        content: str | bytes,
        mime_type: str = "text/html",
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
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
    @property
    def is_running(self) -> bool:
        """bool: Whether CEF is running.

        ``True`` from :meth:`initialize` until all browsers are closed or :meth:`shutdown`
        is called (a popup closing alone leaves it running).
        """
        ...
    @property
    def is_ready_to_execute_javascript(self) -> bool:
        """bool: Whether the first browser has finished loading and can run JavaScript."""
        ...
