#ifndef CEF_WRAPPER_QUERY_ROUTER_H_
#define CEF_WRAPPER_QUERY_ROUTER_H_

// The browser side of window.cefQuery(...): CEF's message router (include/wrapper/
// cef_message_router.h, the same one java-cef uses), with query handlers that call into
// Python. The renderer side is in cef_wrapper_render_process_handler.cc; its configuration
// (the names of the two JavaScript functions) reaches the renderer process as command line
// switches.

#include <cstdint>
#include <map>
#include <mutex>
#include <string>
#include <vector>

#include "include/cef_base.h"
#include "include/wrapper/cef_message_router.h"

extern const char kQueryFunctionSwitch[];
extern const char kCancelFunctionSwitch[];

class PythonQueryHandler;

// The answer to one query. Python holds it as a QueryCallback. It answers once (a persistent
// query: until it fails or is canceled) and reports whether the answer was sent. A holder
// that is dropped while its query is still open fails the query, because CEF treats a
// destroyed callback of an open query as a runtime error.
class QueryCallbackHolder : public CefBaseRefCounted {
 public:
  QueryCallbackHolder(CefRefPtr<CefMessageRouterBrowserSide::Callback> callback,
                      PythonQueryHandler* owner, int64_t query_id, bool persistent);

  // Can be called on any thread; false if the query is closed already.
  bool Success(const std::string& response);
  bool SuccessData(const void* data, size_t size);
  bool Failure(int error_code, const std::string& message);

 private:
  friend class PythonQueryHandler;
  ~QueryCallbackHolder() override;

  // The query was canceled (or the handler removed): nothing may be sent any more.
  void Cancel();
  // The handler does not take the query: forget it without failing it.
  void Detach();

  CefRefPtr<CefMessageRouterBrowserSide::Callback> callback_;
  PythonQueryHandler* owner_;
  const int64_t query_id_;
  const bool persistent_;
  bool closed_ = false;

  IMPLEMENT_REFCOUNTING(QueryCallbackHolder);
};

// Calls into Python (functions of _cefweaver.pyx, which take the GIL and never raise).
// `request` is the text, or the bytes (`binary`) of an ArrayBuffer request.
typedef bool (*query_python_on_query_ptr)(void* handler, CefRefPtr<CefBrowser> browser,
                                          CefRefPtr<CefFrame> frame, int64_t query_id,
                                          bool binary, const void* request, size_t size,
                                          bool persistent, QueryCallbackHolder* callback);
typedef void (*query_python_on_canceled_ptr)(void* handler, CefRefPtr<CefBrowser> browser,
                                             CefRefPtr<CefFrame> frame, int64_t query_id);

class PythonQueryHandler : public CefMessageRouterBrowserSide::Handler {
 public:
  PythonQueryHandler(void* python_handler, query_python_on_query_ptr on_query,
                     query_python_on_canceled_ptr on_canceled)
      : python_handler_(python_handler), on_query_(on_query), on_canceled_(on_canceled) {}

  bool OnQuery(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame, int64_t query_id,
               const CefString& request, bool persistent,
               CefRefPtr<Callback> callback) override;
  bool OnQuery(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame, int64_t query_id,
               CefRefPtr<const CefBinaryBuffer> request, bool persistent,
               CefRefPtr<Callback> callback) override;
  void OnQueryCanceled(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame,
                       int64_t query_id) override;

 private:
  friend class QueryCallbackHolder;
  bool Dispatch(CefRefPtr<CefBrowser> browser, CefRefPtr<CefFrame> frame, int64_t query_id,
                bool binary, const void* request, size_t size, bool persistent,
                CefRefPtr<Callback> callback);
  void Forget(int64_t query_id);

  void* python_handler_;
  query_python_on_query_ptr on_query_;
  query_python_on_canceled_ptr on_canceled_;
  // The open queries this handler took, by id (guarded by the global mutex of the router).
  std::map<int64_t, QueryCallbackHolder*> pending_;
};

// The router of the browser process and the handlers that are given to it.
class QueryRouter {
 public:
  // The names of the JavaScript functions; set before the router is created.
  static void SetFunctions(const std::string& query, const std::string& cancel);
  static const std::string& QueryFunction();
  static const std::string& CancelFunction();

  // Handlers can be added before CEF starts (they are given to the router when it is
  // created) and, once the router exists, at any time on the UI thread.
  // Returns false if the handler is already there.
  static bool AddHandler(PythonQueryHandler* handler, bool first);
  static bool RemoveHandler(PythonQueryHandler* handler);
  static bool HasHandlers();
  // Cancels the pending queries of a browser and/or a handler (both null: all of them).
  static void CancelPending(CefRefPtr<CefBrowser> browser, PythonQueryHandler* handler);

  // Creates the router if there are handlers; null otherwise. Call before the first browser.
  static CefRefPtr<CefMessageRouterBrowserSide> Create();
  // The router, or null (no handlers, or CEF not started).
  static CefRefPtr<CefMessageRouterBrowserSide> Get();
  static bool Exists();
  // Called when CEF shuts down.
  static void Reset();
};

// Guards the open queries of all handlers; callbacks may be answered on any thread.
std::recursive_mutex& QueryMutex();

#endif  // CEF_WRAPPER_QUERY_ROUTER_H_
