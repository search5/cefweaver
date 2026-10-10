#include "cef_wrapper_render_process_handler.h"

#include "include/cef_render_process_handler.h"
#include "include/internal/cef_ptr.h"
#include "javascript_binding.h"
#include "javascript_bindings_handler.h"
#include "javascript_python_binding_handler.h"
#include "include/cef_command_line.h"
#include "query_router.h"
#include "bridge.h"
#include "include/cef_dom.h"
#include "include/cef_v8.h"

#include <map>
#include <string>
#include <utility>

namespace {

// The contexts that cefweaver.JavascriptBridge.evaluate() runs sources in, by (browser, frame): the context and the
// function of the shim that reports an outcome. Renderer thread only.
struct EvalContext {
  CefRefPtr<CefV8Context> context;
  CefRefPtr<CefV8Value> settle;
};
std::map<std::pair<int, std::string>, EvalContext>& EvalContexts() {
  static std::map<std::pair<int, std::string>, EvalContext> contexts;
  return contexts;
}
std::pair<int, std::string> EvalKey(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame) {
  return {browser ? browser->GetIdentifier() : 0, frame ? frame->GetIdentifier().ToString() : std::string()};
}
// "Uncaught SyntaxError: ..." as "SyntaxError: ..." (the form of the error of a page's own exception).
std::string ErrorText(CefRefPtr<CefV8Exception> exception) {
  std::string text = exception ? exception->GetMessage().ToString() : "error";
  const std::string prefix = "Uncaught ";
  return text.compare(0, prefix.size(), prefix) == 0 ? text.substr(prefix.size()) : text;
}

// True if the browser process asked for the events of the renderer (the switch of bridge.h).
bool RendererEventsOn() {
  static const bool on = [] {
    CefRefPtr<CefCommandLine> line = CefCommandLine::GetGlobalCommandLine();
    return line && line->HasSwitch(kRendererEventsSwitch);
  }();
  return on;
}

// "cefweaver-renderer-event" with the kind of the event first; the browser process gets it as a process message
// (the user's Client.on_process_message_received, which cefweaver.RendererEvents decodes).
CefRefPtr<CefProcessMessage> NewEvent(const char* kind) {
  CefRefPtr<CefProcessMessage> message = CefProcessMessage::Create(kRendererEventMessage);
  message->GetArgumentList()->SetString(0, kind);
  return message;
}

void SendEvent(CefRefPtr<CefFrame> frame, CefRefPtr<CefProcessMessage> message) {
  if (frame && frame->IsValid()) {
    frame->SendProcessMessage(PID_BROWSER, message);
  }
}

}  // namespace

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
  if (frame) {
    // Only the entry of this very context: a new context of the frame may have been entered first.
    auto found = EvalContexts().find(EvalKey(browser, frame));
    if (found != EvalContexts().end() && found->second.context->IsSame(context)) {
      EvalContexts().erase(found);
    }
  }
  if (RendererEventsOn() && frame && frame->IsValid()) {
    CefRefPtr<CefProcessMessage> message = NewEvent("context-released");
    message->GetArgumentList()->SetBool(1, frame->IsMain());
    message->GetArgumentList()->SetString(2, frame->GetURL());
    // The browser process drops a message of a frame it has already replaced (the page was left): it goes through
    // the main frame of the browser, which is the current one.
    CefRefPtr<CefFrame> main = browser ? browser->GetMainFrame() : nullptr;
    SendEvent(main && main->IsValid() ? main : frame, message);
  }
}

void SimpleRenderProcessHandler::OnUncaughtException(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                                     CefRefPtr<CefV8Context> context,
                                                     CefRefPtr<CefV8Exception> exception,
                                                     CefRefPtr<CefV8StackTrace> stackTrace) {
  if (!RendererEventsOn() || !exception) {
    return;
  }
  CefRefPtr<CefProcessMessage> message = NewEvent("uncaught-exception");
  CefRefPtr<CefListValue> args = message->GetArgumentList();
  args->SetString(1, exception->GetMessage());
  args->SetString(2, exception->GetSourceLine());
  args->SetString(3, exception->GetScriptResourceName());
  args->SetInt(4, exception->GetLineNumber());
  args->SetInt(5, exception->GetStartColumn());
  args->SetInt(6, exception->GetEndColumn());
  CefRefPtr<CefListValue> frames = CefListValue::Create();
  if (stackTrace) {
    for (int i = 0; i < stackTrace->GetFrameCount(); ++i) {
      CefRefPtr<CefV8StackFrame> entry = stackTrace->GetFrame(i);
      CefRefPtr<CefListValue> item = CefListValue::Create();
      item->SetString(0, entry->GetFunctionName());
      item->SetString(1, entry->GetScriptName());
      item->SetInt(2, entry->GetLineNumber());
      item->SetInt(3, entry->GetColumn());
      frames->SetList(i, item);
    }
  }
  args->SetList(7, frames);
  SendEvent(frame, message);
}

void SimpleRenderProcessHandler::OnFocusedNodeChanged(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                                      CefRefPtr<CefDOMNode> node) {
  if (!RendererEventsOn()) {
    return;
  }
  CefRefPtr<CefProcessMessage> message = NewEvent("focused-node");
  CefRefPtr<CefListValue> args = message->GetArgumentList();
  if (node) {                                         // no node: the focus left every node of the page
    args->SetBool(1, true);
    args->SetBool(2, node->IsEditable());
    args->SetString(3, node->IsElement() ? node->GetElementTagName() : CefString());
    const CefRect bounds = node->IsElement() ? node->GetElementBounds() : CefRect();
    args->SetInt(4, bounds.x);
    args->SetInt(5, bounds.y);
    args->SetInt(6, bounds.width);
    args->SetInt(7, bounds.height);
  } else {
    args->SetBool(1, false);
  }
  SendEvent(frame, message);
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
  if (message->GetName() == "cefweaver-eval" && frame) {
    CefRefPtr<CefListValue> arguments = message->GetArgumentList();
    auto found = EvalContexts().find(EvalKey(browser, frame));
    if (found == EvalContexts().end()) {
      return true;
    }
    EvalContext entry = found->second;
    CefRefPtr<CefV8Context> current = frame->IsValid() ? frame->GetV8Context() : nullptr;
    if (!current || !current->IsSame(entry.context)) {  // a context that was left
      EvalContexts().erase(found);
      return true;
    }
    // In a block: a let or const of the source does not stay in the page (a second source of the same name would fail).
    const std::string source = "{\n" + arguments->GetString(1).ToString() + "\n}";
    if (entry.context->Enter()) {
      CefRefPtr<CefV8Value> value;
      CefRefPtr<CefV8Exception> exception;
      const bool ok = entry.context->Eval(source, "cefweaver-evaluate", 0, value, exception);
      CefV8ValueList outcome;
      outcome.push_back(CefV8Value::CreateInt(arguments->GetInt(0)));
      outcome.push_back(CefV8Value::CreateBool(ok));
      outcome.push_back(ok ? (value ? value : CefV8Value::CreateUndefined()) : CefV8Value::CreateString(ErrorText(exception)));
      CefRefPtr<CefV8Value> delivered = entry.settle->ExecuteFunction(nullptr, outcome);
      if (!delivered) {
        // CEF's value type cannot carry this result (a BigInt, say): tell the error instead of losing the answer.
        CefV8ValueList failure;
        failure.push_back(CefV8Value::CreateInt(arguments->GetInt(0)));
        failure.push_back(CefV8Value::CreateBool(false));
        failure.push_back(CefV8Value::CreateString("TypeError: the result cannot be passed to the bridge"));
        entry.settle->ExecuteFunction(nullptr, failure);
      }
      entry.context->Exit();
    }
    return true;
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
    if (RendererEventsOn() && frame && frame->IsValid()) {
        CefRefPtr<CefProcessMessage> event = NewEvent("context-created");
        event->GetArgumentList()->SetBool(1, frame->IsMain());
        event->GetArgumentList()->SetString(2, frame->GetURL());
        SendEvent(frame, event);
    }

    // The functions Python exposes (cefweaver.JavascriptBridge): after the router, whose
    // query function they use.
    CefRefPtr<CefCommandLine> line = CefCommandLine::GetGlobalCommandLine();
    if (line && line->HasSwitch(kBridgeSwitch) && line->HasSwitch(kQueryFunctionSwitch)) {
        // The names are identifiers checked in Python and the query function is quoted as
        // JSON, so neither can end the expression.
        std::string code = std::string("(") + kBridgeShim + ")(" +
                           line->GetSwitchValue(kBridgeSwitch).ToString() + ",\"" +
                           line->GetSwitchValue(kQueryFunctionSwitch).ToString() + "\");";
        CefRefPtr<CefV8Value> result;
        CefRefPtr<CefV8Exception> exception;
        if (context->Eval(code, "cefweaver-bridge", 0, result, exception) && result && result->IsFunction() && frame) {
            EvalContexts()[EvalKey(browser, frame)] = {context, result};
        }
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


