#include "cef_wrapper_render_process_handler.h"

#include "include/cef_render_process_handler.h"
#include "include/internal/cef_ptr.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"
#include "javascript_python_binding_handler.h"
#include "include/cef_command_line.h"
#include "query_router.h"

CefRefPtr<CefMessageRouterRendererSide> SimpleRenderProcessHandler::GetQueryRouter() {
  if (!m_QueryRouterChecked) {
    m_QueryRouterChecked = true;
    CefRefPtr<CefCommandLine> line = CefCommandLine::GetGlobalCommandLine();
    if (line && line->HasSwitch(kQueryFunctionSwitch)) {
      CefMessageRouterConfig config;
      config.js_query_function = line->GetSwitchValue(kQueryFunctionSwitch);
      config.js_cancel_function = line->GetSwitchValue(kCancelFunctionSwitch);
      m_QueryRouter = CefMessageRouterRendererSide::Create(config);
    }
  }
  return m_QueryRouter;
}

void SimpleRenderProcessHandler::OnContextReleased(CefRefPtr<CefBrowser> browser,
                                                   CefRefPtr<CefFrame> frame,
                                                   CefRefPtr<CefV8Context> context) {
  if (CefRefPtr<CefMessageRouterRendererSide> router = GetQueryRouter()) {
    router->OnContextReleased(browser, frame, context);
  }
}

void SimpleRenderProcessHandler::OnBrowserCreated(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefDictionaryValue> extra_info) {
    CEF_REQUIRE_RENDERER_THREAD();


    // extra_info is null for browsers that were not created by this wrapper.
    if (!extra_info)
    {
      return;
    }

    // The renderer only needs the names: calls are forwarded to the browser
    // process, which owns the handler functions.
    if (extra_info->HasKey("JSCallbackNames"))
    {
      CefRefPtr<CefListValue> names = extra_info->GetList("JSCallbackNames");
      m_Javascript_Bindings = std::vector<JavascriptBinding>();
      for (size_t i = 0; i < names->GetSize(); ++i) {
        m_Javascript_Bindings.push_back(JavascriptBinding(names->GetString(i), nullptr));
      }
    }

    if (extra_info->HasKey("JSNativePythonApiNames"))
    {
      CefRefPtr<CefListValue> names = extra_info->GetList("JSNativePythonApiNames");
      m_Javascript_Python_Bindings = std::vector<JavascriptPythonBinding>();
      for (size_t i = 0; i < names->GetSize(); ++i) {
        m_Javascript_Python_Bindings.push_back(
            JavascriptPythonBinding(nullptr, names->GetString(i), nullptr));
      }
    }
}
bool SimpleRenderProcessHandler::OnProcessMessageReceived(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
    CefProcessId source_process, CefRefPtr<CefProcessMessage> message) {
  if (CefRefPtr<CefMessageRouterRendererSide> router = GetQueryRouter()) {
    if (router->OnProcessMessageReceived(browser, frame, source_process, message)) {
      return true;
    }
  }
  if (message->GetName() != "cefweaver-ping" || !frame) {
    return false;
  }
  CefRefPtr<CefProcessMessage> pong = CefProcessMessage::Create("cefweaver-pong");
  CefRefPtr<CefListValue> in = message->GetArgumentList();
  CefRefPtr<CefListValue> out = pong->GetArgumentList();
  out->SetSize(in->GetSize());
  for (size_t i = 0; i < in->GetSize(); ++i) {
    out->SetValue(i, in->GetValue(i));  // copies the value
  }
  frame->SendProcessMessage(PID_BROWSER, pong);
  return true;
}

/* Null, because instance will be initialized on demand. */
CefRefPtr<SimpleRenderProcessHandler> SimpleRenderProcessHandler::instance = nullptr;

CefRefPtr<SimpleRenderProcessHandler> SimpleRenderProcessHandler::getInstance()
{
    if (instance == nullptr)
    {
        instance = CefRefPtr<SimpleRenderProcessHandler>(new SimpleRenderProcessHandler());
    }

    return instance;
}

void SimpleRenderProcessHandler::SetJavascriptBindings(std::vector<JavascriptBinding> javascript_bindings, std::vector<JavascriptPythonBinding> javascript_python_bindings)
{
    getInstance()->m_Javascript_Bindings = javascript_bindings;
    getInstance()->m_Javascript_Python_Bindings = javascript_python_bindings;
}

SimpleRenderProcessHandler::SimpleRenderProcessHandler()
= default;

void SimpleRenderProcessHandler::OnContextCreated(
    CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
    CefRefPtr<CefV8Context> context) {
    //CEF_REQUIRE_RENDERER_THREAD();

    if (CefRefPtr<CefMessageRouterRendererSide> router = GetQueryRouter()) {
        router->OnContextCreated(browser, frame, context);
    }

    if (!m_Javascript_Bindings.empty())
    {
        // Retrieve the context's window object.
        CefRefPtr<CefV8Value> object = context->GetGlobal();
        CefRefPtr<CefV8Handler> handler = new JavascriptBindingsHandler(m_Javascript_Bindings, browser);
        for (size_t i = 0; i < m_Javascript_Bindings.size(); ++i)
        {
            CefRefPtr<CefV8Value> func = CefV8Value::CreateFunction(
              m_Javascript_Bindings[i].functionName, handler);
            object->SetValue(m_Javascript_Bindings[i].functionName, func, V8_PROPERTY_ATTRIBUTE_NONE);
        }
    }

    if (!m_Javascript_Python_Bindings.empty())
    {
      // Retrieve the context's window object.
      CefRefPtr<CefV8Value> object = context->GetGlobal();
      CefRefPtr<CefV8Handler> handler = new JavascriptPythonBindingsHandler(
          m_Javascript_Python_Bindings, browser);
      for (size_t i = 0; i < m_Javascript_Python_Bindings.size(); ++i)
      {
        CefRefPtr<CefV8Value> func = CefV8Value::CreateFunction(
            m_Javascript_Python_Bindings[i].MessageTopic, handler);
        object->SetValue(m_Javascript_Python_Bindings[i].MessageTopic, func, V8_PROPERTY_ATTRIBUTE_NONE);
      }
    }
}


