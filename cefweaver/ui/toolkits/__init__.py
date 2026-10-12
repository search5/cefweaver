"""Adapters of :mod:`cefweaver.ui` for GUI toolkits, one module each.

The modules are ``gtk3``, ``qt`` (PyQt6 and PySide6), ``tk``, ``sdl2``, ``pywin32``, ``wx`` and ``kivy``.

Nothing in this package is imported by :mod:`cefweaver` or :mod:`cefweaver.ui`. Import the module of the toolkit in
use, for example ``from cefweaver.ui.toolkits import qt``; it requires that toolkit (the extras ``cefweaver[qt]``
and so on). The modules do not import each other and use only the public API of :mod:`cefweaver.ui`.
"""
