"""Adapters of ``cefweaver.ui`` for GUI toolkits, one module each: ``gtk3``, ``qt`` (PyQt6 and PySide6), ``tk``,
``sdl2``, ``wx`` and ``kivy``.

Nothing here is imported by ``cefweaver`` or ``cefweaver.ui``: import the module of the toolkit you use
(``from cefweaver.ui.toolkits import qt``), which needs that toolkit (the extras ``cefweaver[qt]`` and so on). The
modules do not import each other and use only the public side of ``cefweaver.ui``, so that one of them can be
moved to a package of its own. Each module says at its top what it has been checked on and what not.
"""
