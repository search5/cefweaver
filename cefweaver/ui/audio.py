"""The sound of a page, for the application: what a sink is and how the planes CEF gives become samples.

CEF captures the sound of a page instead of playing it when the browser has an audio handler (``cefweaver.AudioHandler``):
it gives a block of 32 bit floats for every channel (planar). ``BrowserView(adapter, audio=sink)`` makes that handler
and passes the sound to ``sink``, which an application, a toolkit adapter (``audio_sink()``) or ``PygameSink`` provides.
Without a sink CEF plays the sound itself.

A sink has three methods and is called in the thread of CEF's audio stream, so it must not wait::

    sink.start(sample_rate, channels)     # a stream begins (it may begin again later)
    sink.write(samples, frames)           # frames * channels float32, little endian, interleaved (L R L R ...)
    sink.stop()                           # the stream is over, or failed
"""

import array
import sys


def interleave(planes):
    """The planes (a float32 ``memoryview`` for every channel) as one buffer of interleaved samples: (bytes, frames)."""
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
    """The interleaved float32 samples (bytes) times ``volume``; the same bytes when it is 1.0."""
    if volume == 1.0:
        return samples
    data = array.array("f", samples)
    for index in range(len(data)):
        data[index] *= volume
    return data.tobytes()


def is_sink(candidate):
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
    """A sink that plays through pygame (``pip install pygame``), for toolkits that cannot play a stream themselves.

    It opens the audio device with ``pygame._sdl2.audio.AudioDevice`` (a callback that the device calls for the next
    block: a latency of a few blocks, so that the sound stays with the picture) and keeps what ``write`` gives in a ring
    that holds at most ``max_latency`` seconds (older sound is dropped when the application cannot keep up).
    ``volume`` (0.0 to 1.0) is applied to the samples. A little sound (``prebuffer`` seconds) is collected before it is
    played, and again after the ring ran empty, so that the jitter of the packets is not heard. ``stats()`` tells what
    happened.

    pygame starts the audio of SDL through its mixer, which holds the device too; the SDL audio driver ``dummy`` (no
    sound card) allows a device to be opened once only, so the sink fails to start there, which the view reports
    (``BrowserView.on_audio_error``).
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
        """Frames written and consumed, blocks that found nothing to play (``underruns``) and frames dropped."""
        with self._lock:
            return dict(self._counters, queued=len(self._ring) // (4 * max(1, self._channels)))


def pygame_sink():
    """A ``PygameSink`` if pygame is installed, else None."""
    try:
        return PygameSink()
    except ImportError:
        return None
