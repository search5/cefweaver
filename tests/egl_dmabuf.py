"""Test support: reads a dmabuf (a shared texture of CEF) the way a GL toolkit would, through
EGL_EXT_image_dma_buf_import and an external texture drawn into a framebuffer (ctypes only).
The tests run this file's text in the CEF process (exec); it is not imported."""
import ctypes, os

EGL_PLATFORM_X11_KHR = 0x31D5
EGL_OPENGL_ES_API = 0x30A0
EGL_NONE = 0x3038
EGL_WIDTH, EGL_HEIGHT = 0x3057, 0x3056
EGL_LINUX_DMA_BUF_EXT = 0x3270
EGL_LINUX_DRM_FOURCC_EXT = 0x3271
EGL_DMA_BUF_PLANE0_FD_EXT, EGL_DMA_BUF_PLANE0_OFFSET_EXT, EGL_DMA_BUF_PLANE0_PITCH_EXT = 0x3272, 0x3273, 0x3274
EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT = 0x3443, 0x3444
EGL_CONTEXT_CLIENT_VERSION = 0x3098
DRM_FORMAT_ARGB8888 = 0x34325241  # 'AR24': BGRA in memory on little endian


class Reader:
    def __init__(self):
        self.egl = ctypes.CDLL("libEGL.so.1")
        self.gles = ctypes.CDLL("libGLESv2.so.2")
        x11 = ctypes.CDLL("libX11.so.6")
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x = x11.XOpenDisplay(None)
        e = self.egl
        e.eglGetProcAddress.restype = ctypes.c_void_p
        e.eglGetProcAddress.argtypes = [ctypes.c_char_p]
        get_platform_display = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)(
            e.eglGetProcAddress(b"eglGetPlatformDisplayEXT") or e.eglGetProcAddress(b"eglGetPlatformDisplay"))
        self.display = get_platform_display(EGL_PLATFORM_X11_KHR, self.x, None)
        major, minor = ctypes.c_int(), ctypes.c_int()
        e.eglInitialize.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        assert e.eglInitialize(self.display, ctypes.byref(major), ctypes.byref(minor)), "eglInitialize"
        e.eglBindAPI(EGL_OPENGL_ES_API)
        e.eglCreateContext.restype = ctypes.c_void_p
        e.eglCreateContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        attribs = (ctypes.c_int * 3)(EGL_CONTEXT_CLIENT_VERSION, 2, EGL_NONE)
        self.context = e.eglCreateContext(self.display, None, None, attribs)   # EGL_NO_CONFIG_KHR is 0 on NVIDIA/Mesa
        assert self.context, "eglCreateContext"
        e.eglMakeCurrent.argtypes = [ctypes.c_void_p] * 4
        assert e.eglMakeCurrent(self.display, None, None, self.context), "eglMakeCurrent (surfaceless)"
        self.create_image = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
                                             ctypes.c_void_p, ctypes.c_void_p)(e.eglGetProcAddress(b"eglCreateImageKHR"))
        self.destroy_image = ctypes.CFUNCTYPE(ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)(e.eglGetProcAddress(b"eglDestroyImageKHR"))
        self.target = ctypes.CFUNCTYPE(None, ctypes.c_uint, ctypes.c_void_p)(e.eglGetProcAddress(b"glEGLImageTargetTexture2DOES"))

    VERTEX = b"attribute vec2 p; varying vec2 uv; void main() { uv = p * 0.5 + 0.5; gl_Position = vec4(p, 0.0, 1.0); }"
    FRAGMENT = (b"#extension GL_OES_EGL_image_external : require\nprecision mediump float; varying vec2 uv; "
                b"uniform samplerExternalOES t; void main() { gl_FragColor = texture2D(t, uv); }")

    def _program(self):
        g = self.gles
        def shader(kind, source):
            handle = g.glCreateShader(kind)
            pointer = ctypes.c_char_p(source)
            g.glShaderSource(handle, 1, ctypes.byref(pointer), None)
            g.glCompileShader(handle)
            status = ctypes.c_int()
            g.glGetShaderiv(handle, 0x8B81, ctypes.byref(status))
            if not status.value:
                log = ctypes.create_string_buffer(2048)
                g.glGetShaderInfoLog(handle, 2048, None, log)
                raise AssertionError("shader: " + log.value.decode())
            return handle
        program = g.glCreateProgram()
        g.glAttachShader(program, shader(0x8B31, self.VERTEX))
        g.glAttachShader(program, shader(0x8B30, self.FRAGMENT))
        g.glBindAttribLocation(program, 0, b"p")
        g.glLinkProgram(program)
        return program

    def read(self, plane, modifier, width, height):
        g = self.gles
        attribs = (ctypes.c_int * 19)(
            EGL_WIDTH, width, EGL_HEIGHT, height, EGL_LINUX_DRM_FOURCC_EXT, DRM_FORMAT_ARGB8888,
            EGL_DMA_BUF_PLANE0_FD_EXT, plane.fd, EGL_DMA_BUF_PLANE0_OFFSET_EXT, plane.offset,
            EGL_DMA_BUF_PLANE0_PITCH_EXT, plane.stride,
            EGL_DMA_BUF_PLANE0_MODIFIER_LO_EXT, modifier & 0xFFFFFFFF, EGL_DMA_BUF_PLANE0_MODIFIER_HI_EXT, modifier >> 32,
            EGL_NONE, EGL_NONE, EGL_NONE)
        image = self.create_image(self.display, None, EGL_LINUX_DMA_BUF_EXT, None, attribs)
        assert image, "eglCreateImageKHR: error 0x%x" % self.egl.eglGetError()
        source, target, fbo = ctypes.c_uint(), ctypes.c_uint(), ctypes.c_uint()
        g.glGenTextures(1, ctypes.byref(source))
        g.glBindTexture(0x8D65, source)                       # GL_TEXTURE_EXTERNAL_OES
        self.target(0x8D65, image)
        g.glTexParameteri(0x8D65, 0x2801, 0x2600)             # NEAREST
        g.glTexParameteri(0x8D65, 0x2800, 0x2600)
        g.glGenTextures(1, ctypes.byref(target))
        g.glBindTexture(0x0DE1, target)
        g.glTexImage2D(0x0DE1, 0, 0x1908, width, height, 0, 0x1908, 0x1401, None)
        g.glGenFramebuffers(1, ctypes.byref(fbo))
        g.glBindFramebuffer(0x8D40, fbo)
        g.glFramebufferTexture2D(0x8D40, 0x8CE0, 0x0DE1, target, 0)
        status = g.glCheckFramebufferStatus(0x8D40)
        assert status == 0x8CD5, "framebuffer status 0x%x" % status
        program = self._program()
        g.glUseProgram(program)
        g.glViewport(0, 0, width, height)
        g.glActiveTexture(0x84C0)
        g.glBindTexture(0x8D65, source)
        g.glUniform1i(g.glGetUniformLocation(program, b"t"), 0)
        quad = (ctypes.c_float * 8)(-1, -1, 1, -1, -1, 1, 1, 1)
        g.glEnableVertexAttribArray(0)
        g.glVertexAttribPointer(0, 2, 0x1406, 0, 0, quad)
        g.glDrawArrays(0x0005, 0, 4)                          # TRIANGLE_STRIP
        buffer = ctypes.create_string_buffer(width * height * 4)
        g.glReadPixels(0, 0, width, height, 0x1908, 0x1401, buffer)   # RGBA bytes
        error = g.glGetError()
        assert error == 0, "GL error 0x%x" % error
        g.glDeleteProgram(program)
        g.glDeleteFramebuffers(1, ctypes.byref(fbo))
        g.glDeleteTextures(1, ctypes.byref(source))
        g.glDeleteTextures(1, ctypes.byref(target))
        self.destroy_image(self.display, image)
        return buffer.raw   # RGBA, rows from the bottom (as GL has them), width * 4 bytes each
