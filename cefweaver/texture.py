"""Read the pixels of a shared texture from ``RenderHandler.on_accelerated_paint()``.

On Linux a shared texture consists of dmabuf file descriptors owned by CEF. They are valid
only during the ``on_accelerated_paint()`` call.
"""

import errno
import mmap
import struct
import sys

if sys.platform != "win32":
    import fcntl

# <linux/dma-buf.h>: DMA_BUF_IOCTL_SYNC = _IOW('b', 0, struct dma_buf_sync { __u64 flags; })
_DMA_BUF_IOCTL_SYNC = 0x40086200
_SYNC_START_READ = 0 | 1
_SYNC_END_READ = 4 | 1


def read_plane(plane, length=None):
    """Copy a plane of a shared texture to ``bytes``.

    Only a linear texture (``info.modifier == 0``) can be read this way. A tiled texture is
    meant for the GPU; import it with ``EGL_EXT_image_dma_buf_import`` on a duplicate of the
    descriptor (``os.dup(plane.fd)``).

    Args:
        plane: A plane of the shared texture, with ``fd``, ``offset``, ``stride`` and
            ``size`` attributes.
        length (int, optional): The number of bytes to read from ``plane.offset``. Defaults
            to ``plane.size``.

    Returns:
        bytes: The ``length`` bytes of the plane, with rows ``plane.stride`` bytes apart.

    Raises:
        OSError: If the descriptor is invalid or cannot be mapped (a tiled texture).
        NotImplementedError: On Windows, which provides no dmabuf descriptors.

    Note:
        Call inside ``on_accelerated_paint()``; the descriptor is invalid afterwards.
    """
    if sys.platform == "win32":
        raise NotImplementedError("shared textures are dmabuf file descriptors; Windows gives none")
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
