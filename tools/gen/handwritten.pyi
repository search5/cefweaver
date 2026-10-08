import os
from collections.abc import Callable, Sequence
from typing import Any, NamedTuple

class QueryHandler:
    """Answers the queries a page sends with `window.cefQuery({request, persistent,
    onSuccess, onFailure})` (CEF's message router, as in java-cef).

    Subclass it and add an instance with `CefApp.add_query_handler()` before
    `initialize()`. All methods run on the thread that called `initialize()`, inside
    `do_message_loop_work()`.
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
        """Return True to take the query and answer it with `callback`, now or later;
        False to leave it to the next handler (if none takes it, the page gets -1)."""
    def on_query_canceled(self, browser: Browser, frame: Frame, query_id: int) -> None:
        """The page canceled a query this handler took, left the page, or went away."""

class QueryCallback:
    """The answer to one query; usable from any thread. A callback that is dropped without
    an answer fails the query."""

    def success(self, response: str | bytes | bytearray | memoryview) -> bool: ...
    def failure(self, error_code: int, message: str = "") -> bool: ...

class CefApp:
    """An embedded Chromium (CEF) instance.

    CEF can be initialized only once per process, also after `shutdown()`.
    """

    def __init__(self) -> None: ...
    def set_subprocess_path(self, path: str | bytes | os.PathLike[str]) -> None: ...
    def set_cache_path(self, path: str | bytes | os.PathLike[str]) -> None: ...
    def set_resources_path(self, path: str | bytes | os.PathLike[str]) -> None: ...
    def add_command_line_switch(self, name: str, value: str = "") -> None: ...
    def set_client(self, client: Client | None) -> None: ...
    @property
    def devtools_menu(self) -> bool: ...
    @devtools_menu.setter
    def devtools_menu(self, value: bool) -> None: ...
    def set_query_functions(self, query: str = "cefQuery", cancel: str = "cefQueryCancel") -> None: ...
    def add_query_handler(self, handler: QueryHandler, first: bool = False) -> None: ...
    def remove_query_handler(self, handler: QueryHandler) -> bool: ...
    def add_javascript_binding(self, name: str, callback: Callable[..., Any]) -> None: ...
    def initialize(self, start_url: str = "about:blank") -> None: ...
    def do_message_loop_work(self) -> None: ...
    def shutdown(self) -> None: ...
    def load_url(self, url: str) -> bool: ...
    def execute_javascript(self, code: str) -> bool: ...
    def add_resource(
        self,
        url: str,
        content: str | bytes,
        mime_type: str = "text/html",
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        """Serve `content` for `url` (http or https) without a network access.

        Call it after `initialize()`.
        """
    @property
    def is_running(self) -> bool: ...
    @property
    def is_ready_to_execute_javascript(self) -> bool: ...
