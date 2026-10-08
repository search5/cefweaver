"""Python bindings for the Chromium Embedded Framework."""

import os
import sys

_package_dir = os.path.dirname(os.path.abspath(__file__))

if sys.platform.startswith("linux"):
    # libcef.so must be loaded first and with global symbols, before the
    # extension module (the same approach as cefpython and `LD_PRELOAD=libcef.so`
    # in java-cef's run scripts).
    import ctypes

    _libcef = os.path.join(_package_dir, "libcef.so")
    if os.path.exists(_libcef):
        ctypes.CDLL(_libcef, mode=ctypes.RTLD_GLOBAL)
elif sys.platform == "win32":
    os.add_dll_directory(_package_dir)  # libcef.dll next to the module (not tested yet)

from . import types  # noqa: E402  (enumerations and value types; plain Python)
from . import settings as _settings  # noqa: E402,F401
from .settings import Settings  # noqa: E402
from .version import Version  # noqa: E402
from . import _cefweaver  # noqa: E402
from ._cefweaver import *  # noqa: E402,F401,F403  (the public names are listed in __all__)
from .pump import MessagePump  # noqa: E402
from .bridge import JavascriptBridge, JsCallback  # noqa: E402
from .texture import read_plane  # noqa: E402


def get_version():
    """The ``Version`` of cefweaver, CEF and Chromium (callable at any time, also before
    ``initialize()``; java-cef's ``CefApp.getVersion()``)."""
    from . import version as _version
    entries = [_cefweaver._cef_version_info(i) for i in range(8)]
    return _version.Version(_version._package_version(), *entries)


__all__ = list(_cefweaver.__all__) + ["types", "Settings", "Version", "get_version", "MessagePump", "JavascriptBridge", "JsCallback", "read_plane"]
