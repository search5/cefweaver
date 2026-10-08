# Declarations of the C++ wrapper in native/cefwrapper (library.h and
# javascript_binding.h). Only what the extension module uses is declared.
#
# GIL rules: calls that can block, or that run CEF callbacks, are declared
# `nogil` and must be called inside `with nogil:` (see _cefweaver.pyx).

from libcpp cimport bool as cpp_bool
from libcpp.string cimport string

from libc.stdint cimport int64_t

from cefweaver.cef_api cimport CefBrowser, CefClient, CefFrame, CefRefPtr


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


cdef extern from "library.h":
    cdef cppclass CefWrapper:
        CefWrapper()
        cpp_bool InitCefSimple(string start_url) nogil
        cpp_bool ExecuteJavascript(string code) nogil
        void ShutdownCefSimple() nogil
        cpp_bool IsRunning()
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
        void SetOffscreen(cpp_bool enabled)
        cpp_bool Offscreen()
        void SetWindowlessFrameRate(int frames_per_second)
        int WindowlessFrameRate()
        void SetQueryFunctions(string query, string cancel)
        cpp_bool AddQueryHandler(PythonQueryHandler* handler, cpp_bool first)
        cpp_bool RemoveQueryHandler(PythonQueryHandler* handler)
        cpp_bool QueryRouterExists()
