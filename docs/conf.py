"""Sphinx configuration of the cefweaver documentation.

The text comes from the docstrings of the package (Google style, read by napoleon). The package, with its compiled
extension, must be installed: autodoc imports it. The language is selected with ``-D language=ko``; the catalogs
live in ``locale/<language>/LC_MESSAGES`` (see the Makefile).
"""

import ctypes
from unittest import mock

# The Win32 toolkit module loads user32 at import; on another system only its docstrings are read.
for _name in ("WinDLL", "windll", "WINFUNCTYPE", "WinError", "FormatError", "GetLastError"):
    if not hasattr(ctypes, _name):
        setattr(ctypes, _name, mock.MagicMock())

project = "cefweaver"
author = "cefweaver contributors"
copyright = "cefweaver contributors, BSD-3-Clause"
language = "en"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

source_suffix = ".rst"
master_doc = "index"
exclude_patterns = ["_build", "locale"]
pygments_style = "sphinx"

# Internationalization: ``make gettext`` writes the templates, ``sphinx-intl`` keeps the .po files.
locale_dirs = ["locale/"]
gettext_compact = False
gettext_uuid = False

# Google style only
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_ivar = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "undoc-members": False, "show-inheritance": True}
autodoc_inherit_docstrings = True
# The toolkit modules import their toolkit at the top; the docstrings do not need it.
# (Qt needs the real binding, its key table is built from the enum values at import: install PyQt6 and Pillow.)
autodoc_mock_imports = ["gi", "cairo", "PySide6", "wx", "kivy", "sdl2", "pygame", "objc", "AppKit",
                        "pywintypes", "win32api", "win32con", "win32gui", "win32clipboard", "win32process", "pythoncom", "win32event", "win32file", "win32ui", "win32com", "win32com.client", "winerror", "win32timezone", "win32clipboard"]
nitpicky = True
# Types of the toolkits that the Args lines name; their documentation is not part of this one.
nitpick_ignore_regex = [
    ("py:class", r"(Gdk|Gtk|gi|cairo|kivy|Qt|PyQt6|wx|win32\w*|Q[A-Z]\w+)\b.*"),
    ("py:class", r"(Texture|Image|Bitmap|Surface)"),
    ("py:class", r"(optional|callable|iterable|collection|collections?\.abc\.\w+|sequence|iterator)"),       # words of Args types
]

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_theme = "sphinx_rtd_theme"
html_theme_options = {"collapse_navigation": False, "navigation_depth": 3, "titles_only": False}
html_title = "cefweaver"
html_show_sphinx = False


def _attribute_docstring(app, what, name, obj, options, lines):
    """Keep napoleon from reading the text before the first colon of an attribute docstring as its type.

    The docstrings of enumeration members and fields come from the CEF headers and may hold a colon
    (``file://``, "to whit: ..."); a leading colon makes the type empty.
    """
    if what in ("attribute", "data") and lines and not lines[0].startswith(":"):
        lines[0] = ": " + lines[0]


def _skip_types(app, what, name, obj, skip, options):
    """``cefweaver`` re-exports the structures of ``cefweaver.types``; document them there only."""
    if app.env.docname == "api/core" and (getattr(obj, "__module__", None) or "").startswith("cefweaver.types"):
        return True
    return None


def setup(app):
    app.connect("autodoc-process-docstring", _attribute_docstring, priority=100)
    app.connect("autodoc-skip-member", _skip_types)
