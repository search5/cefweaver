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
]

# Global functions.
FUNCTIONS = [
    "CefRegisterSchemeHandlerFactory",
    "CefClearSchemeHandlerFactories",
    "CefGetMimeType",
    "CefPostTask",
    "CefPostDelayedTask",
    "CefCurrentlyOn",
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

    def is_library(self, name):
        return name in self._library

    def is_client(self, name):
        return name in self._client

    @property
    def library_classes(self):
        return [self.model.classes[n] for n in sorted(self._library)]

    @property
    def client_classes(self):
        return [self.model.classes[n] for n in sorted(self._client)]
