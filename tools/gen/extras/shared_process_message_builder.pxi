    def write(self, size_t offset, data):
        """Write the bytes of ``data`` into the shared memory at ``offset``. Returns False if they do not fit
        (the memory is copied into: CEF owns it and it is not lent out)."""
        cdef const unsigned char[::1] _view = data
        cdef size_t _size = _view.shape[0]
        cdef CefSharedProcessMessageBuilder* _p = self._ptr()
        cdef cpp_bool _ok
        if _size == 0:
            return True
        with nogil:
            _ok = CefWeaverSharedBuilderWrite(_p, offset, &_view[0], _size)
        return _ok
