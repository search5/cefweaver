"""Microphone and camera permission requests of a page.

With ``BrowserView(adapter, media_permissions=policy)``, CEF calls ``policy(request)`` when a
page asks for the microphone or the camera (``getUserMedia``). The policy receives a
:class:`MediaRequest` and answers with ``request.allow()`` or ``request.deny()``, immediately
or later. Without a policy CEF keeps its default answer, which refuses.
"""

import sys

from cefweaver import types

DEVICES = types.MediaAccessPermissionTypes.DEVICE_AUDIO_CAPTURE | types.MediaAccessPermissionTypes.DEVICE_VIDEO_CAPTURE


class MediaRequest:
    """A request of a page for the microphone or the camera.

    It is answered once; later answers are ignored.

    Args:
        origin (str): The origin of the requesting page.
        permissions (MediaAccessPermissionTypes): The requested permissions.
        is_main_frame (bool): Whether the request comes from the main frame.
        answer: The CEF callback that receives the answer.

    Attributes:
        origin (str): The origin of the requesting page.
        permissions (~cefweaver.types.MediaAccessPermissionTypes): The requested permissions.
        is_main_frame (bool): Whether the request comes from the main frame.
    """

    def __init__(self, origin, permissions, is_main_frame, answer):
        self.origin = origin
        self.permissions = types.MediaAccessPermissionTypes(int(permissions))
        self.is_main_frame = is_main_frame
        self._answer = answer

    def allow(self, permissions=None):
        """Grant the request.

        Args:
            permissions (MediaAccessPermissionTypes, optional): The permissions to grant,
                restricted to those requested. Defaults to everything requested.
        """
        if self._answer is None:
            return
        given = self.permissions if permissions is None else self.permissions & types.MediaAccessPermissionTypes(int(permissions))
        answer, self._answer = self._answer, None
        answer.continue_(given)

    def deny(self):
        """Refuse the request."""
        if self._answer is None:
            return
        answer, self._answer = self._answer, None
        answer.cancel()


def allow_origins(*origins):
    """Create a policy that grants the microphone and the camera to the given origins only.

    Requests from other origins are denied, and permissions other than audio and video capture
    (such as screen capture) are never granted.

    Args:
        *origins (str): Origins as ``scheme://host`` with the port if any, e.g.
            ``https://meet.example.org``.

    Returns:
        callable: A policy for ``media_permissions``.
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
    """Run a policy for a request.

    An exception raised by the policy denies the request and is reported through
    ``sys.excepthook``.

    Args:
        policy (callable): The policy.
        request (MediaRequest): The request.
    """
    try:
        policy(request)
    except Exception:
        request.deny()
        sys.excepthook(*sys.exc_info())
