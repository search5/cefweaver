    def to_bytes(self):
        """A copy of the shared memory as bytes (CEF owns the memory and can free it: it is not lent out)."""
        cdef CefSharedMemoryRegion* _p = self._ptr()
        cdef string _data
        with nogil:
            _data = CefWeaverSharedMemoryRead(_p)
        return <bytes>_data
