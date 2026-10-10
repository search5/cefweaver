    def show_dev_tools(self, int inspect_x=-1, int inspect_y=-1):
        """Open DevTools in a window of its own (CEF makes the window). If ``inspect_x`` and ``inspect_y``
        are both 0 or more, the element of the page at that point is inspected. ``has_dev_tools()`` tells
        whether DevTools are open and ``close_dev_tools()`` closes them. (CEF's ShowDevTools() takes a
        window description, a client and settings: this one has CEF's defaults.)"""
        cdef CefBrowserHost* _p = self._ptr()
        with nogil:
            CefWeaverShowDevTools(_p, inspect_x, inspect_y)
        return None
