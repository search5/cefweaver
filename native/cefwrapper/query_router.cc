#include "query_router.h"

#include <algorithm>

const char kQueryFunctionSwitch[] = "cefweaver-query-function";
const char kCancelFunctionSwitch[] = "cefweaver-cancel-function";

std::recursive_mutex& QueryMutex() {
  static std::recursive_mutex mutex;
  return mutex;
}

// -- QueryCallbackHolder ------------------------------------------------------------------

QueryCallbackHolder::QueryCallbackHolder(
    CefRefPtr<CefMessageRouterBrowserSide::Callback> callback, PythonQueryHandler* owner,
    int64_t query_id, bool persistent)
    : callback_(callback), owner_(owner), query_id_(query_id), persistent_(persistent) {}

QueryCallbackHolder::~QueryCallbackHolder() {
  CefRefPtr<CefMessageRouterBrowserSide::Callback> open;
  PythonQueryHandler* owner;
  {
    std::lock_guard<std::recursive_mutex> lock(QueryMutex());
    owner = owner_;
    if (!closed_) {
      open = callback_;
    }
    closed_ = true;
    owner_ = nullptr;
  }
  if (open) {
    open->Failure(-1, "the query was not answered");
  }
  if (owner) {
    owner->Forget(query_id_);
  }
}

bool QueryCallbackHolder::Success(const std::string& response) {
  std::lock_guard<std::recursive_mutex> lock(QueryMutex());
  if (closed_) {
    return false;
  }
  callback_->Success(CefString(response));
  closed_ = !persistent_;
  return true;
}

bool QueryCallbackHolder::SuccessData(const void* data, size_t size) {
  std::lock_guard<std::recursive_mutex> lock(QueryMutex());
  if (closed_) {
    return false;
  }
  callback_->Success(data, size);
  closed_ = !persistent_;
  return true;
}

bool QueryCallbackHolder::Failure(int error_code, const std::string& message) {
  std::lock_guard<std::recursive_mutex> lock(QueryMutex());
  if (closed_) {
    return false;
  }
  callback_->Failure(error_code, CefString(message));
  closed_ = true;
  return true;
}

void QueryCallbackHolder::Cancel() {
  closed_ = true;  // the caller holds the mutex
}

void QueryCallbackHolder::Detach() {
  closed_ = true;
  owner_ = nullptr;
}

// -- PythonQueryHandler -------------------------------------------------------------------

bool PythonQueryHandler::Dispatch(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                  int64_t query_id, bool binary, const void* request,
                                  size_t size, bool persistent, CefRefPtr<Callback> callback) {
  CefRefPtr<QueryCallbackHolder> holder =
      new QueryCallbackHolder(callback, this, query_id, persistent);
  {
    std::lock_guard<std::recursive_mutex> lock(QueryMutex());
    pending_[query_id] = holder.get();
  }
  // Never hold the mutex while Python runs: Python code answers from other threads.
  bool handled = on_query_(python_handler_, browser, frame, query_id, binary, request, size,
                           persistent, holder.get());
  if (!handled) {
    std::lock_guard<std::recursive_mutex> lock(QueryMutex());
    pending_.erase(query_id);
    holder->Detach();
  }
  return handled;
}

bool PythonQueryHandler::OnQuery(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                 int64_t query_id, const CefString& request, bool persistent,
                                 CefRefPtr<Callback> callback) {
  const std::string text = request.ToString();
  return Dispatch(browser, frame, query_id, false, text.data(), text.size(), persistent,
                  callback);
}

bool PythonQueryHandler::OnQuery(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                                 int64_t query_id, CefRefPtr<const CefBinaryBuffer> request,
                                 bool persistent, CefRefPtr<Callback> callback) {
  return Dispatch(browser, frame, query_id, true, request->GetData(), request->GetSize(),
                  persistent, callback);
}

void PythonQueryHandler::OnQueryCanceled(CefRefPtr<CefBrowser> browser,
                                         CefRefPtr<CefFrame> frame, int64_t query_id) {
  {
    std::lock_guard<std::recursive_mutex> lock(QueryMutex());
    auto found = pending_.find(query_id);
    if (found != pending_.end()) {
      found->second->Cancel();
      pending_.erase(found);
    }
  }
  on_canceled_(python_handler_, browser, frame, query_id);
}

void PythonQueryHandler::Forget(int64_t query_id) {
  std::lock_guard<std::recursive_mutex> lock(QueryMutex());
  pending_.erase(query_id);
}

// -- QueryRouter --------------------------------------------------------------------------

namespace {
std::string g_query_function = "cefQuery";
std::string g_cancel_function = "cefQueryCancel";
std::vector<std::pair<PythonQueryHandler*, bool>> g_handlers;  // handler, first
CefRefPtr<CefMessageRouterBrowserSide> g_router;
}  // namespace

void QueryRouter::SetFunctions(const std::string& query, const std::string& cancel) {
  g_query_function = query;
  g_cancel_function = cancel;
}
const std::string& QueryRouter::QueryFunction() { return g_query_function; }
const std::string& QueryRouter::CancelFunction() { return g_cancel_function; }

bool QueryRouter::AddHandler(PythonQueryHandler* handler, bool first) {
  for (const auto& entry : g_handlers) {
    if (entry.first == handler) {
      return false;
    }
  }
  g_handlers.emplace_back(handler, first);
  if (g_router) {
    g_router->AddHandler(handler, first);
  }
  return true;
}

bool QueryRouter::RemoveHandler(PythonQueryHandler* handler) {
  auto found = std::find_if(g_handlers.begin(), g_handlers.end(),
                            [handler](const auto& entry) { return entry.first == handler; });
  if (found == g_handlers.end()) {
    return false;
  }
  g_handlers.erase(found);
  if (g_router) {
    g_router->RemoveHandler(handler);
  }
  return true;
}

bool QueryRouter::HasHandlers() { return !g_handlers.empty(); }
void QueryRouter::CancelPending(CefRefPtr<CefBrowser> browser, PythonQueryHandler* handler) {
  if (g_router) {
    g_router->CancelPending(browser, handler);
  }
}

CefRefPtr<CefMessageRouterBrowserSide> QueryRouter::Create() {
  if (!g_router && !g_handlers.empty()) {
    CefMessageRouterConfig config;
    config.js_query_function = g_query_function;
    config.js_cancel_function = g_cancel_function;
    g_router = CefMessageRouterBrowserSide::Create(config);
    for (const auto& entry : g_handlers) {
      g_router->AddHandler(entry.first, entry.second);
    }
  }
  return g_router;
}

CefRefPtr<CefMessageRouterBrowserSide> QueryRouter::Get() { return g_router; }
bool QueryRouter::Exists() { return g_router != nullptr; }
void QueryRouter::Reset() { g_router = nullptr; }
