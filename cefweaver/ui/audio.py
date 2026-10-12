"""Audio sinks: receive the sound of a page as interleaved float32 samples.

When a :class:`~cefweaver.ui.BrowserView` is given a sink with ``BrowserView(adapter, audio=sink)``,
it installs an ``AudioHandler`` and passes the page sound to the sink instead of CEF playing it.
The sink can be provided by the application, by a toolkit adapter (``audio_sink()``) or be a
:class:`PygameSink`.

A sink implements three methods:

* ``start(sample_rate, channels)``: A stream begins; may be called again later.
* ``write(samples, frames)``: ``samples`` is ``bytes`` of ``frames * channels`` interleaved
  little-endian float32 values (L R L R ...).
* ``stop()``: The stream ended or failed.

Note:
    The methods are called on the thread of CEF's audio stream and must not block.
"""

import array
import sys


def interleave(planes):
    """Interleave per-channel planes into one buffer of samples.

    Args:
        planes (sequence): One float32 ``memoryview`` (or ``array.array``) per channel.

    Returns:
        tuple: ``(samples, frames)``, where ``samples`` is ``bytes`` of little-endian float32
        values interleaved by channel, and ``frames`` is the number of samples per channel.
    """
    if not planes:
        return b"", 0
    channels = [array.array("f", bytes(plane)) if not isinstance(plane, array.array) else plane for plane in planes]
    frames = len(channels[0])
    if len(channels) == 1:
        samples = channels[0]
    else:
        samples = array.array("f", bytes(4 * frames * len(channels)))
        for index, channel in enumerate(channels):
            samples[index::len(channels)] = channel
    if sys.byteorder != "little":
        samples = array.array("f", samples)
        samples.byteswap()
    return samples.tobytes(), frames


def apply_volume(samples, volume):
    """Scale interleaved float32 samples.

    Args:
        samples (bytes): Interleaved float32 samples in native byte order.
        volume (float): The factor to multiply each sample by.

    Returns:
        bytes: The scaled samples; ``samples`` itself if ``volume`` is 1.0.
    """
    if volume == 1.0:
        return samples
    data = array.array("f", samples)
    for index in range(len(data)):
        data[index] *= volume
    return data.tobytes()


def is_sink(candidate):
    """Return whether an object has the ``start``, ``write`` and ``stop`` methods of a sink.

    Args:
        candidate: The object to test.

    Returns:
        bool: ``True`` if all three are callable attributes.
    """
    return all(callable(getattr(candidate, name, None)) for name in ("start", "write", "stop"))


def _sdl_library():
    """The SDL2 that pygame loaded, as a ``ctypes`` library (the same file: the same devices), or None (Linux)."""
    import ctypes
    import os
    try:
        with open("/proc/self/maps") as maps:
            for line in maps:
                path = line.split()[-1] if line.strip() else ""
                name = os.path.basename(path)
                if name.startswith("libSDL2-") and ".so" in name:        # not libSDL2_mixer and the like
                    return ctypes.CDLL(path)
    except OSError:
        pass
    return None


def _close_device(device):
    """Close a pygame ``AudioDevice`` without holding the GIL.

    ``AudioDevice.close()`` waits for SDL's audio thread while it keeps the GIL, and that thread may be waiting for the
    GIL to run the Python callback: a deadlock (seen, nearly every time when the callback was busy). Calling SDL through
    ``ctypes`` lets go of the GIL for the call, so the callback can finish.
    """
    import ctypes
    library = _sdl_library()
    if library is not None and hasattr(device, "deviceid"):
        library.SDL_CloseAudioDevice(ctypes.c_uint32(device.deviceid))
    else:
        device.close()


class PygameSink:
    """A sink that plays through pygame, for toolkits that cannot play a stream themselves.

    Requires pygame (``pip install pygame``). Samples passed to :meth:`write` are buffered in a
    ring of at most ``max_latency`` seconds; older samples are dropped when playback falls
    behind. Playback starts once ``prebuffer`` seconds are buffered, and again after the ring
    ran empty. A failure to start is reported by ``BrowserView.on_audio_error``.

    Args:
        device (str, optional): The name of the output device. Defaults to the first one.
        volume (float, optional): The factor applied to the samples, 0.0 to 1.0. Defaults to 1.0.
        max_latency (float, optional): The capacity of the ring, in seconds. Defaults to 0.5.
        chunk (int, optional): The size of a device block, in frames. Defaults to 1024.
        prebuffer (float, optional): The seconds of sound collected before playback starts.
            Defaults to 0.04.

    Raises:
        ImportError: If pygame is not installed.

    Attributes:
        device_name (str or None): The ``device`` argument.
        volume (float): The factor applied to the samples.
        max_latency (float): The capacity of the ring, in seconds.
        chunk (int): The size of a device block, in frames.
        prebuffer (float): The seconds collected before playback starts.
    """

    def __init__(self, device=None, volume=1.0, max_latency=0.5, chunk=1024, prebuffer=0.04):
        import os
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        import pygame
        from pygame._sdl2 import audio as sdl_audio
        self._pygame, self._sdl_audio = pygame, sdl_audio
        self.device_name, self.volume, self.max_latency, self.chunk, self.prebuffer = device, volume, max_latency, chunk, prebuffer
        self._playing = False
        import threading
        self._lock = threading.Lock()
        self._ring = bytearray()
        self._device = None
        self._rate = self._channels = 0
        self._counters = dict(written=0, consumed=0, underruns=0, dropped=0)

    def start(self, sample_rate, channels):
        """Open the audio device and begin playback; any previous stream is stopped.

        Args:
            sample_rate (int): The sample rate in Hz.
            channels (int): The number of channels.
        """
        self.stop()
        pygame, sdl_audio = self._pygame, self._sdl_audio
        if not pygame.mixer.get_init():
            pygame.mixer.init()                                  # starts the audio of SDL
        name = self.device_name or sdl_audio.get_audio_device_names(False)[0]
        self._rate, self._channels = sample_rate, channels
        with self._lock:
            self._ring.clear()
            self._playing = False
        self._device = sdl_audio.AudioDevice(devicename=name, iscapture=False, frequency=sample_rate,
                                             audioformat=sdl_audio.AUDIO_F32, numchannels=channels,
                                             chunksize=self.chunk, allowed_changes=0, callback=self._callback)
        self._device.pause(0)

    def write(self, samples, frames):
        """Queue samples for playback.

        Args:
            samples (bytes): Interleaved float32 samples.
            frames (int): The number of samples per channel.
        """
        samples = apply_volume(samples, self.volume)
        limit = int(self._rate * self.max_latency) * self._channels * 4
        with self._lock:
            self._ring += samples
            self._counters["written"] += frames
            if len(self._ring) > limit:
                extra = len(self._ring) - limit
                del self._ring[:extra]
                self._counters["dropped"] += extra // (4 * max(1, self._channels))

    def stop(self):
        """Close the audio device and discard queued samples."""
        device, self._device = self._device, None
        if device is not None:
            try:
                _close_device(device)
            except Exception:
                pass
        with self._lock:
            self._ring.clear()

    def _callback(self, device, buffer):                         # in the thread of SDL's audio
        with self._lock:
            if not self._playing and len(self._ring) >= int(self._rate * self.prebuffer) * self._channels * 4:
                self._playing = True                              # enough is collected
            count = min(len(buffer), len(self._ring)) if self._playing else 0
            buffer[:count] = self._ring[:count]
            del self._ring[:count]
            if count < len(buffer):
                buffer[count:] = bytes(len(buffer) - count)      # nothing to play: silence
                if self._playing:
                    self._playing = False                        # it ran empty: collect again
                    self._counters["underruns"] += 1
            self._counters["consumed"] += count // (4 * max(1, self._channels))

    def stats(self):
        """Return the playback counters.

        Returns:
            dict: ``written``, ``consumed``, ``dropped`` and ``queued`` in frames, and
            ``underruns``, the number of device blocks that found nothing to play.
        """
        with self._lock:
            return dict(self._counters, queued=len(self._ring) // (4 * max(1, self._channels)))


def pygame_sink():
    """Create a :class:`PygameSink` with default arguments.

    Returns:
        PygameSink or None: The sink, or ``None`` if pygame is not installed.
    """
    try:
        return PygameSink()
    except ImportError:
        return None
