#include "runtime.h"

#import <Cocoa/Cocoa.h>
#import <objc/message.h>
#import <objc/runtime.h>

#include <dlfcn.h>

#include <cstdio>
#include <filesystem>
#include <mutex>
#include <vector>

#include "global_vars.h"
#include "include/cef_application_mac.h"
#include "include/cef_browser.h"
#include "include/wrapper/cef_library_loader.h"

namespace {

const char kMainBundle[] = "cefsubprocess.app";
const char kFramework[] = "Chromium Embedded Framework.framework";
const char kHelper[] = "cefsubprocess Helper";

BOOL g_handling_send_event = NO;
IMP g_original_send_event = nullptr;

BOOL IsHandlingSendEvent(id, SEL) { return g_handling_send_event; }

void SetHandlingSendEvent(id, SEL, BOOL handling) { g_handling_send_event = handling; }

// Chromium's message loop asks NSApp whether an event is being sent, to decide whether it
// may run nested work. -sendEvent: is where the answer changes.
void SendEvent(id self, SEL command, NSEvent* event) {
  CefScopedSendingEvent sending_event_scoper;
  reinterpret_cast<void (*)(id, SEL, NSEvent*)>(g_original_send_event)(self, command, event);
}

}  // namespace

std::string CefWeaverModuleDir() {
  Dl_info info;
  if (dladdr(reinterpret_cast<void*>(&CefWeaverModuleDir), &info) && info.dli_fname) {
    return std::filesystem::path(info.dli_fname).parent_path().string();
  }
  return std::string();
}

std::string CefWeaverMainBundlePath() {
  return (std::filesystem::path(CefWeaverModuleDir()) / kMainBundle).string();
}

std::string CefWeaverFrameworkDir() {
  return (std::filesystem::path(CefWeaverMainBundlePath()) / "Contents" / "Frameworks" /
          kFramework)
      .string();
}

std::string CefWeaverHelperPath() {
  const std::filesystem::path helper_app =
      std::filesystem::path(CefWeaverMainBundlePath()) / "Contents" / "Frameworks" /
      (std::string(kHelper) + ".app");
  return (helper_app / "Contents" / "MacOS" / kHelper).string();
}

namespace {
struct ClosedView {
  NSView* view;
  int browser_id;
};
std::vector<ClosedView>& ClosedViews() {
  static std::vector<ClosedView> views;
  return views;
}
std::mutex& ClosedViewsMutex() {
  static std::mutex mutex;
  return mutex;
}
}  // namespace

void CefWeaverQueueClosedView(void* view, int browser_id) {
  std::lock_guard<std::mutex> lock(ClosedViewsMutex());
  ClosedViews().push_back({(__bridge NSView*)view, browser_id});
}

void CefWeaverDoMessageLoopWork() {
  @autoreleasepool {
    CefDoMessageLoopWork();
  }
}

void CefWeaverPumpApplicationEvents() {
  @autoreleasepool {
    for (int i = 0; i < 100; ++i) {                // bounded: an event can post another
      NSEvent* event = [NSApp nextEventMatchingMask:NSEventMaskAny
                                          untilDate:[NSDate distantPast]
                                             inMode:NSDefaultRunLoopMode
                                            dequeue:YES];
      if (!event) {
        break;
      }
      [NSApp sendEvent:event];
    }
    // The sources of the run loop too (performSelector:onMainThread: of CEF's window close, the
    // main queue): nextEvent does not run them when no event is waiting.
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0, true);
  }
}

void CefWeaverFlushClosedViews() {
  @autoreleasepool {
    std::vector<ClosedView> views;
    {
      std::lock_guard<std::mutex> lock(ClosedViewsMutex());
      views.swap(ClosedViews());
    }
    for (const ClosedView& closed : views) {
      NSWindow* own_window = nil;
      {
        std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
        if (g_OwnWindowBrowsers.count(closed.browser_id)) {
          own_window = [closed.view window];
        }
      }
      [closed.view removeFromSuperview];
      [own_window close];            // the window CEF made for it: nothing is left in it
      // The view is out of the window: with nothing to close but the browser, CEF can finish.
      CefRefPtr<CefBrowser> browser;
      {
        std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
        auto it = g_ChildViewBrowsers.find(closed.browser_id);
        if (it != g_ChildViewBrowsers.end()) {
          it->second = 2;
        }
      }
      browser = CefBrowserHost::GetBrowserByIdentifier(closed.browser_id);
      if (browser) {
        browser->GetHost()->CloseBrowser(true);
      }
    }
  }
}

void CefWeaverViewSize(uintptr_t view, int* width, int* height) {
  *width = *height = 0;
  if (view == 0) {
    return;
  }
  NSView* ns_view = (__bridge NSView*)reinterpret_cast<void*>(view);
  if (![ns_view isKindOfClass:[NSView class]]) {
    return;
  }
  const NSRect bounds = [ns_view bounds];
  *width = static_cast<int>(bounds.size.width);
  *height = static_cast<int>(bounds.size.height);
}

bool CefWeaverLoadRuntime() {
  static bool loaded = false;
  if (loaded) {
    return true;
  }
  const std::string library =
      (std::filesystem::path(CefWeaverFrameworkDir()) / "Chromium Embedded Framework").string();
  if (!std::filesystem::exists(library)) {
    std::fprintf(stderr, "cefweaver: the CEF framework is missing: %s\n", library.c_str());
    return false;
  }
  if (!cef_load_library(library.c_str())) {
    std::fprintf(stderr, "cefweaver: could not load the CEF framework: %s\n", library.c_str());
    return false;
  }
  loaded = true;
  return true;
}

void CefWeaverPrepareApplication() {
  @autoreleasepool {
    // A toolkit (Qt, Tk, ...) may have made NSApp already; its class is kept.
    [NSApplication sharedApplication];
    Class application_class = [NSApp class];
    if (class_conformsToProtocol(application_class, @protocol(CefAppProtocol))) {
      return;
    }

    // CEF only calls the methods, but it also checks the protocols.
    class_addMethod(application_class, @selector(isHandlingSendEvent),
                    reinterpret_cast<IMP>(IsHandlingSendEvent), "c@:");
    class_addMethod(application_class, @selector(setHandlingSendEvent:),
                    reinterpret_cast<IMP>(SetHandlingSendEvent), "v@:c");
    class_addProtocol(application_class, @protocol(CrAppProtocol));
    class_addProtocol(application_class, @protocol(CrAppControlProtocol));
    class_addProtocol(application_class, @protocol(CefAppProtocol));

    Method send_event = class_getInstanceMethod(application_class, @selector(sendEvent:));
    g_original_send_event = method_getImplementation(send_event);
    class_replaceMethod(application_class, @selector(sendEvent:),
                        reinterpret_cast<IMP>(SendEvent), method_getTypeEncoding(send_event));
  }
}
