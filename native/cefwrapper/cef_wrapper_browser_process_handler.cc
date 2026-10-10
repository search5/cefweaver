

#include "runtime.h"
#include "cef_wrapper_browser_process_handler.h"
#include "cef_wrapper_client_handler.h"
#include "cef_wrapper_render_process_handler.h"
#include "custom_protocol_scheme_handler.h"
#include "javascript_binding.h"
#include "global_vars.h"
#include "query_router.h"
#include "app_hooks.h"
#include "bridge.h"

CefWrapperBrowserProcessHandler::CefWrapperBrowserProcessHandler() = default;

void CefWrapperBrowserProcessHandler::OnBeforeChildProcessLaunch(
    CefRefPtr<CefCommandLine> command_line) {
  const std::string schemes = CustomSchemesSwitchValue();
  if (!schemes.empty()) {
    command_line->AppendSwitchWithValue(kCustomSchemesSwitch, schemes);
  }
  if (!BridgeNames().empty()) {
    command_line->AppendSwitchWithValue(kBridgeSwitch, BridgeNames());
  }
  if (QueryRouter::HasHandlers()) {
    command_line->AppendSwitchWithValue(kQueryFunctionSwitch, QueryRouter::QueryFunction());
    command_line->AppendSwitchWithValue(kCancelFunctionSwitch, QueryRouter::CancelFunction());
  }
  if (g_RendererEvents.load()) {
    command_line->AppendSwitch(kRendererEventsSwitch);
  }
  const AppHooks& hooks = GetAppHooks();
  if (hooks.child_launch) {
    hooks.child_launch(hooks.py, command_line);   // the application's turn, after the wrapper's switches
  }
}

void CefWrapperBrowserProcessHandler::OnRegisterCustomPreferences(
    cef_preferences_type_t type, CefRawPtr<CefPreferenceRegistrar> registrar) {
  const AppHooks& hooks = GetAppHooks();
  if (hooks.preferences) {
    PreferenceRegistrarProxy proxy(registrar);
    hooks.preferences(hooks.py, static_cast<int>(type), &proxy);
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

CefRefPtr<CefBrowser> CefWrapperBrowserProcessHandler::CreateBrowser(
    const std::string& url, bool offscreen, bool transparent,
    CefRefPtr<CefRequestContext> request_context, const CefBrowserSettings* settings,
    bool shared_texture, uintptr_t parent_view) {
  CEF_REQUIRE_UI_THREAD();
  CefRefPtr<CefWrapperBrowserProcessHandler> self = GetInstance();
  CefBrowserSettings browser_settings = settings ? *settings : self->m_BrowserSettings;

  CefWindowInfo window_info;
  // Alloy style only, as in java-cef: it adds the client callbacks (DoClose, ...) and
  // supports a client-provided parent window and windowless rendering.
  window_info.runtime_style = CEF_RUNTIME_STYLE_ALLOY;
  if (offscreen) {
    // No window: CEF draws into the buffer of the user's render handler.
    window_info.SetAsWindowless(kNullWindowHandle);
    window_info.shared_texture_enabled = shared_texture;
    if (browser_settings.windowless_frame_rate == 0) {
      browser_settings.windowless_frame_rate = g_WindowlessFrameRate.load();
    }
    // A colour the browser settings give (opaque) wins over the app's.
    if (!transparent && (browser_settings.background_color >> 24) != 0xFF) {
      // CEF takes a clear browser colour as "paint transparent" (and then ignores the colour
      // of CefSettings), so an opaque browser gets its colour here, white by default as in
      // java-cef.
      const unsigned int color = g_BackgroundColor.load();
      browser_settings.background_color = (color >> 24) == 0xFF ? color : 0xFFFFFFFF;
    }
  }

#if defined(OS_MAC)
  if (!offscreen && parent_view != 0) {
    // A child of the application's NSView, filling it (CEF resizes it with its parent).
    int width = 0, height = 0;
    CefWeaverViewSize(parent_view, &width, &height);
    window_info.SetAsChild(reinterpret_cast<cef_window_handle_t>(parent_view),
                           CefRect(0, 0, width, height));
  }
#endif

#if defined(OS_WIN)
  // On Windows we need to specify certain flags that will be passed to
  // CreateWindowEx().
  window_info.SetAsPopup(nullptr, "cefsimple");
#endif

  CefRefPtr<CefDictionaryValue> extra = CefDictionaryValue::Create();
  // Only the names cross the process boundary. The binding objects hold
  // std::string and function pointers of this process, so they must not be
  // copied as raw memory into the renderer process.
  if (!self->m_JavascriptBindings.empty()) {
    CefRefPtr<CefListValue> names = CefListValue::Create();
    for (size_t i = 0; i < self->m_JavascriptBindings.size(); ++i) {
      names->SetString(i, self->m_JavascriptBindings[i].functionName);
    }
    extra->SetList("JSCallbackNames", names);
  }
  if (!self->m_JavascriptPythonBindings.empty()) {
    CefRefPtr<CefListValue> names = CefListValue::Create();
    for (size_t i = 0; i < self->m_JavascriptPythonBindings.size(); ++i) {
      names->SetString(i, self->m_JavascriptPythonBindings[i].MessageTopic);
    }
    extra->SetList("JSNativePythonApiNames", names);
  }

  CefRefPtr<CefBrowser> browser = CefBrowserHost::CreateBrowserSync(
      window_info, CefWrapperClientHandler::GetInstance(), url, browser_settings, extra,
      request_context);
#if defined(OS_MAC)
  if (browser && !offscreen) {
    std::lock_guard<std::mutex> lock(g_ChildViewBrowsersMutex);
    g_ChildViewBrowsers[browser->GetIdentifier()] = 0;
    if (parent_view == 0) {
      g_OwnWindowBrowsers.insert(browser->GetIdentifier());
    }
  }
#endif
  return browser;
}

void CefWrapperBrowserProcessHandler::OnScheduleMessagePumpWork(int64_t delay_ms) {
  const AppHooks& hooks = GetAppHooks();
  if (hooks.schedule) {
    hooks.schedule(hooks.py, delay_ms);
  }
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

  if (!g_NoFirstBrowser.load()) {
    Browser = CreateBrowser(StartUrl, g_Offscreen.load(), g_Transparent.load(), m_RequestContext,
                            nullptr, g_SharedTexture.load(), g_ParentView.load());
  }

  // m_Browser->GetHost()->ShowDevTools(window_info, nullptr, browser_settings, CefPoint());
}
void CefWrapperBrowserProcessHandler::SetBrowserSettings(const CefBrowserSettings& settings) {
  CefWrapperBrowserProcessHandler::GetInstance()->m_BrowserSettings = settings;
}
void CefWrapperBrowserProcessHandler::SetRequestContext(CefRefPtr<CefRequestContext> context) {
  CefWrapperBrowserProcessHandler::GetInstance()->m_RequestContext = context;
}
void CefWrapperBrowserProcessHandler::SetStartUrl(std::string url) {
  CefWrapperBrowserProcessHandler::GetInstance()->StartUrl = url;
}
void CefWrapperBrowserProcessHandler::LoadUrl(std::string url) {
  CefWrapperBrowserProcessHandler::GetInstance()->Browser->GetMainFrame()->LoadURL(url);
}
