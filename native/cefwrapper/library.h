#ifndef LIBRARY_LIBRARY_H
#define LIBRARY_LIBRARY_H


#include "cef_wrapper_app.h"
#include "cef_wrapper_client_handler.h"
#include "include/cef_command_line.h"
#include "javascript_binding.h"

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

private:
    CefRefPtr<CefWrapperApp> m_App;

    bool m_UseCustomCefSubPath = false;
    std::string m_CustomCefSubPath = "";

    std::vector<std::pair<std::string, std::string>> m_CommandLineSwitches;

    bool m_UseCustomCefResourcesPath = false;
    std::string m_CustomCefResourcesPath = "";

    bool m_UseCustomCefCachePath = false;
    std::string m_CustomCefCachePath = "";

    std::vector<JavascriptBinding> m_Javascript_Bindings;
    std::vector<JavascriptPythonBinding> m_Javascript_Python_Bindings;
}
;

#endif//LIBRARY_LIBRARY_H
