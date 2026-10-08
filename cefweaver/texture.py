"""Reading the pixels of a shared texture (``RenderHandler.on_accelerated_paint()``).

On Linux a shared texture is made of dmabuf file descriptors that CEF owns: they are valid
**only during the call**, and the texture is reused afterwards. ``read_plane()`` copies a plane
to ``bytes`` inside the call. That works for a linear texture (``info.modifier == 0``); a
texture in a driver's tiled layout is meant for the GPU (import it with
``EGL_EXT_image_dma_buf_import`` on a duplicate of the descriptor, ``os.dup(plane.fd)``).
"""

import errno
import fcntl
import mmap
import struct

# <linux/dma-buf.h>: DMA_BUF_IOCTL_SYNC = _IOW('b', 0, struct dma_buf_sync { __u64 flags; })
_DMA_BUF_IOCTL_SYNC = 0x40086200
_SYNC_START_READ = 0 | 1
_SYNC_END_READ = 4 | 1


def read_plane(plane, length=None):
    """The bytes of a plane of a shared texture: ``length`` bytes (default ``plane.size``) from
    ``plane.offset``, rows ``plane.stride`` bytes apart. Raises ``OSError`` if the descriptor
    cannot be mapped (a tiled texture) or is not valid any more."""
    length = plane.size if length is None else length
    if plane.fd < 0:
        raise OSError(errno.EBADF, "not a file descriptor")
    with mmap.mmap(plane.fd, plane.offset + length, flags=mmap.MAP_SHARED, prot=mmap.PROT_READ) as mapped:
        try:  # the GPU may still write: tell the kernel that the CPU reads
            fcntl.ioctl(plane.fd, _DMA_BUF_IOCTL_SYNC, struct.pack("Q", _SYNC_START_READ))
        except OSError:
            pass
        try:
            return bytes(mapped[plane.offset:plane.offset + length])
        finally:
            try:
                fcntl.ioctl(plane.fd, _DMA_BUF_IOCTL_SYNC, struct.pack("Q", _SYNC_END_READ))
            except OSError:
                pass
