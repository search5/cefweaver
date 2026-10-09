# Declarations of the C++ wrapper in native/cefwrapper (library.h and
# javascript_binding.h). Only what the extension module uses is declared.
#
# GIL rules: calls that can block, or that run CEF callbacks, are declared
# `nogil` and must be called inside `with nogil:` (see _cefweaver.pyx).

from libcpp cimport bool as cpp_bool
from libcpp.string cimport string

from libc.stdint cimport int64_t, uintptr_t

from cefweaver.cef_api cimport CefBrowser, CefBrowserSettings, CefClient, CefRequestContext, CefCommandLine, CefFrame, CefRefPtr


cdef extern from "runtime.h":
    # macOS: loads the CEF framework (libcef is not linked there); elsewhere it does nothing.
    cpp_bool CefWeaverLoadRuntime()


cdef extern from "javascript_binding.h":
    cdef cppclass CefValueWrapper:
        int Type  # 0: int, 1: bool, 2: double, 3: string
        int IntValue
        cpp_bool BoolValue
        double DoubleValue
        string StringValue

    # Called by CEF; the callee must not raise into C++.
    ctypedef void (*js_python_bindings_handler_function_ptr)(
        void* python_callback_object, int args_size, CefValueWrapper* args) noexcept


cdef extern from "query_router.h":
    # The answer to one query (a QueryCallback holds it); callable from any thread.
    cdef cppclass QueryCallbackHolder:
        cpp_bool Success(const string& response) nogil
        cpp_bool SuccessData(const void* data, size_t size) nogil
        cpp_bool Failure(int error_code, const string& message) nogil

    # Called by CEF on the UI thread; the callee must not raise into C++.
    ctypedef cpp_bool (*query_python_on_query_ptr)(
        void* handler, CefRefPtr[CefBrowser] browser, CefRefPtr[CefFrame] frame,
        int64_t query_id, cpp_bool binary, const void* request, size_t size,
        cpp_bool persistent, QueryCallbackHolder* callback) noexcept
    ctypedef void (*query_python_on_canceled_ptr)(
        void* handler, CefRefPtr[CefBrowser] browser, CefRefPtr[CefFrame] frame,
        int64_t query_id) noexcept

    cdef cppclass PythonQueryHandler:
        PythonQueryHandler(void* python_handler, query_python_on_query_ptr on_query,
                           query_python_on_canceled_ptr on_canceled)


cdef extern from "app_hooks.h":
    cdef cppclass SchemeRegistrarProxy:
        cpp_bool Add(const string& name, int options)

    ctypedef void (*app_command_line_ptr)(void* py, CefRefPtr[CefCommandLine] command_line) noexcept
    ctypedef void (*app_schemes_ptr)(void* py, SchemeRegistrarProxy* registrar) noexcept
    ctypedef void (*app_context_ptr)(void* py) noexcept
    ctypedef void (*app_schedule_ptr)(void* py, long long delay_ms) noexcept
    ctypedef cpp_bool (*app_relaunch_ptr)(void* py, CefRefPtr[CefCommandLine] command_line,
                                          const string& current_directory) noexcept


cdef extern from "include/cef_version_info.h":
    int cef_version_info(int entry)


cdef extern from "library.h":
    cdef cppclass CefWrapper:
        CefWrapper()
        cpp_bool InitCefSimple(string start_url) nogil
        cpp_bool ExecuteJavascript(string code) nogil
        void ShutdownCefSimple() nogil
        cpp_bool IsRunning()
        void PumpApplicationEvents()
        cpp_bool ExternalMessagePump()
        cpp_bool IsReadyToExecuteJavascript()
        void DoCefMessageLoopWork() nogil
        void AddJavascriptPythonBinding(
            string name,
            js_python_bindings_handler_function_ptr handler,
            void* python_callback_object)
        void SetCustomCefSubprocessPath(string path)
        void SetCustomCefCachePath(string path)
        void SetCustomCefResourcesPath(string path)
        void AddCommandLineSwitch(string name, string value)
        cpp_bool LoadUrl(string url) nogil
        void SetClient(CefRefPtr[CefClient] client)
        void SetDevToolsMenuEnabled(cpp_bool enabled)
        cpp_bool DevToolsMenuEnabled()
        void SetStringSetting(string name, string value)
        void SetIntSetting(string name, long long value)
        CefRefPtr[CefBrowser] CreateBrowser(string url, int offscreen, int transparent,
                                            CefRefPtr[CefRequestContext] request_context,
                                            const CefBrowserSettings* settings, int shared_texture,
                                            int64_t parent_view)
        void SetParentView(uintptr_t view)
        uintptr_t ParentView()
        void SetBrowserSettings(const CefBrowserSettings& settings)
        void SetSharedTexture(cpp_bool enabled)
        cpp_bool SharedTexture()
        void SetTransparent(cpp_bool transparent)
        cpp_bool Transparent()
        void SetOffscreen(cpp_bool enabled)
        void SetRequestContext(CefRefPtr[CefRequestContext] context)
        cpp_bool Offscreen()
        void SetWindowlessFrameRate(int frames_per_second)
        int WindowlessFrameRate()
        void SetQueryFunctions(string query, string cancel)
        void SetBridgeNames(string json)
        cpp_bool AddQueryHandler(PythonQueryHandler* handler, cpp_bool first)
        cpp_bool RemoveQueryHandler(PythonQueryHandler* handler)
        cpp_bool QueryRouterExists()
        void CancelPendingQueries(CefRefPtr[CefBrowser] browser, PythonQueryHandler* handler)
        void SetAppHooks(void* py, app_command_line_ptr command_line, app_schemes_ptr schemes,
                         app_context_ptr context, app_relaunch_ptr relaunch,
                         app_schedule_ptr schedule)
