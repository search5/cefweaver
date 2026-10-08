



#include "cef_wrapper_app.h"

#include "include/cef_browser.h"
#include "include/cef_command_line.h"

#include "include/cef_origin_whitelist.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"
#include "app_hooks.h"

CefRefPtr<CefBrowser> CefWrapperApp::GetBrowser()
{
    return CefWrapperBrowserProcessHandler::GetInstance()->Browser;
}

void CefWrapperApp::OnBeforeCommandLineProcessing(
    const CefString &process_type, CefRefPtr<CefCommandLine> command_line) {
  //command_line->AppendSwitch("allow-file-access-from-files");
  if (!process_type.empty()) {
    return;  // the switches below are for the browser process only; children get what OnBeforeChildProcessLaunch adds
  }
  // java-cef gives its handler the command line of the browser process before the essentials.
  const AppHooks& hooks = GetAppHooks();
  if (hooks.command_line) {
    hooks.command_line(hooks.py, command_line);
  }
  for (const auto &entry : m_CommandLineSwitches) {
    if (entry.second.empty()) {
      command_line->AppendSwitch(entry.first);
    } else {
      command_line->AppendSwitchWithValue(entry.first, entry.second);
    }
  }
}

void CefWrapperApp::AddCommandLineSwitch(std::string name, std::string value) {
  m_CommandLineSwitches.emplace_back(std::move(name), std::move(value));
}

CefWrapperApp::CefWrapperApp(std::string start_url, std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings) {
  m_Javascript_Bindings = javascript_bindings;
  m_Javascript_Python_Bindings = javascript_python_bindings;
  CefWrapperBrowserProcessHandler::SetJavascriptBindings(
      m_Javascript_Bindings, m_Javascript_Python_Bindings);
  CefWrapperBrowserProcessHandler::SetStartUrl(start_url);
}

void CefWrapperApp::LoadUrl(std::string url) {
  CefWrapperBrowserProcessHandler::LoadUrl(url);
}
void CefWrapperApp::OnRegisterCustomSchemes(
    CefRawPtr<CefSchemeRegistrar> registrar) {
  CefRefPtr<CefCommandLine> line = CefCommandLine::GetGlobalCommandLine();
  if (line && line->HasSwitch("type")) {
    // A child process: the schemes the browser process registered, from its switch.
    RegisterCustomSchemesFrom(line->GetSwitchValue(kCustomSchemesSwitch), registrar);
    return;
  }
  const AppHooks& hooks = GetAppHooks();
  if (hooks.schemes) {
    SchemeRegistrarProxy proxy(registrar);
    hooks.schemes(hooks.py, &proxy);
  }
}
