#include "cef_wrapper_client_handler.h"

#include <sstream>
#include <string>

#include "global_vars.h"
#include "include/base/cef_callback.h"
#include "include/cef_app.h"
#include "include/cef_parser.h"
#include "include/views/cef_browser_view.h"
#include "include/views/cef_window.h"
#include "include/wrapper/cef_closure_task.h"
#include "include/wrapper/cef_helpers.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"
#include "query_router.h"

namespace {
// The ids of the wrapper's own menu items are the last ones of the range CEF leaves to
// applications, so that the ids a user picks from the start of the range never collide.
enum client_menu_ids {
  CLIENT_ID_SHOW_DEVTOOLS = MENU_ID_USER_LAST - 2,
  CLIENT_ID_CLOSE_DEVTOOLS = MENU_ID_USER_LAST - 1,
  CLIENT_ID_INSPECT_ELEMENT = MENU_ID_USER_LAST,
};
CefWrapperClientHandler *g_instance = nullptr;


std::string GetDataURI(const std::string &data, const std::string &mime_type) {
  return "data:" + mime_type + ";base64," +
         CefURIEncode(CefBase64Encode(data.data(), data.size()), false)
             .ToString();
}

} // namespace

CefWrapperClientHandler::CefWrapperClientHandler(
    bool use_views, std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings,
    CefRefPtr<CefClient> user_client) : use_views_(use_views), user_client_(user_client), is_closing_(false) {
  DCHECK(!g_instance);
  m_JavascriptBindings = javascript_bindings;
  m_JavascriptPythonBindings = javascript_python_bindings;
  g_instance = this;
  
}
CefWrapperClientHandler::~CefWrapperClientHandler() { g_instance = nullptr; }

CefRefPtr<CefRequestHandler> CefWrapperClientHandler::GetRequestHandler() {
  forward_request_handler_ = user_client_ ? user_client_->GetRequestHandler() : nullptr;
  return (QueryRouter::Exists() || forward_request_handler_) ? this : nullptr;
}

bool CefWrapperClientHandler::OnBeforeBrowse(CefRefPtr<CefBrowser> browser,
                                             CefRefPtr<CefFrame> frame,
                                             CefRefPtr<CefRequest> request, bool user_gesture,
                                             bool is_redirect) {
  CEF_REQUIRE_UI_THREAD();
  // The user's handler decides first; true cancels the navigation.
  const bool canceled = CwRequestHandlerForward::OnBeforeBrowse(browser, frame, request,
                                                                user_gesture, is_redirect);
  // Only an allowed navigation leaves the page, so only then are its queries canceled.
  if (!canceled) {
    if (CefRefPtr<CefMessageRouterBrowserSide> router = QueryRouter::Get()) {
      router->OnBeforeBrowse(browser, frame);
    }
  }
  return canceled;
}

void CefWrapperClientHandler::OnRenderProcessTerminated(CefRefPtr<CefBrowser> browser,
                                                        TerminationStatus status,
                                                        int error_code,
                                                        const CefString& error_string) {
  CEF_REQUIRE_UI_THREAD();
  if (CefRefPtr<CefMessageRouterBrowserSide> router = QueryRouter::Get()) {
    router->OnRenderProcessTerminated(browser);
  }
  CwRequestHandlerForward::OnRenderProcessTerminated(browser, status, error_code, error_string);
}


CefWrapperClientHandler *CefWrapperClientHandler::GetInstance() { return g_instance; }

void CefWrapperClientHandler::OnBeforeContextMenu(CefRefPtr<CefBrowser> browser,
                                        CefRefPtr<CefFrame> frame,
                                        CefRefPtr<CefContextMenuParams> params,
                                        CefRefPtr<CefMenuModel> model) {
  CEF_REQUIRE_UI_THREAD();

  // The user's handler changes the menu first (it may clear it), then the wrapper adds its
  // own items, so the user sees the same menu with the items on and off.
  CwContextMenuHandlerForward::OnBeforeContextMenu(browser, frame, params, model);

  if (!g_DevToolsMenuEnabled.load()) {
    return;
  }
  if (model->GetCount() > 0)
    model->AddSeparator();

  model->AddItem(CLIENT_ID_SHOW_DEVTOOLS, "&Show DevTools");
  model->AddItem(CLIENT_ID_CLOSE_DEVTOOLS, "Close DevTools");
  model->AddSeparator();
  model->AddItem(CLIENT_ID_INSPECT_ELEMENT, "Inspect Element");
}

bool CefWrapperClientHandler::OnContextMenuCommand(CefRefPtr<CefBrowser> browser,
                                         CefRefPtr<CefFrame> frame,
                                         CefRefPtr<CefContextMenuParams> params,
                                         int command_id,
                                         EventFlags event_flags) {
  CEF_REQUIRE_UI_THREAD();

  // The wrapper's own items are handled whether or not the items are on now (a menu built
  // before they were turned off may still be showing them). Every other command goes to the
  // user's handler, and when it does not handle it CEF runs its standard command.
  switch (command_id) {
  case CLIENT_ID_SHOW_DEVTOOLS:
    ShowDevTools(browser, CefPoint());
    return true;
  case CLIENT_ID_CLOSE_DEVTOOLS:
    CloseDevTools(browser);
    return true;
  case CLIENT_ID_INSPECT_ELEMENT:
    ShowDevTools(browser, CefPoint(params->GetXCoord(), params->GetYCoord()));
    return true;
  default:
    return CwContextMenuHandlerForward::OnContextMenuCommand(browser, frame, params,
                                                             command_id, event_flags);
  }
}
void CefWrapperClientHandler::ShowDevTools(CefRefPtr<CefBrowser> browser,
                                 const CefPoint &inspect_element_at) {
  if (!CefCurrentlyOn(TID_UI)) {
    // Execute this method on the UI thread.
    CefPostTask(TID_UI, base::BindOnce(&CefWrapperClientHandler::ShowDevTools, this,
                                       browser, inspect_element_at));
    return;
  }

  CefWindowInfo windowInfo;
  CefRefPtr<CefClient> client;
  CefBrowserSettings settings;

  CefRefPtr<CefBrowserHost> host = browser->GetHost();

  host->ShowDevTools(windowInfo, client, settings, inspect_element_at);
}

void CefWrapperClientHandler::CloseDevTools(CefRefPtr<CefBrowser> browser) {
  browser->GetHost()->CloseDevTools();
}

void CefWrapperClientHandler::OnTitleChange(CefRefPtr<CefBrowser> browser,
                                  const CefString &title) {
  CEF_REQUIRE_UI_THREAD();

  if (use_views_) {
    // Set the title of the window using the Views framework.
    CefRefPtr<CefBrowserView> browser_view =
        CefBrowserView::GetForBrowser(browser);
    if (browser_view) {
      CefRefPtr<CefWindow> window = browser_view->GetWindow();
      if (window)
        window->SetTitle(title);
    }
  } else if (!IsChromeRuntimeEnabled()) {
    // Set the title of the window using platform APIs.
    PlatformTitleChange(browser, title);
  }
  CwDisplayHandlerForward::OnTitleChange(browser, title);
}

void CefWrapperClientHandler::OnAfterCreated(CefRefPtr<CefBrowser> browser) {
  CEF_REQUIRE_UI_THREAD();

  // Add to the list of existing browsers.
  browser_list_.push_back(browser);
  if (primary_browser_id_ == 0 && !browser->IsPopup()) {
    primary_browser_id_ = browser->GetIdentifier();
  }
  CwLifeSpanHandlerForward::OnAfterCreated(browser);
}

bool CefWrapperClientHandler::OnBeforePopup(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame, int popup_id,
    const CefString& target_url, const CefString& target_frame_name,
    cef_window_open_disposition_t target_disposition, bool user_gesture,
    const CefPopupFeatures& popupFeatures, CefWindowInfo& windowInfo,
    CefRefPtr<CefClient>& client, CefBrowserSettings& settings,
    CefRefPtr<CefDictionaryValue>& extra_info, bool* no_javascript_access) {
  CEF_REQUIRE_UI_THREAD();
  if (browser->GetHost()->IsWindowRenderingDisabled()) {
    return true;  // true cancels the popup: an offscreen browser has no window for it
  }
  // The user's handler decides (java-cef's too): true cancels the popup.
  return CwLifeSpanHandlerForward::OnBeforePopup(
      browser, frame, popup_id, target_url, target_frame_name, target_disposition, user_gesture,
      popupFeatures, windowInfo, client, settings, extra_info, no_javascript_access);
}

bool CefWrapperClientHandler::DoClose(CefRefPtr<CefBrowser> browser) {
  CEF_REQUIRE_UI_THREAD();

  // The user's handler can keep the browser open by returning true.
  if (CwLifeSpanHandlerForward::DoClose(browser)) {
    return true;
  }

  // Closing the main window requires special handling. See the DoClose()
  // documentation in the CEF header for a detailed destription of this
  // process.
  if (browser_list_.size() == 1) {
    // Set a flag to indicate that the window close should be allowed.
    is_closing_ = true;
  }

  // Allow the close. For windowed browsers this will result in the OS close
  // event being sent.
  return false;
}

void CefWrapperClientHandler::OnBeforeClose(CefRefPtr<CefBrowser> browser) {
  CEF_REQUIRE_UI_THREAD();

  if (CefRefPtr<CefMessageRouterBrowserSide> router = QueryRouter::Get()) {
    router->OnBeforeClose(browser);
  }

  CwLifeSpanHandlerForward::OnBeforeClose(browser);

  // Remove from the list of existing browsers.
  BrowserList::iterator bit = browser_list_.begin();
  for (; bit != browser_list_.end(); ++bit) {
    if ((*bit)->IsSame(browser)) {
      browser_list_.erase(bit);
      break;
    }
  }
  if (browser_list_.empty()) {
    // All browser windows have closed (a popup closing alone leaves the app running).
    g_IsRunning = false;
    CefQuitMessageLoop();
  }
}

void CefWrapperClientHandler::OnLoadError(CefRefPtr<CefBrowser> browser,
                                CefRefPtr<CefFrame> frame, ErrorCode errorCode,
                                const CefString &errorText,
                                const CefString &failedUrl) {
  CEF_REQUIRE_UI_THREAD();

  CwLoadHandlerForward::OnLoadError(browser, frame, errorCode, errorText, failedUrl);

  // Allow Chrome to show the error page.
  if (IsChromeRuntimeEnabled())
    return;

  // Don't display an error for downloaded files.
  if (errorCode == ERR_ABORTED)
    return;

  // Display a load error message using a data: URI.
  std::stringstream ss;
  ss << "<html><body bgcolor=\"white\">"
        "<h2>Failed to load URL "
     << std::string(failedUrl) << " with error " << std::string(errorText)
     << " (" << errorCode << ").</h2></body></html>";

  frame->LoadURL(GetDataURI(ss.str(), "text/html"));
}

void CefWrapperClientHandler::CloseAllBrowsers(bool force_close) {
  if (!CefCurrentlyOn(TID_UI)) {
    // Execute on the UI thread.
    CefPostTask(TID_UI, base::BindOnce(&CefWrapperClientHandler::CloseAllBrowsers, this,
                                       force_close));
    return;
  }

  if (browser_list_.empty())
    return;

  // Closing a browser without a window (offscreen) runs OnBeforeClose right away, which
  // removes it from browser_list_: walk a copy.
  const BrowserList browsers = browser_list_;
  for (const auto& browser : browsers)
    browser->GetHost()->CloseBrowser(force_close);
}


bool CefWrapperClientHandler::IsChromeRuntimeEnabled() {
  static int value = -1;
  if (value == -1) {
    CefRefPtr<CefCommandLine> command_line =
        CefCommandLine::GetGlobalCommandLine();
    value = command_line->HasSwitch("enable-chrome-runtime") ? 1 : 0;
  }
  return value == 1;
}
void CefWrapperClientHandler::OnLoadEnd(CefRefPtr<CefBrowser> browser,
                              CefRefPtr<CefFrame> frame, int httpStatusCode)
{
  std::string code = "const event = new Event('cefready'); window.dispatchEvent(event);";
  frame->ExecuteJavaScript(code, frame->GetURL(), 0);
  CwLoadHandlerForward::OnLoadEnd(browser, frame, httpStatusCode);
}
bool CefWrapperClientHandler::IsReadyToExecuteJs() { return m_IsReadyToExecuteJs; }
void CefWrapperClientHandler::OnLoadStart(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
    CefLoadHandler::TransitionType transition_type) {
  if (browser->GetIdentifier() == primary_browser_id_) {
    m_IsReadyToExecuteJs = false;
  }
  CwLoadHandlerForward::OnLoadStart(browser, frame, transition_type);
}
bool CefWrapperClientHandler::OnProcessMessageReceived(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
    CefProcessId source_process, CefRefPtr<CefProcessMessage> message) {
  if (CefRefPtr<CefMessageRouterBrowserSide> router = QueryRouter::Get()) {
    if (router->OnProcessMessageReceived(browser, frame, source_process, message)) {
      return true;
    }
  }
  const std::string& message_name = message->GetName();
  if (message_name == "javascript-binding")
  {
    CefRefPtr<CefListValue> argList = message->GetArgumentList();
    std::string funcName = argList->GetString(0);

    for (size_t i = 0; i < m_JavascriptBindings.size(); ++i)
    {
      if(m_JavascriptBindings[i].functionName == funcName)
      {
        m_JavascriptBindings[i].function();
      }
    }
    return true;
  }
  else if (message_name == "javascript-python-binding")
  {
    CefRefPtr<CefListValue> argList = message->GetArgumentList();
    std::string funcName = argList->GetString(0);
    CefRefPtr<CefListValue> javascript_arg_types = argList->GetList(1);
    CefRefPtr<CefListValue> javascript_args = argList->GetList(2);
   // void* args = nullptr;
    int argsSize = (int)javascript_args->GetSize();

    auto* valueWrapper = new CefValueWrapper[argsSize];
    for (size_t i = 0; i < javascript_args->GetSize(); ++i) {
      std::string type = javascript_arg_types->GetString(i);

      if(type == "int")
      {
        valueWrapper->Type = 0;
        valueWrapper->IntValue = javascript_args->GetInt(i);
      }
      else if(type == "bool")
      {
        valueWrapper->Type = 1;
        valueWrapper->BoolValue = javascript_args->GetBool(i);
      }
      else if(type == "double")
      {
        valueWrapper->Type = 2;
        valueWrapper->DoubleValue = javascript_args->GetDouble(i);
      }
      else if(type == "string")
      {
        valueWrapper->Type = 3;
        valueWrapper->StringValue = javascript_args->GetString(i);
      }
      ++valueWrapper;
    }

    valueWrapper -= argsSize;

    for (size_t i = 0; i < m_JavascriptPythonBindings.size(); ++i)
    {
      if(m_JavascriptPythonBindings[i].MessageTopic == funcName)
      {
        m_JavascriptPythonBindings[i].CallHandler(argsSize, valueWrapper);
      }
    }
    delete[] valueWrapper;
    return true;
  }
  // Not one of the wrapper's messages: it is for the user's client, if there is one. The
  // wrapper's two names above never reach the user.
  return user_client_ ? user_client_->OnProcessMessageReceived(browser, frame, source_process, message)
                      : false;
}
void CefWrapperClientHandler::OnLoadingStateChange(
    CefRefPtr<CefBrowser> browser, bool isLoading, bool canGoBack,
    bool canGoForward) {
  if (browser->GetIdentifier() == primary_browser_id_) {
    m_IsReadyToExecuteJs = !isLoading;
  }
  CwLoadHandlerForward::OnLoadingStateChange(browser, isLoading, canGoBack, canGoForward);
}
