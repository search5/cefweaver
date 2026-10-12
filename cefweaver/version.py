"""The versions of cefweaver, CEF and Chromium."""

from typing import NamedTuple


class Version(NamedTuple):
    """The versions of cefweaver, CEF and Chromium, as returned by ``get_version()``.

    Attributes:
        cefweaver (str): The cefweaver package version.
        cef_major (int): The CEF major version.
        cef_minor (int): The CEF minor version.
        cef_patch (int): The CEF patch version.
        cef_commit (int): The CEF commit number.
        chrome_major (int): The Chromium major version.
        chrome_minor (int): The Chromium minor version.
        chrome_build (int): The Chromium build number.
        chrome_patch (int): The Chromium patch number.
    """

    cefweaver: str
    cef_major: int
    cef_minor: int
    cef_patch: int
    cef_commit: int
    chrome_major: int
    chrome_minor: int
    chrome_build: int
    chrome_patch: int

    @property
    def cef(self):
        """str: The CEF version as ``major.minor.patch``, e.g. ``154.0.34``."""
        return "%d.%d.%d" % (self.cef_major, self.cef_minor, self.cef_patch)

    @property
    def chrome(self):
        """str: The Chromium version, e.g. ``154.0.8037.98``."""
        return "%d.%d.%d.%d" % (self.chrome_major, self.chrome_minor, self.chrome_build,
                                self.chrome_patch)


def _package_version():
    try:
        from importlib.metadata import version
        return version("cefweaver")
    except Exception:
        return "0.0"
