#ifndef CEFWEAVER_RUNTIME_H_
#define CEFWEAVER_RUNTIME_H_

#include <cstdint>
#include <string>

#include "include/base/cef_build.h"
#include "include/cef_app.h"

// Platform runtime setup that has to happen before CEF is used.
//
// Only macOS needs it: libcef is not linked there but loaded from
// "Chromium Embedded Framework.framework" at run time (cef_load_library), and the
// application needs the Cocoa protocol CEF's message loop relies on. Elsewhere these
// are no-ops.

#if defined(OS_MAC)

// The directory of the Python extension module (where the CEF runtime is deployed).
std::string CefWeaverModuleDir();

// <module dir>/cefsubprocess.app: the stand-in for the main app bundle, which a Python
// process does not have. CEF finds the helper apps and the framework inside it.
std::string CefWeaverMainBundlePath();
std::string CefWeaverFrameworkDir();
std::string CefWeaverHelperPath();

// The size of an NSView (a window's content view, ...) in points. The view is given by its
// address as an integer. Zero if it is not a view.
void CefWeaverViewSize(uintptr_t view, int* width, int* height);

// Takes the NSViews of closed child-view browsers out of the application's view (the ones
// CefWrapperClientHandler::PlatformCloseView() queued). Main thread. It does not run the Cocoa
// loop: that would run the application's own callbacks (Python ones, too) at a moment when the
// GIL is not held.
void CefWeaverFlushClosedViews();

// Handles the pending events of the application (NSApp) without waiting: the clicks, keys and
// window operations of the windows CEF made, which only a turn of the Cocoa loop handles. For an
// application that polls CefDoMessageLoopWork() and has no loop of its own. The caller holds the
// GIL (an event can run Python code of a toolkit).
void CefWeaverPumpApplicationEvents();

// CefDoMessageLoopWork() inside an autorelease pool. A polling loop of Python has no pool on the
// main thread, so what AppKit and Chromium autorelease there (windows, views) would never be
// released, and a browser would never be seen as closed. (A Cocoa run loop drains a pool each turn.)
void CefWeaverDoMessageLoopWork();
void CefWeaverQueueClosedView(void* view, int browser_id);

// Loads the CEF framework (once). Must run before the first CEF call; it is called when the
// extension module is imported. Returns false (and says why on stderr) if it fails.
bool CefWeaverLoadRuntime();

// Makes the application object ready for CEF (main thread, before CefInitialize()): creates
// NSApp if it does not exist and gives its class the methods of CefAppProtocol.
void CefWeaverPrepareApplication();

#else

inline bool CefWeaverLoadRuntime() { return true; }
inline void CefWeaverFlushClosedViews() {}
inline void CefWeaverPumpApplicationEvents() {}
inline void CefWeaverDoMessageLoopWork() { CefDoMessageLoopWork(); }
inline void CefWeaverQueueClosedView(void*, int) {}
inline void CefWeaverViewSize(uintptr_t, int* width, int* height) { *width = *height = 0; }
inline void CefWeaverPrepareApplication() {}

#endif

#endif  // CEFWEAVER_RUNTIME_H_
