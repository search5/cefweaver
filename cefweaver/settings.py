"""CEF settings.

``CefApp.settings`` is a :class:`Settings` object. The cache path, resources path and
subprocess path are set with ``CefApp.set_cache_path()``, ``CefApp.set_resources_path()`` and
``CefApp.set_subprocess_path()``; offscreen mode is ``CefApp.offscreen``.
"""

from . import types

# name -> (kind, description); the kinds are "str", "bool", "int", "port", "color" and "severity"
_FIELDS = {
    "external_message_pump": ("bool", "The application runs the message loop (``do_message_loop_work()``) when ``AppHandler.on_schedule_message_pump_work()`` says so, instead of polling."),
    "root_cache_path": ("str", "The directory of the profile data shared by the caches below it (CEF's ``root_cache_path``). ``set_cache_path()`` must name a directory within it; without that the cache is the root itself."),
    "user_agent": ("str", "The user agent string; it replaces the default one."),
    "user_agent_product": ("str", "The product token of the default user agent, e.g. ``Product/1.2``."),
    "locale": ("str", "The UI locale, e.g. ``ko``. On Linux the language of the pages follows LANGUAGE/LANG, not this setting."),
    "log_file": ("str", "The log file; the default is ``debug.log`` in the executable's directory."),
    "log_severity": ("severity", "A ``types.LogSeverity``; ``DISABLE`` writes nothing."),
    "javascript_flags": ("str", "Flags for V8, e.g. ``--expose-gc``."),
    "remote_debugging_port": ("port", "The port of the remote debugging server (1024 to 65535); 0 or unset: off."),
    "persist_session_cookies": ("bool", "Keep session cookies in the cache directory across restarts."),
    "command_line_args_disabled": ("bool", "Ignore the command line arguments of the process."),
    "chrome_policy_id": ("str", "The id of the Chrome policy that applies to the app."),
    "uncaught_exception_stack_size": ("int", "The frames of the stack trace of an uncaught JavaScript exception."),
    "background_color": ("color", "The background of the browser as ARGB (0xAARRGGBB) where the page draws none."),
    "cookieable_schemes_list": ("str", "The schemes that may have cookies, separated by commas."),
    "cookieable_schemes_exclude_defaults": ("bool", "Do not add http, https, ws and wss to the cookieable schemes."),
}


class Settings:
    """The CEF settings, as attributes.

    A field left at ``None`` is not given to CEF, which uses its own default. The values are
    checked on assignment (``TypeError`` for a wrong type, ``ValueError`` for a value out of
    range). The settings are read by ``CefApp.initialize()``; assigning afterwards raises
    ``RuntimeError``. Assigning a name that is not a field raises ``AttributeError``.

    Args:
        **fields: Initial values of the attributes below, by name.

    Raises:
        TypeError: If a name is not a field, or a value has the wrong type.

    Attributes:
        external_message_pump (bool): The application runs the message loop
            (``do_message_loop_work()``) when ``AppHandler.on_schedule_message_pump_work()``
            requests it, instead of polling.
        root_cache_path (str): The directory of the profile data shared by the caches below
            it. ``set_cache_path()`` must name a directory within it; otherwise the cache is
            the root itself.
        user_agent (str): The user agent string; replaces the default one.
        user_agent_product (str): The product token of the default user agent, e.g.
            ``Product/1.2``.
        locale (str): The UI locale, e.g. ``ko``. On Linux the language of pages follows
            ``LANGUAGE``/``LANG``, not this setting.
        log_file (str): The log file; the default is ``debug.log`` in the executable's
            directory.
        log_severity (~cefweaver.types.LogSeverity): The log level; ``DISABLE`` writes
            nothing. An ``int`` is converted to the enum.
        javascript_flags (str): Flags for V8, e.g. ``--expose-gc``.
        remote_debugging_port (int): The port of the remote debugging server, 1024 to 65535;
            0 or ``None`` turns it off.
        persist_session_cookies (bool): Keep session cookies in the cache directory across
            restarts.
        command_line_args_disabled (bool): Ignore the command line arguments of the process.
        chrome_policy_id (str): The id of the Chrome policy that applies to the app.
        uncaught_exception_stack_size (int): The number of frames in the stack trace of an
            uncaught JavaScript exception; not negative.
        background_color (int): The browser background as ARGB (``0xAARRGGBB``), where the
            page draws none.
        cookieable_schemes_list (str): The schemes that may have cookies, separated by commas.
        cookieable_schemes_exclude_defaults (bool): Do not add ``http``, ``https``, ``ws`` and
            ``wss`` to the cookieable schemes.
    """

    __slots__ = tuple(_FIELDS) + ("_frozen",)

    def __init__(self, **fields):
        object.__setattr__(self, "_frozen", False)
        for name in _FIELDS:
            object.__setattr__(self, name, None)
        for name, value in fields.items():
            if name not in _FIELDS:
                raise TypeError("unknown setting %r" % name)
            setattr(self, name, value)

    def __setattr__(self, name, value):
        if name not in _FIELDS:
            raise AttributeError("unknown setting %r" % name)
        if self._frozen:
            raise RuntimeError("the settings cannot change after initialize()")
        if value is not None:
            value = _check(name, _FIELDS[name][0], value)
        object.__setattr__(self, name, value)

    def _freeze(self):
        object.__setattr__(self, "_frozen", True)

    def _given(self):
        """{name: value} of the fields that are set (enums as integers)."""
        return {name: getattr(self, name) for name in _FIELDS if getattr(self, name) is not None}

    def __repr__(self):
        return "Settings(%s)" % ", ".join("%s=%r" % item for item in self._given().items())


def _check(name, kind, value):
    if kind == "str":
        if not isinstance(value, str):
            raise TypeError("%s must be a str" % name)
        return value
    if kind == "bool":
        if not isinstance(value, bool):
            raise TypeError("%s must be a bool" % name)
        return value
    if kind == "severity":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("%s must be a types.LogSeverity" % name)
        return types.LogSeverity(value)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("%s must be an int" % name)
    if kind == "port" and not 0 <= value <= 65535:
        raise ValueError("%s must be a port number" % name)
    if kind == "color" and not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("%s must be ARGB (0 to 0xFFFFFFFF)" % name)
    if kind == "int" and value < 0:
        raise ValueError("%s must not be negative" % name)
    return value
