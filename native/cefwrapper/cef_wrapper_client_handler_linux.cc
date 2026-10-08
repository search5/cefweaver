#include "cef_wrapper_client_handler.h"

#include <X11/Xatom.h>
#include <X11/Xlib.h>

#include <string>

#include "include/cef_browser.h"

namespace {

// The top-level window of the browser: CEF creates one for an Alloy style browser that
// has no parent window, and what GetWindowHandle() returns may be a child of it.
::Window TopLevelWindow(::Display* display, ::Window window) {
  for (;;) {
    ::Window root = 0;
    ::Window parent = 0;
    ::Window* children = nullptr;
    unsigned int count = 0;
    if (!XQueryTree(display, window, &root, &parent, &children, &count)) {
      return window;
    }
    if (children) {
      XFree(children);
    }
    if (parent == 0 || parent == root) {
      return window;
    }
    window = parent;
  }
}

}  // namespace

void CefWrapperClientHandler::PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                                        const CefString& title) {
  // An Alloy style window has no title of its own (a Chrome style one sets it from the
  // page), so the wrapper sets it, the way cefsimple does.
  ::Display* display = cef_get_xdisplay();
  ::Window window = browser->GetHost()->GetWindowHandle();
  if (!display || !window) {
    return;
  }
  window = TopLevelWindow(display, window);

  const std::string text = title.ToString();
  XChangeProperty(display, window, XInternAtom(display, "_NET_WM_NAME", False),
                  XInternAtom(display, "UTF8_STRING", False), 8, PropModeReplace,
                  reinterpret_cast<const unsigned char*>(text.c_str()),
                  static_cast<int>(text.size()));
  XStoreName(display, window, text.c_str());
  XFlush(display);
}
