# Declarations of the C++ wrapper in native/cefwrapper (library.h and
# javascript_binding.h). Only what the extension module uses is declared.
#
# GIL rules: calls that can block, or that run CEF callbacks, are declared
# `nogil` and must be called inside `with nogil:` (see _cefweaver.pyx).

from libcpp cimport bool as cpp_bool
from libcpp.string cimport string


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
