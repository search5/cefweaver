#ifndef CEF_WRAPPER_BROWSER_PROCESS_HANDLER_H
#define CEF_WRAPPER_BROWSER_PROCESS_HANDLER_H

#include "include/cef_browser_process_handler.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"
class CefWrapperBrowserProcessHandler : public CefBrowserProcessHandler
{
private:
  /* Here will be the instance stored. */
  static CefRefPtr<CefWrapperBrowserProcessHandler> instance;

  /* Private constructor to prevent instancing. */
  CefWrapperBrowserProcessHandler();

public:
  /* Static access method. */
  static CefRefPtr<CefWrapperBrowserProcessHandler> GetInstance();
  static void SetJavascriptBindings(std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings);
  // The client whose handlers get the browser events (empty for none). Set before CEF starts.
  static void SetUserClient(CefRefPtr<CefClient> client);
  static void SetStartUrl(std::string url);
  // The request context of the first browser (none: the global one). Set before it is created.
  static void SetRequestContext(CefRefPtr<CefRequestContext> context);
  static void LoadUrl(std::string url);
  // A browser as java-cef's CefClient.createBrowser(): on the UI thread, once CEF runs. The
  // first browser is made by OnContextInitialized() the same way.
  // `settings` (null: the app's, see SetBrowserSettings()) fills CefBrowserSettings; what the
  // app decides on top of it is the frame rate and, for an opaque offscreen browser, the colour.
  static CefRefPtr<CefBrowser> CreateBrowser(const std::string& url, bool offscreen,
                                             bool transparent,
                                             CefRefPtr<CefRequestContext> request_context,
                                             const CefBrowserSettings* settings = nullptr,
                                             bool shared_texture = false,
                                             uintptr_t parent_view = 0);
  static void SetBrowserSettings(const CefBrowserSettings& settings);
  CefRefPtr<CefBrowser>Browser;
  CefRefPtr<CefClient> m_UserClient;
  std::vector<JavascriptBinding> m_JavascriptBindings;
  std::vector<JavascriptPythonBinding> m_JavascriptPythonBindings;
  CefRefPtr<CefClient> GetDefaultClient()  override;
  void OnContextInitialized() override;
  // CEF wants the message loop to run in delay_ms (with the setting external_message_pump);
  // it may be called on any thread.
  void OnScheduleMessagePumpWork(int64_t delay_ms) override;
  // A second start of the application (with the same user data) reaches the first one here.
  bool OnAlreadyRunningAppRelaunch(CefRefPtr<CefCommandLine> command_line,
                                   const CefString& current_directory) override;
  // Gives the renderer processes the names of the message router functions (only a few
  // switches of the browser process reach a child process by themselves).
  void OnBeforeChildProcessLaunch(CefRefPtr<CefCommandLine> command_line) override;

  std::string StartUrl;
  CefRefPtr<CefRequestContext> m_RequestContext;
  CefBrowserSettings m_BrowserSettings;

  IMPLEMENT_REFCOUNTING(CefWrapperBrowserProcessHandler);

};
#endif // CEF_WRAPPER_BROWSER_PROCESS_HANDLER_H
