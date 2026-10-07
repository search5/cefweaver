#include "cef_wrapper_client_handler.h"

#include "include/cef_browser.h"

void CefWrapperClientHandler::PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                                        const CefString& title) {
  // Not implemented: CEF owns the top-level X11 window in this configuration,
  // and the wrapper has no X11 dependency to set the title with.
}
