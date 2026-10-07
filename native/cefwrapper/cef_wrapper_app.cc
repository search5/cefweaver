



#include "cef_wrapper_app.h"

#include "include/cef_browser.h"
#include "include/cef_command_line.h"

#include "include/cef_origin_whitelist.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"

CefRefPtr<CefBrowser> CefWrapperApp::GetBrowser()
{
    return CefWrapperBrowserProcessHandler::GetInstance()->Browser;
}

void CefWrapperApp::OnBeforeCommandLineProcessing(
    const CefString &process_type, CefRefPtr<CefCommandLine> command_line) {
  //command_line->AppendSwitch("allow-file-access-from-files");
  if (!process_type.empty()) {
    return;  // child processes inherit the browser process switches
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
  //registrar->AddCustomScheme("zen", CEF_SCHEME_OPTION_STANDARD | CEF_SCHEME_OPTION_CORS_ENABLED);
}
