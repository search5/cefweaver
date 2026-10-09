"""The microphone and the camera of a page: the application decides.

``BrowserView(adapter, media_permissions=policy)``: when a page asks for the microphone or the camera
(``getUserMedia``), CEF asks ``policy(request)``. The request has ``origin``, ``permissions``
(``types.MediaAccessPermissionTypes``) and ``is_main_frame``, and the policy answers with ``request.allow()`` or
``request.deny()``, at once or later (after it asked the user). Without a policy CEF keeps its own answer, which
refuses. The sound then comes from the microphone of the system through Chromium itself.
"""

import sys

from cefweaver import types

DEVICES = types.MediaAccessPermissionTypes.DEVICE_AUDIO_CAPTURE | types.MediaAccessPermissionTypes.DEVICE_VIDEO_CAPTURE


class MediaRequest:
    """One request of a page for the microphone or the camera. It is answered once; later answers are ignored."""

    def __init__(self, origin, permissions, is_main_frame, answer):
        self.origin = origin
        self.permissions = types.MediaAccessPermissionTypes(int(permissions))
        self.is_main_frame = is_main_frame
        self._answer = answer

    def allow(self, permissions=None):
        """Give the page what it asked for, or ``permissions`` (never more than it asked for)."""
        if self._answer is None:
            return
        given = self.permissions if permissions is None else self.permissions & types.MediaAccessPermissionTypes(int(permissions))
        answer, self._answer = self._answer, None
        answer.continue_(given)

    def deny(self):
        """Refuse the page."""
        if self._answer is None:
            return
        answer, self._answer = self._answer, None
        answer.cancel()


def allow_origins(*origins):
    """A policy that gives the microphone and the camera (not the screen) to pages of these origins only.

    An origin is ``scheme://host`` with the port if there is one, e.g. ``https://meet.example.org``.
    """
    allowed = {origin.rstrip("/") for origin in origins}

    def policy(request):
        origin = request.origin.rstrip("/")
        given = request.permissions & DEVICES
        if origin in allowed and given:
            request.allow(given)
        else:
            request.deny()
    return policy


def ask(policy, request):
    """Run the policy; an error in it denies the request and is reported like the error of any handler."""
    try:
        policy(request)
    except Exception:
        request.deny()
        sys.excepthook(*sys.exc_info())
