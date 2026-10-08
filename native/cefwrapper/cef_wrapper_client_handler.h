#ifndef CEF_WRAPPER_CLIENT_HANDLER_H_
#define CEF_WRAPPER_CLIENT_HANDLER_H_

#include "include/cef_client.h"
#include "include/cef_request_handler.h"
#include "include/wrapper/cef_message_router.h"

#include <list>

#include "generated/cefweaver_proxies.h"
#include "global_vars.h"
#include "include/wrapper/cef_helpers.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"


// The client of every browser. It does what the wrapper needs for itself (the list of
// browsers, the ready flag, the error page, the window title, the JavaScript bindings)
// and passes the display, life span and load events on to the handlers of the user's
// client (`user_client`, a generated proxy of a Python object), if there is one.
//
// The Cw...Forward base classes are generated (cefweaver_proxies.h). Each forwards to
// the handler in its forward_..._ member, which GetDisplayHandler() and the like fill
// from the user's client every time CEF asks for the handler.
class CefWrapperClientHandler : public CefClient,
                      public CwRequestHandlerForward,
                      public CwDisplayHandlerForward,
                      public CwDragHandlerForward,
                      public CwLifeSpanHandlerForward,
                      public CwLoadHandlerForward,
                      public CwRenderHandlerForward,
                      public CwFocusHandlerForward,
                      public CwJSDialogHandlerForward,
                      public CwDialogHandlerForward,
                      public CwDownloadHandlerForward,
                      public CwKeyboardHandlerForward,
                      public CwPrintHandlerForward,
                      public CwContextMenuHandlerForward {
public:

  explicit CefWrapperClientHandler(bool use_views,
                std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings,
                CefRefPtr<CefClient> user_client = nullptr);

  void OnLoadStart(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                   TransitionType transition_type) override;
  ~CefWrapperClientHandler() override;

  // Provide access to the single global instance of this object.
  static CefWrapperClientHandler *GetInstance();

  void OnBeforeContextMenu(CefRefPtr<CefBrowser> browser,
                           CefRefPtr<CefFrame> frame,
                           CefRefPtr<CefContextMenuParams> params,
                           CefRefPtr<CefMenuModel> model) override;

  bool OnContextMenuCommand(CefRefPtr<CefBrowser> browser,
                            CefRefPtr<CefFrame> frame,
                            CefRefPtr<CefContextMenuParams> params,
                            int command_id, EventFlags event_flags) override;

  // The context menu handler is the wrapper's only if the user has one or the DevTools items
  // are on; otherwise CEF keeps its default menu. Turning the items on or off changes nothing
  // else: the user's handler sees the same events either way.
  CefRefPtr<CefContextMenuHandler> GetContextMenuHandler() override {
    forward_context_menu_handler_ =
        user_client_ ? user_client_->GetContextMenuHandler() : nullptr;
    return (forward_context_menu_handler_ || g_DevToolsMenuEnabled.load()) ? this : nullptr;
  }

  // The wrapper has a request handler for the message router (a navigation and the end of the
  // renderer cancel the queries of a page) and passes every event on to the user's request
  // handler. CEF gets this one if either of them exists.
  CefRefPtr<CefRequestHandler> GetRequestHandler() override;
  bool OnBeforeBrowse(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                      CefRefPtr<CefRequest> request, bool user_gesture,
                      bool is_redirect) override;
  void OnRenderProcessTerminated(CefRefPtr<CefBrowser> browser, TerminationStatus status,
                                 int error_code, const CefString& error_string) override;

  // Show a new DevTools popup window.
  void ShowDevTools(CefRefPtr<CefBrowser> browser,
                    const CefPoint &inspect_element_at);

  // Close the existing DevTools popup window, if any.
  void CloseDevTools(CefRefPtr<CefBrowser> browser);

  // CefClient methods:
  CefRefPtr<CefDisplayHandler> GetDisplayHandler() override {
    forward_display_handler_ = user_client_ ? user_client_->GetDisplayHandler() : nullptr;
    return this;
  }

  // Nothing in the wrapper needs the drag events: they only go to the user's handler.
  CefRefPtr<CefDragHandler> GetDragHandler() override {
    forward_drag_handler_ = user_client_ ? user_client_->GetDragHandler() : nullptr;
    return forward_drag_handler_ ? this : nullptr;
  }

  CefRefPtr<CefLifeSpanHandler> GetLifeSpanHandler() override {
    forward_life_span_handler_ = user_client_ ? user_client_->GetLifeSpanHandler() : nullptr;
    return this;
  }

  // Nothing in the wrapper needs the paint events: they only go to the user's handler.
  CefRefPtr<CefRenderHandler> GetRenderHandler() override {
    forward_render_handler_ = user_client_ ? user_client_->GetRenderHandler() : nullptr;
    return forward_render_handler_ ? this : nullptr;
  }

  // The wrapper does not use the focus, dialog and download events either: they go to the
  // user's handlers, and CEF keeps its own behavior (a dialog, a download) without one.
  CefRefPtr<CefFocusHandler> GetFocusHandler() override {
    forward_focus_handler_ = user_client_ ? user_client_->GetFocusHandler() : nullptr;
    return forward_focus_handler_ ? this : nullptr;
  }
  CefRefPtr<CefJSDialogHandler> GetJSDialogHandler() override {
    forward_js_dialog_handler_ = user_client_ ? user_client_->GetJSDialogHandler() : nullptr;
    return forward_js_dialog_handler_ ? this : nullptr;
  }
  CefRefPtr<CefDialogHandler> GetDialogHandler() override {
    forward_dialog_handler_ = user_client_ ? user_client_->GetDialogHandler() : nullptr;
    return forward_dialog_handler_ ? this : nullptr;
  }
  CefRefPtr<CefDownloadHandler> GetDownloadHandler() override {
    forward_download_handler_ = user_client_ ? user_client_->GetDownloadHandler() : nullptr;
    return forward_download_handler_ ? this : nullptr;
  }

  CefRefPtr<CefKeyboardHandler> GetKeyboardHandler() override {
    forward_keyboard_handler_ = user_client_ ? user_client_->GetKeyboardHandler() : nullptr;
    return forward_keyboard_handler_ ? this : nullptr;
  }

  CefRefPtr<CefPrintHandler> GetPrintHandler() override {
    forward_print_handler_ = user_client_ ? user_client_->GetPrintHandler() : nullptr;
    return forward_print_handler_ ? this : nullptr;
  }

  CefRefPtr<CefLoadHandler> GetLoadHandler() override {
    forward_load_handler_ = user_client_ ? user_client_->GetLoadHandler() : nullptr;
    return this;
  }

  // CefDisplayHandler methods:
  void OnTitleChange(CefRefPtr<CefBrowser> browser,
                     const CefString &title) override;

  // CefLifeSpanHandler methods:
  void OnAfterCreated(CefRefPtr<CefBrowser> browser) override;
  bool DoClose(CefRefPtr<CefBrowser> browser) override;
  // An offscreen browser has no window for a popup (java-cef blocks them as well); in a
  // windowed one the user's handler decides, as before, and CEF opens the popup by default.
  bool OnBeforePopup(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame, int popup_id,
                     const CefString& target_url, const CefString& target_frame_name,
                     cef_window_open_disposition_t target_disposition, bool user_gesture,
                     const CefPopupFeatures& popupFeatures, CefWindowInfo& windowInfo,
                     CefRefPtr<CefClient>& client, CefBrowserSettings& settings,
                     CefRefPtr<CefDictionaryValue>& extra_info,
                     bool* no_javascript_access) override;
  void OnBeforeClose(CefRefPtr<CefBrowser> browser) override;

  // CefLoadHandler methods:
  void OnLoadError(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                   ErrorCode errorCode, const CefString &errorText,
                   const CefString &failedUrl) override;

  // Request that all existing m_Browser windows close.
  void CloseAllBrowsers(bool force_close);

  bool IsClosing() const { return is_closing_; }
  bool HasOpenBrowsers() const { return !browser_list_.empty(); }

  // Returns true if the Chrome runtime is enabled.
  static bool IsChromeRuntimeEnabled();
  void OnLoadEnd(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                 int httpStatusCode) override;

  bool IsReadyToExecuteJs();
  bool OnProcessMessageReceived(CefRefPtr<CefBrowser> browser,
                                CefRefPtr<CefFrame> frame,
                                CefProcessId source_process,
                                CefRefPtr<CefProcessMessage> message) override;
  void OnLoadingStateChange(CefRefPtr<CefBrowser> browser, bool isLoading,
                            bool canGoBack, bool canGoForward) override;


private:
  // Platform-specific implementation.
  void PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                           const CefString &title);

  // True if the application is using the Views framework.
  const bool use_views_;

  // The client given by the user (empty if there is none).
  CefRefPtr<CefClient> user_client_;

  // List of existing m_Browser windows. Only accessed on the CEF UI thread.
  using BrowserList = std::list<CefRefPtr<CefBrowser>>;
  BrowserList browser_list_;

  bool m_IsReadyToExecuteJs = false;
  std::vector<JavascriptBinding> m_JavascriptBindings;
  std::vector<JavascriptPythonBinding> m_JavascriptPythonBindings;
  bool is_closing_;

  // Include the default reference counting implementation.
  IMPLEMENT_REFCOUNTING(CefWrapperClientHandler);
};

#endif // CEF_WRAPPER_CLIENT_HANDLER_H_
