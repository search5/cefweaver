#ifndef CEF_WRAPPER_RENDER_PROCESS_HANDLER_H_
#define CEF_WRAPPER_RENDER_PROCESS_HANDLER_H_
#include "include/cef_render_process_handler.h"
#include "include/wrapper/cef_message_router.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"

class SimpleRenderProcessHandler: public CefRenderProcessHandler
{
private:
    /* Here will be the instance stored. */
    static CefRefPtr<SimpleRenderProcessHandler> instance;

    /* Private constructor to prevent instancing. */
    SimpleRenderProcessHandler();

public:
    /* Static access method. */
    static CefRefPtr<SimpleRenderProcessHandler> getInstance();

    static void
    SetJavascriptBindings(std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings);
  //SimpleRenderProcessHandler::SimpleRenderProcessHandler(std::vector<JSNativeApi> nativeApi);

  void OnContextCreated(CefRefPtr<CefBrowser> browser,
                        CefRefPtr<CefFrame> frame,
                        CefRefPtr<CefV8Context> context) override ;


  void OnContextReleased(CefRefPtr<CefBrowser> browser,
                         CefRefPtr<CefFrame> frame,
                         CefRefPtr<CefV8Context> context) override;

  void OnBrowserCreated(CefRefPtr<CefBrowser> browser,
                        CefRefPtr<CefDictionaryValue> extra_info) override;

  // Sent to the browser process as "cefweaver-renderer-event" messages when its switch is given (see bridge.h).
  void OnUncaughtException(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                           CefRefPtr<CefV8Context> context, CefRefPtr<CefV8Exception> exception,
                           CefRefPtr<CefV8StackTrace> stackTrace) override;
  void OnFocusedNodeChanged(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                            CefRefPtr<CefDOMNode> node) override;

  // "cefweaver-ping": answers with "cefweaver-pong" and the same arguments, so that the browser
  // process can tell that the renderer of a frame answers (a diagnostic, and the sender that
  // lets a Python program receive a process message of its own).
  bool OnProcessMessageReceived(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                CefProcessId source_process,
                                CefRefPtr<CefProcessMessage> message) override;

  // The router of window.cefQuery(...); null if the browser process has no query handler.
  // It is made from the command line switches the browser process passes on.
  CefRefPtr<CefMessageRouterRendererSide> GetQueryRouter();

  std::vector<JavascriptBinding> m_Javascript_Bindings;
  std::vector<JavascriptPythonBinding> m_Javascript_Python_Bindings;
  bool m_QueryRouterChecked = false;
  CefRefPtr<CefMessageRouterRendererSide> m_QueryRouter;
  IMPLEMENT_REFCOUNTING(SimpleRenderProcessHandler);
};
#endif //CEF_WRAPPER_RENDER_PROCESS_HANDLER_H_

