"""The versions of cefweaver, CEF and Chromium (java-cef's ``CefApp.getVersion()``)."""

from typing import NamedTuple


class Version(NamedTuple):
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
        """The CEF version, e.g. ``154.0.34``."""
        return "%d.%d.%d" % (self.cef_major, self.cef_minor, self.cef_patch)

    @property
    def chrome(self):
        """The Chromium version, e.g. ``154.0.8037.98``."""
        return "%d.%d.%d.%d" % (self.chrome_major, self.chrome_minor, self.chrome_build,
                                self.chrome_patch)


def _package_version():
    try:
        from importlib.metadata import version
        return version("cefweaver")
    except Exception:
        return "0.0"
