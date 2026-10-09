"""The extension module of cefweaver (the rest of the metadata is in pyproject.toml).

The extension is declared here and not in pyproject.toml because the libraries to link differ
per platform and the static ``ext-modules`` table cannot branch.

The native libraries must be prepared first with ``python tools/prepare.py``, which also links
the CEF distribution at build/native/cef. Linux (x86_64) and macOS (arm64) are supported here;
the library names and directories differ on Windows.
"""

import os
import sys

from setuptools import Extension, setup

NATIVE = "build/native"

include_dirs = [f"{NATIVE}/cef", "native/cefwrapper"]
library_dirs = [
    f"{NATIVE}/native/cefwrapper",
    f"{NATIVE}/libcef_dll_wrapper",
]
# Relink when the native libraries or headers change; without this setuptools only
# compares the .pyx/.cpp timestamps and silently reuses a stale build.
depends = [
    "cefweaver/cefwrapper.pxd",
    "cefweaver/cef_api.pxd",
    "cefweaver/cef_api.pxi",
    "native/cefwrapper/generated/cefweaver_proxies.h",
    "native/cefwrapper/library.h",
    "native/cefwrapper/javascript_binding.h",
    "native/cefwrapper/query_router.h",
    "native/cefwrapper/bridge.h",
    "native/cefwrapper/app_hooks.h",
    "native/cefwrapper/runtime.h",
    "native/cefwrapper/platform_structs.h",
    f"{NATIVE}/native/cefwrapper/libcefwrapper.a",
    f"{NATIVE}/libcef_dll_wrapper/libcef_dll_wrapper.a",
]

if sys.platform == "darwin":
    # libcef is not linked: the CEF framework is loaded at run time (native/cefwrapper/
    # mac_runtime.mm), the way the helper apps do it.
    # The wrapper libraries are built for macOS 12 (CEF_TARGET_SDK in CEF's cmake).
    os.environ.setdefault("MACOSX_DEPLOYMENT_TARGET", "12.0")
    libraries = ["cefwrapper", "cef_dll_wrapper"]
    define_macros = [("NDEBUG", "1")]
    extra_compile_args = ["-std=c++20", "-mmacosx-version-min=12.0"]
    extra_link_args = ["-framework", "Cocoa", "-framework", "AppKit",
                       "-framework", "IOSurface", "-Wl,-ObjC"]
else:
    library_dirs.append(f"{NATIVE}/cef/Release")
    depends.append(f"{NATIVE}/cef/Release/libcef.so")
    # Order matters for the static libraries: cefwrapper uses cef_dll_wrapper.
    libraries = ["cefwrapper", "cef_dll_wrapper", "cef", "X11", "dl", "pthread"]
    # Must match how the CEF wrapper libraries were compiled (see flags.make).
    define_macros = [("NDEBUG", "1"), ("_FILE_OFFSET_BITS", "64")]
    extra_compile_args = ["-std=c++20"]
    extra_link_args = ["-Wl,-rpath,$ORIGIN"]

setup(
    ext_modules=[
        Extension(
            "cefweaver._cefweaver",
            sources=["cefweaver/_cefweaver.pyx"],
            language="c++",
            include_dirs=include_dirs,
            library_dirs=library_dirs,
            depends=depends,
            libraries=libraries,
            define_macros=define_macros,
            extra_compile_args=extra_compile_args,
            extra_link_args=extra_link_args,
        )
    ],
)
