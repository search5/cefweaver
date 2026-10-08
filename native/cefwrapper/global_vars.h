#ifndef GLOBAL_VARS_H
#define GLOBAL_VARS_H

#include <atomic>

inline bool g_IsRunning = false;

// Whether the wrapper adds "Show DevTools" and the like to the context menu (off by default).
// It is read when a menu is built and when a command is run, on the UI thread.
inline std::atomic<bool> g_DevToolsMenuEnabled{false};

// Offscreen (windowless) rendering: the browser draws into a buffer that the user's render
// handler receives (on_paint), and has no window. Read when the browser is created.
inline std::atomic<bool> g_Offscreen{false};
// Frames per second of an offscreen browser (CEF accepts 1 to 60).
inline std::atomic<int> g_WindowlessFrameRate{30};

#endif // GLOBAL_VARS_H
