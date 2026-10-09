#include "cef_wrapper_client_handler.h"

#include <X11/Xatom.h>
#include <X11/Xlib.h>

#include <string>

#include "include/cef_browser.h"



bool CefWrapperClientHandler::PlatformCloseView(CefRefPtr<CefBrowser>) { return false; }
bool CefWrapperClientHandler::PlatformCloseFinishing(CefRefPtr<CefBrowser>) { return false; }

void CefWrapperClientHandler::PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                                        const CefString& title) {
  // An Alloy style window has no title of its own (a Chrome style one sets it from the
  // page), so the wrapper sets it, the way cefsimple does. GetWindowHandle() is the
  // top-level window CEF created; a window manager reparents it into its own frame window,
  // which must not be used (the title is read from the client window).
  //
  // Only an X11 browser has an X11 window. The window is checked first because on native
  // Wayland there is no X11 connection and cef_get_xdisplay() ends the process (SIGTRAP).
  ::Window window = browser->GetHost()->GetWindowHandle();
  if (!window) {
    return;
  }
  ::Display* display = cef_get_xdisplay();
  if (!display) {
    return;
  }

  const std::string text = title.ToString();
  XChangeProperty(display, window, XInternAtom(display, "_NET_WM_NAME", False),
                  XInternAtom(display, "UTF8_STRING", False), 8, PropModeReplace,
                  reinterpret_cast<const unsigned char*>(text.c_str()),
                  static_cast<int>(text.size()));
  XStoreName(display, window, text.c_str());
  XFlush(display);
}
