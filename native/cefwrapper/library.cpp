#include "library.h"

#include "global_vars.h"
#include "javascript_binding.h"
#include <filesystem>
#include <chrono>
#include <iostream>
#include <thread>
#undef CEF_USE_SANDBOX

#if defined(OS_LINUX)
#include <dlfcn.h>
#include <unistd.h>
#include <climits>
#endif

namespace {

#if defined(OS_LINUX)
// Directory of the shared object that contains this code (the Python
// extension module). The CEF runtime files and the cefsubprocess executable
// are deployed next to it.
std::string ModuleDir() {
  Dl_info info;
  if (dladdr(reinterpret_cast<void *>(&ModuleDir), &info) && info.dli_fname) {
    return std::filesystem::path(info.dli_fname).parent_path().string();
  }
  return std::string();
}
#endif

}  // namespace


std::string ExePath() {
#if defined(OS_LINUX)
  std::filesystem::path cwd = std::filesystem::path(ModuleDir()) / "cefsubprocess";
#else
  std::filesystem::path cwd = std::filesystem::current_path() /"cefsubprocess" / "cefsubprocess.exe";   //"C:\\Dev\\cef-binaries\\cef_binary_106.0.27+g20ed841+chromium-106.0.5249.103_windows64\\cmake-build-debug-visual-studio\\src\\cefsubprocess\\Debug\\cefsubprocess.exe";
#endif
  return cwd.string();
}

std::string CachePath() {
  std::filesystem::path cwd = std::filesystem::current_path() / "cache";   //"C:\\Dev\\cef-binaries\\cef_binary_106.0.27+g20ed841+chromium-106.0.5249.103_windows64\\cmake-build-debug-visual-studio\\src\\cefsubprocess\\Debug\\cefsubprocess.exe";
  return cwd.string();
}

bool CefWrapper::InitCefSimple(std::string start_url) {
#if defined(OS_WIN)
  CefEnableHighDPISupport();
#endif

  void *sandbox_info = nullptr;

#if defined(OS_LINUX)
  // On Linux CefMainArgs needs argc/argv, but an embedded interpreter has no
  // meaningful ones; the real executable path is resolved by CEF itself.
  static char arg0[] = "cefweaver";
  static char *argv[] = {arg0, nullptr};
  CefMainArgs main_args(1, argv);
#else
  CefMainArgs main_args;
#endif

  m_App = CefRefPtr<CefWrapperApp>(new CefWrapperApp( start_url, m_Javascript_Bindings, m_Javascript_Python_Bindings));
  for (const auto &entry : m_CommandLineSwitches) {
    m_App->AddCommandLineSwitch(entry.first, entry.second);
  }
  CefExecuteProcess(main_args, m_App.get(), sandbox_info);

#if defined(OS_WIN)
  CefRefPtr<CefCommandLine> command_line = CefCommandLine::CreateCommandLine();
  command_line->InitFromString(::GetCommandLineW());
#endif



  CefSettings settings;

  if(m_UseCustomCefCachePath)
  {
    CefString(&settings.cache_path) = m_CustomCefCachePath;
    CefString(&settings.root_cache_path) = m_CustomCefCachePath;
  }
  else
  {
    CefString(&settings.cache_path) = CachePath();
    CefString(&settings.root_cache_path) = CachePath();
  }

  // settings.multi_threaded_message_loop = true;
  settings.no_sandbox = true;

  // Optional. On Linux CEF 154 looks for icudtl.dat next to libcef.so whatever
  // is set here (checked with libcef.so and the resources in different
  // directories), so the runtime files must be deployed together with
  // libcef.so. Without this setting the files next to libcef.so are used.
  if (m_UseCustomCefResourcesPath && !m_CustomCefResourcesPath.empty()) {
    CefString(&settings.resources_dir_path) = m_CustomCefResourcesPath;
    CefString(&settings.locales_dir_path) =
        (std::filesystem::path(m_CustomCefResourcesPath) / "locales").string();
  }

  if(m_UseCustomCefSubPath)
  {
    CefString(&settings.browser_subprocess_path).FromASCII(m_CustomCefSubPath.c_str());
  }
  else
  {
    CefString(&settings.browser_subprocess_path).FromASCII(ExePath().c_str());
  }

  if (!CefInitialize(main_args, settings, m_App.get(), sandbox_info)) {
    m_App = nullptr;
    return false;
  }
  g_IsRunning = true;
  return true;
}
bool CefWrapper::ExecuteJavascript(std::string code) {
  if (!m_App || !g_IsRunning) {
    return false;
  }
  CefRefPtr<CefBrowser> browser = m_App->GetBrowser();
  CefRefPtr<CefWrapperClientHandler> handler = CefWrapperClientHandler::GetInstance();
  if (!browser || !handler || !handler->IsReadyToExecuteJs()) {
    return false;
  }
  CefRefPtr<CefFrame> frame = browser->GetMainFrame();
  frame->ExecuteJavaScript(code, frame->GetURL(), 0);
  return true;
}

void CefWrapper::ShutdownCefSimple() {
  // CEF requires every browser to be closed and released before CefShutdown().
  CefRefPtr<CefWrapperClientHandler> handler = CefWrapperClientHandler::GetInstance();
  if (handler) {
    handler->CloseAllBrowsers(true);
    for (int i = 0; i < 500 && handler->HasOpenBrowsers(); ++i) {
      CefDoMessageLoopWork();
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
  }
  CefWrapperBrowserProcessHandler::GetInstance()->Browser = nullptr;
  handler = nullptr;
  CefShutdown();
  m_App = nullptr;
  g_IsRunning = false;
}

bool CefWrapper::IsRunning() { return g_IsRunning; }

void CefWrapper::DoCefMessageLoopWork() { CefDoMessageLoopWork(); }
bool CefWrapper::IsReadyToExecuteJavascript() {
  return CefWrapperClientHandler::GetInstance()->IsReadyToExecuteJs();
}

void CefWrapper::AddJavascriptBinding(std::string name, js_binding_function_ptr jsNativeApiFunctionPtr)
{
  m_Javascript_Bindings.push_back(JavascriptBinding(name, jsNativeApiFunctionPtr));
}
CefWrapper::CefWrapper() {}
void CefWrapper::AddJavascriptPythonBinding(
    std::string name,
    js_python_bindings_handler_function_ptr python_bindings_handler,
    js_python_callback_object_ptr python_callback_object) {
  m_Javascript_Python_Bindings.push_back(
      JavascriptPythonBinding(python_bindings_handler, name, python_callback_object));
}
void CefWrapper::SetCustomCefSubprocessPath(std::string cefsub_path) {
  m_UseCustomCefSubPath = true;
  m_CustomCefSubPath = cefsub_path;
}
void CefWrapper::AddCommandLineSwitch(std::string name, std::string value) {
  m_CommandLineSwitches.emplace_back(std::move(name), std::move(value));
}
void CefWrapper::SetCustomCefResourcesPath(std::string cef_resources_path) {
  m_UseCustomCefResourcesPath = true;
  m_CustomCefResourcesPath = cef_resources_path;
}
void CefWrapper::SetCustomCefCachePath(std::string cef_cache_path) {
  m_UseCustomCefCachePath = true;
  m_CustomCefCachePath = cef_cache_path;
}
bool CefWrapper::LoadUrl(std::string url) {
  if (!m_App) {
    return false;
  }
  CefRefPtr<CefBrowser> browser = m_App->GetBrowser();
  if (!browser) {
    return false;
  }
  browser->GetMainFrame()->LoadURL(url);
  return true;
}
