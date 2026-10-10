#ifndef LIBRARY_LIBRARY_H
#define LIBRARY_LIBRARY_H


#include "cef_wrapper_app.h"
#include "cef_wrapper_client_handler.h"
#include "include/cef_command_line.h"
#include "javascript_binding.h"
#include "query_router.h"
#include "app_hooks.h"
#include "include/cef_browser.h"
#include "include/cef_process_message.h"
#include <map>

class CefWrapper {
public:
  CefWrapper();
  // Returns false if CEF could not be initialized.
  bool InitCefSimple(std::string start_url);
  // Returns false if the code was not run (no page yet, or still loading).
  bool ExecuteJavascript(std::string code);
  void ShutdownCefSimple();
  bool IsRunning();
  bool IsReadyToExecuteJavascript();
  void DoCefMessageLoopWork();
  // macOS: the application's events too (see CefWeaverPumpApplicationEvents()); other platforms:
  // nothing. Holds no lock: call it with the GIL.
  void PumpApplicationEvents();
  bool ExternalMessagePump();
  void AddJavascriptBinding(std::string name,
                                js_binding_function_ptr jsNativeApiFunctionPtr);
  void AddJavascriptPythonBinding(std::string name,
      js_python_bindings_handler_function_ptr python_bindings_handler,
      js_python_callback_object_ptr python_callback_object);
  void SetCustomCefSubprocessPath(std::string cefsub_path);
  void SetCustomCefCachePath(std::string cef_cache_path);
  void SetCustomCefResourcesPath(std::string cef_resources_path);
  // Must be called before InitCefSimple(). An empty value adds a bare switch.
  void AddCommandLineSwitch(std::string name, std::string value);
  // Returns false if there is no browser yet.
  bool LoadUrl(std::string url);
  // The client whose display, life span and load handlers get the browser events. Must
  // be called before InitCefSimple(); an empty reference removes it.
  void SetClient(CefRefPtr<CefClient> client);
  // The wrapper's "Show DevTools" items in the context menu (off by default); can be changed
  // at any time and applies to the menus built afterwards.
  void SetDevToolsMenuEnabled(bool enabled);
  bool DevToolsMenuEnabled();
  // Offscreen rendering and its frame rate; read when the browser is created.
  // The fields of java-cef's CefSettings (see cefweaver/settings.py): read by InitCefSimple().
  void SetStringSetting(std::string name, std::string value);
  void SetIntSetting(std::string name, long long value);
  void SetOffscreen(bool enabled);
  // A further browser (java-cef's createBrowser); offscreen and transparent: -1 is the app's
  // setting. Empty when CEF does not run, the first browser does not exist yet, or the thread
  // is not the UI thread.
  CefRefPtr<CefBrowser> CreateBrowser(std::string url, int offscreen, int transparent,
                                      CefRefPtr<CefRequestContext> request_context,
                                      const CefBrowserSettings* settings, int shared_texture,
                                      int64_t parent_view);
  // macOS: the NSView (its address) a windowed browser becomes a child of; 0: none.
  void SetParentView(uintptr_t view);
  uintptr_t ParentView();
  // The settings of the first browser and of the ones made without settings.
  void SetBrowserSettings(const CefBrowserSettings& settings);
  void SetTransparent(bool transparent);
  void SetFirstBrowser(bool create);
  void SetRendererEvents(bool on);
  void SetSharedTexture(bool enabled);
  bool SharedTexture();
  bool Transparent();
  void SetRequestContext(CefRefPtr<CefRequestContext> context);
  bool Offscreen();
  void SetWindowlessFrameRate(int frames_per_second);
  int WindowlessFrameRate();
  // The message router (window.cefQuery): see query_router.h. The names must be set before
  // InitCefSimple(); a handler can be added before it (and, once CEF runs, at any time) only
  // if it was added before, because the renderer learns about the router at startup.
  void SetQueryFunctions(std::string query, std::string cancel);
  // The names JavascriptBridge exposes, as a JSON array (before InitCefSimple()).
  void SetBridgeNames(std::string json);
  bool AddQueryHandler(PythonQueryHandler* handler, bool first);
  bool RemoveQueryHandler(PythonQueryHandler* handler);
  bool QueryRouterExists();
  void CancelPendingQueries(CefRefPtr<CefBrowser> browser, PythonQueryHandler* handler);
  // java-cef's CefAppHandler hooks (app_hooks.h); before InitCefSimple().
  void SetAppHooks(void* py, app_command_line_ptr command_line, app_schemes_ptr schemes,
                   app_context_ptr context, app_relaunch_ptr relaunch, app_schedule_ptr schedule,
                   app_child_launch_ptr child_launch, app_preferences_ptr preferences);

private:
    CefRefPtr<CefWrapperApp> m_App;
    CefRefPtr<CefClient> m_Client;

    bool m_UseCustomCefSubPath = false;
    std::string m_CustomCefSubPath = "";

    std::vector<std::pair<std::string, std::string>> m_CommandLineSwitches;

    bool m_UseCustomCefResourcesPath = false;
    std::string m_CustomCefResourcesPath = "";

    std::map<std::string, std::string> m_StringSettings;
    std::map<std::string, long long> m_IntSettings;

    bool m_UseCustomCefCachePath = false;
    std::string m_CustomCefCachePath = "";

    std::vector<JavascriptBinding> m_Javascript_Bindings;
    std::vector<JavascriptPythonBinding> m_Javascript_Python_Bindings;
}
;

// Small helpers for what the generator cannot express (see tools/gen/extras/): DevTools in a window of its own,
// and the copy of a shared memory region of a process message.
void CefWeaverShowDevTools(CefBrowserHost* host, int inspect_x, int inspect_y);
std::string CefWeaverSharedMemoryRead(CefSharedMemoryRegion* region);
bool CefWeaverSharedBuilderWrite(CefSharedProcessMessageBuilder* builder, size_t offset, const void* data,
                                 size_t size);

#endif//LIBRARY_LIBRARY_H
