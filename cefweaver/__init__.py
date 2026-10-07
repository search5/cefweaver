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

from . import _cefweaver  # noqa: E402
from ._cefweaver import *  # noqa: E402,F401,F403  (the public names are listed in __all__)

__all__ = list(_cefweaver.__all__)
