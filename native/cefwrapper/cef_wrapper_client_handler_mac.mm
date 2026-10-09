#include "cef_wrapper_client_handler.h"
#include "global_vars.h"
#include "runtime.h"

#import <Cocoa/Cocoa.h>

#include <string>

#include "include/cef_browser.h"

bool CefWrapperClientHandler::PlatformCloseFinishing(CefRefPtr<CefBrowser> browser) {
  std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
  auto it = g_ChildViewBrowsers.find(browser->GetIdentifier());
  return it != g_ChildViewBrowsers.end() && it->second == 2;
}

bool CefWrapperClientHandler::PlatformCloseView(CefRefPtr<CefBrowser> browser) {
  // Every browser with a window: a child of the application's view (CefApp.parent_view) or in a
  // window of CEF's own. CEF's way of finishing the close, performClose: of the window, did not
  // end with OnBeforeClose in a Python process (the window closed, but the browser's view was
  // never released), and in a window of the application it would close all of it. So the view
  // leaves its window and CloseBrowser(true) completes the close. See CefWeaverFlushClosedViews().
  int phase;
  {
    std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
    auto it = g_ChildViewBrowsers.find(browser->GetIdentifier());
    if (it == g_ChildViewBrowsers.end()) {
      return false;
    }
    phase = it->second;
    if (phase == 0) {
      it->second = 1;
    }
  }
  if (phase == 2) {
    // The view has left (CefWeaverFlushClosedViews() asked again): there is no window to close.
    return false;
  }
  if (phase == 0) {
    // Not at once: CEF is in the middle of the close. The view leaves when the application's
    // Cocoa loop turns (the main queue) or, in shutdown(), by its wait for the browsers.
    NSView* view = (__bridge NSView*)browser->GetHost()->GetWindowHandle();
    if (view) {
      CefWeaverQueueClosedView((__bridge void*)view, browser->GetIdentifier());
      dispatch_async(dispatch_get_main_queue(), ^{
        CefWeaverFlushClosedViews();
      });
    }
  }
  // True: DoClose() returning false would send performClose: to the window.
  return true;
}

void CefWrapperClientHandler::PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                                                  const CefString& title) {
  // An Alloy style window has no title of its own, so the wrapper sets it, the way cefsimple
  // does. An offscreen browser has no view and so no window.
  NSView* view = (__bridge NSView*)browser->GetHost()->GetWindowHandle();
  NSWindow* window = [view window];
  if (!window) {
    return;
  }
  NSString* text = [NSString stringWithUTF8String:title.ToString().c_str()];
  [window setTitle:text ? text : @""];
}
