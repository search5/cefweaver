

#include "cef_wrapper_browser_process_handler.h"
#include "cef_wrapper_client_handler.h"
#include "cef_wrapper_render_process_handler.h"
#include "custom_protocol_scheme_handler.h"
#include "javascript_binding.h"
#include "global_vars.h"
#include "query_router.h"
#include "app_hooks.h"

CefWrapperBrowserProcessHandler::CefWrapperBrowserProcessHandler() = default;

void CefWrapperBrowserProcessHandler::OnBeforeChildProcessLaunch(
    CefRefPtr<CefCommandLine> command_line) {
  const std::string schemes = CustomSchemesSwitchValue();
  if (!schemes.empty()) {
    command_line->AppendSwitchWithValue(kCustomSchemesSwitch, schemes);
  }
  if (QueryRouter::HasHandlers()) {
    command_line->AppendSwitchWithValue(kQueryFunctionSwitch, QueryRouter::QueryFunction());
    command_line->AppendSwitchWithValue(kCancelFunctionSwitch, QueryRouter::CancelFunction());
  }
}

/* Null, because instance will be initialized on demand. */
CefRefPtr<CefWrapperBrowserProcessHandler>
    CefWrapperBrowserProcessHandler::instance = nullptr;

CefRefPtr<CefWrapperBrowserProcessHandler>
CefWrapperBrowserProcessHandler::GetInstance()
{
  if (instance == nullptr)
  {
    instance = CefRefPtr<CefWrapperBrowserProcessHandler>(new CefWrapperBrowserProcessHandler());
  }

  return instance;
}
void CefWrapperBrowserProcessHandler::SetJavascriptBindings(std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings)
{
  GetInstance()->m_JavascriptBindings = javascript_bindings;
  GetInstance()->m_JavascriptPythonBindings = javascript_python_bindings;
}

void CefWrapperBrowserProcessHandler::SetUserClient(CefRefPtr<CefClient> client)
{
  GetInstance()->m_UserClient = client;
}

CefRefPtr<CefClient> CefWrapperBrowserProcessHandler::GetDefaultClient()
{
  return CefWrapperClientHandler::GetInstance();
}

bool CefWrapperBrowserProcessHandler::OnAlreadyRunningAppRelaunch(
    CefRefPtr<CefCommandLine> command_line, const CefString& current_directory) {
  const AppHooks& hooks = GetAppHooks();
  return hooks.relaunch ? hooks.relaunch(hooks.py, command_line, current_directory.ToString())
                        : false;
}

void CefWrapperBrowserProcessHandler::OnContextInitialized()
{
  CEF_REQUIRE_UI_THREAD();
  const AppHooks& hooks = GetAppHooks();
  if (hooks.context) {
    hooks.context(hooks.py);  // before the first browser, so a hook can still prepare things
  }

  CefRefPtr<CefCommandLine> command_line =
      CefCommandLine::GetGlobalCommandLine();

  bool use_views = command_line->HasSwitch("use-views");

  //RegisterSchemeHandlerFactory();

  CefRefPtr<CefWrapperClientHandler> handler(new CefWrapperClientHandler(use_views, m_JavascriptBindings, m_JavascriptPythonBindings, m_UserClient));
  SimpleRenderProcessHandler::getInstance()->SetJavascriptBindings(
      m_JavascriptBindings, m_JavascriptPythonBindings);

  CefBrowserSettings browser_settings;

  std::string url;
  url = StartUrl;

  CefWindowInfo window_info;
  // Alloy style only, as in java-cef: it adds the client callbacks (DoClose, ...) and
  // supports a client-provided parent window and windowless rendering.
  window_info.runtime_style = CEF_RUNTIME_STYLE_ALLOY;
  if (g_Offscreen.load()) {
    // No window: CEF draws into the buffer of the user's render handler.
    window_info.SetAsWindowless(kNullWindowHandle);
    browser_settings.windowless_frame_rate = g_WindowlessFrameRate.load();
  }

#if defined(OS_WIN)
  // On Windows we need to specify certain flags that will be passed to
  // CreateWindowEx().
  window_info.SetAsPopup(nullptr, "cefsimple");
#endif

  CefRefPtr<CefDictionaryValue> extra = CefDictionaryValue::Create();
  // Only the names cross the process boundary. The binding objects hold
  // std::string and function pointers of this process, so they must not be
  // copied as raw memory into the renderer process.
  if(!m_JavascriptBindings.empty())
  {
    CefRefPtr<CefListValue> names = CefListValue::Create();
    for (size_t i = 0; i < m_JavascriptBindings.size(); ++i)
    {
      names->SetString(i, m_JavascriptBindings[i].functionName);
    }
    extra->SetList("JSCallbackNames", names);
  }

  if(!m_JavascriptPythonBindings.empty())
  {
    CefRefPtr<CefListValue> names = CefListValue::Create();
    for (size_t i = 0; i < m_JavascriptPythonBindings.size(); ++i)
    {
      names->SetString(i, m_JavascriptPythonBindings[i].MessageTopic);
    }
    extra->SetList("JSNativePythonApiNames", names);
  }

  Browser = CefBrowserHost::CreateBrowserSync(window_info, handler, url, browser_settings,
                                                extra, nullptr);

  // m_Browser->GetHost()->ShowDevTools(window_info, nullptr, browser_settings, CefPoint());
}
void CefWrapperBrowserProcessHandler::SetStartUrl(std::string url) {
  CefWrapperBrowserProcessHandler::GetInstance()->StartUrl = url;
}
void CefWrapperBrowserProcessHandler::LoadUrl(std::string url) {
  CefWrapperBrowserProcessHandler::GetInstance()->Browser->GetMainFrame()->LoadURL(url);
}
