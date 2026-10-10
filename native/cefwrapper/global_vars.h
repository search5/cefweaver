#ifndef GLOBAL_VARS_H
#define GLOBAL_VARS_H

#include <atomic>
#include <cstdint>
#include <mutex>
#include <map>
#include <set>

inline bool g_IsRunning = false;

// Whether the wrapper adds "Show DevTools" and the like to the context menu (off by default).
// It is read when a menu is built and when a command is run, on the UI thread.
inline std::atomic<bool> g_DevToolsMenuEnabled{false};

// Offscreen (windowless) rendering: the browser draws into a buffer that the user's render
// handler receives (on_paint), and has no window. Read when the browser is created.
inline std::atomic<bool> g_Offscreen{false};
// macOS: the NSView a windowed browser is made a child of (0: CEF makes a window of its own).
inline std::atomic<uintptr_t> g_ParentView{0};
// macOS: the identifiers of the browsers that are children of the application's NSView. They
// are taken out of it when they close. Guarded by g_ChildViewBrowsersMutex.
// The value is how far the close is: 0 not started, 1 the view is queued to leave, 2 it has left.
// Browsers with a window of CEF's own are in it too (with a negative phase: -1 not started ... see
// PlatformCloseView()).
inline std::map<int, int> g_ChildViewBrowsers;
inline std::set<int> g_OwnWindowBrowsers;
inline std::mutex g_ChildViewBrowsersMutex;
inline void ForgetChildViewBrowser(int browser_id) {
  std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
  g_ChildViewBrowsers.erase(browser_id);
  g_OwnWindowBrowsers.erase(browser_id);
}
// An offscreen browser paints nothing clear (default) or is opaque; the colour (ARGB) is
// CefSettings.background_color, which an opaque offscreen browser uses (0: white).
inline std::atomic<bool> g_Transparent{true};
// initialize(None): CEF starts without a first browser (the application makes its own, e.g. a Views BrowserView).
inline std::atomic<bool> g_NoFirstBrowser{false};
// An offscreen browser gives CEF's shared textures (dmabufs) to OnAcceleratedPaint() instead of
// pixels to OnPaint().
inline std::atomic<bool> g_SharedTexture{false};
inline std::atomic<unsigned int> g_BackgroundColor{0};
// Frames per second of an offscreen browser (CEF accepts 1 to 60).
inline std::atomic<int> g_WindowlessFrameRate{30};

#endif // GLOBAL_VARS_H
