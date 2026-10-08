#ifndef GLOBAL_VARS_H
#define GLOBAL_VARS_H

#include <atomic>

inline bool g_IsRunning = false;

// Whether the wrapper adds "Show DevTools" and the like to the context menu (off by default).
// It is read when a menu is built and when a command is run, on the UI thread.
inline std::atomic<bool> g_DevToolsMenuEnabled{false};

#endif // GLOBAL_VARS_H
