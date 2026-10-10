"""What is generated.

The generator is meant to cover the whole CEF API eventually. Until then this file
lists the classes and functions that are generated, so a stage of the work is a
change to these lists (and, when a stage needs a new kind of type, to types.py).
"""

# Classes implemented by CEF and used by the application.
LIBRARY_CLASSES = [
    "CefRequest",
    "CefResponse",
    "CefCallback",
    "CefResourceReadCallback",
    "CefResourceSkipCallback",
    "CefBrowser",
    "CefBrowserHost",
    "CefFrame",
    "CefDisplay",
    "CefImage",
    # Navigation entries, certificates, a server, the media router, updates (2026-10-10)
    "CefNavigationEntry",
    "CefX509Certificate",
    "CefX509CertPrincipal",
    "CefSSLStatus",
    "CefServer",
    "CefMediaRouter",
    "CefMediaRoute",
    "CefMediaSink",
    "CefMediaSource",
    "CefComponent",
    "CefComponentUpdater",
    "CefSharedMemoryRegion",
    "CefSharedProcessMessageBuilder",
    "CefSelectClientCertificateCallback",
    # The Views framework: windows, panels, buttons, text fields, layouts (a subclass is a Python subclass)
    "CefView",
    "CefPanel",
    "CefWindow",
    "CefBrowserView",
    "CefButton",
    "CefLabelButton",
    "CefMenuButton",
    "CefMenuButtonPressedLock",
    "CefTextfield",
    "CefScrollView",
    "CefLayout",
    "CefBoxLayout",
    "CefFillLayout",
    "CefOverlayController",
    "CefMenuModel",
    "CefPrintSettings",
    "CefContextMenuParams",
    "CefRunContextMenuCallback",
    "CefRunQuickMenuCallback",
    "CefProcessMessage",
    "CefValue",
    "CefListValue",
    "CefDictionaryValue",
    "CefBinaryValue",
    "CefTaskManager",
    "CefJSDialogCallback",
    "CefFileDialogCallback",
    "CefBeforeDownloadCallback",
    "CefDownloadItemCallback",
    "CefDownloadItem",
    "CefPrintDialogCallback",
    "CefPrintJobCallback",
    "CefAuthCallback",
    "CefSSLInfo",
    "CefUnresponsiveProcessCallback",
    "CefPostData",
    "CefPostDataElement",
    "CefStreamReader",
    "CefStreamWriter",
    "CefZipReader",
    "CefRegistration",
    "CefCookieManager",
    "CefRequestContext",
    "CefURLRequest",
    "CefCommandLine",
    "CefDragData",
    "CefMediaAccessCallback",
    "CefPermissionPromptCallback",
]

# Classes implemented by the application (handlers); CEF calls them.
CLIENT_CLASSES = [
    "CefResourceHandler",
    "CefSchemeHandlerFactory",
    "CefClient",
    "CefLoadHandler",
    "CefLifeSpanHandler",
    "CefDisplayHandler",
    "CefMenuModelDelegate",
    "CefDragHandler",
    "CefContextMenuHandler",
    "CefRenderHandler",
    "CefFocusHandler",
    "CefJSDialogHandler",
    "CefDialogHandler",
    "CefDownloadHandler",
    "CefKeyboardHandler",
    "CefPrintHandler",
    "CefRequestHandler",
    "CefResourceRequestHandler",
    "CefReadHandler",
    "CefWriteHandler",
    "CefPdfPrintCallback",
    "CefCookieVisitor",
    "CefSetCookieCallback",
    "CefDeleteCookiesCallback",
    "CefCompletionCallback",
    "CefCookieAccessFilter",
    "CefPermissionHandler",
    "CefAudioHandler",
    "CefStringVisitor",
    "CefRunFileDialogCallback",
    "CefDevToolsMessageObserver",
    "CefRequestContextHandler",
    "CefURLRequestClient",
    "CefTask",
    "CefDownloadImageCallback",
    # Handlers and callbacks: find, frames, Chrome commands, accessibility, navigation entries, response filters,
    # a server, DNS, observers, media, tracing (2026-10-10)
    "CefFindHandler",
    "CefFrameHandler",
    "CefCommandHandler",
    "CefAccessibilityHandler",
    "CefNavigationEntryVisitor",
    "CefResponseFilter",
    "CefServerHandler",
    "CefResolveCallback",
    "CefSettingObserver",
    "CefPreferenceObserver",
    "CefMediaObserver",
    "CefMediaRouteCreateCallback",
    "CefMediaSinkDeviceInfoCallback",
    "CefComponentUpdateCallback",
    "CefEndTracingCallback",
    # The delegates of the Views (each has the methods of its parents)
    "CefViewDelegate",
    "CefPanelDelegate",
    "CefWindowDelegate",
    "CefBrowserViewDelegate",
    "CefButtonDelegate",
    "CefMenuButtonDelegate",
    "CefTextfieldDelegate",
]

# Static functions (and global functions: the class is "") that end the process with a segmentation fault when CEF
# has not been initialized: they are called only after CefApp.initialize() (a RuntimeError before it). Measured:
# CefImage.CreateImage() (its object cannot be freed) and CefIsRTL() (it needs the i18n data).
NEEDS_CEF_RUNNING = {
    ("CefImage", "CreateImage"): "an Image can only be made after CefApp.initialize()",
    ("", "CefIsRTL"): "is_rtl() can only be called after CefApp.initialize()",     # a function: no class
}

# Methods that are written by hand and added to a generated class (the generator cannot express them: CEF's
# window description, memory that CEF owns). {CEF class: file name in tools/gen/extras/}: `<name>.pxi` is
# the Cython code of the methods (indented as in the class), `<name>.pyi` their stubs.
EXTRA_METHODS = {
    "CefBrowserHost": "browser_host",
    "CefSharedMemoryRegion": "shared_memory_region",
    "CefSharedProcessMessageBuilder": "shared_process_message_builder",
}

# Global functions.
FUNCTIONS = [
    "CefRegisterSchemeHandlerFactory",
    "CefClearSchemeHandlerFactories",
    "CefGetMimeType",
    "CefPostTask",
    "CefPostDelayedTask",
    "CefCurrentlyOn",
    "CefAddCrossOriginWhitelistEntry",
    "CefRemoveCrossOriginWhitelistEntry",
    "CefClearCrossOriginWhitelist",
    "CefIsCertStatusError",
    "CefFormatUrlForSecurityDisplay",
    "CefGetExtensionsForMimeType",
    "CefLoadCRLSetsFile",
    "CefBeginTracing",
    "CefEndTracing",
    "CefSetCrashKeyValue",
    "CefCrashReportingEnabled",
    "CefIsRTL",
    "CefGetPath",
    "CefNowFromSystemTraceTime",
]


class Scope:
    def __init__(self, model, library, client, functions):
        self.model = model
        self._library = set(library)
        self._client = set(client)
        self.functions = list(functions)
        for name in self._library | self._client:
            if name not in model.classes:
                raise KeyError("%s is not in the CEF headers" % name)
        for name in self._library:
            assert model.classes[name].is_library_side(), name
        for name in self._client:
            assert model.classes[name].is_client_side(), name

    @classmethod
    def current(cls, model):
        return cls(model, LIBRARY_CLASSES, CLIENT_CLASSES, FUNCTIONS)

    @classmethod
    def everything(cls, model):
        """Every class and function, to measure the type support of the generator."""
        library = [n for n, c in model.classes.items() if c.is_library_side()]
        client = [n for n, c in model.classes.items() if c.is_client_side()]
        return cls(model, library, client, list(model.functions))

    def python_parent(self, name):
        """The CEF parent of a library class that is a generated library class too (CefPanel -> CefView), else
        None. Such a class is a Python subclass of its parent and has only its own methods; the others
        (CefRequestContext, whose parent CefPreferenceManager is not generated) are one class with the methods of
        their parents."""
        if name not in self._library:
            return None
        parent = self.model.classes[name].get_parent_name()
        return parent if parent in self._library else None

    def python_children(self, name):
        """The generated library classes whose Python parent is `name`, in name order."""
        return [n for n in sorted(self._library) if self.python_parent(n) == name]

    def in_hierarchy(self, name):
        """True for a class that has a Python parent or Python children (the Views: CefView and the classes
        that derive from it): its methods use a typed accessor and its objects are wrapped by their real type."""
        return self.python_parent(name) is not None or bool(self.python_children(name))

    def is_library(self, name):
        return name in self._library

    def is_client(self, name):
        return name in self._client

    @property
    def library_classes(self):
        """The generated library classes by name, a parent before its subclasses in this order of the output
        (the parent has to be defined first: `cdef class Panel(View)`)."""
        def depth(name):
            parent = self.python_parent(name)
            return 0 if parent is None else 1 + depth(parent)
        return [self.model.classes[n] for n in sorted(self._library, key=lambda n: (depth(n), n))]

    @property
    def client_classes(self):
        return [self.model.classes[n] for n in sorted(self._client)]
