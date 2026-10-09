#include "include/cef_app.h"
#include "include/cef_command_line.h"
#include "../cefwrapper/cef_wrapper_app.h"
#include "../cefwrapper/javascript_binding.h"

#if defined(OS_WIN)
#include <windows.h>
#include "include/cef_sandbox_win.h"
#endif

#if defined(OS_MAC)
#include "include/wrapper/cef_library_loader.h"
#endif


#if defined(OS_WIN) && defined(CEF_USE_SANDBOX)
// The cef_sandbox.lib static library may not link successfully with all VS
// versions.
#pragma comment(lib, "cef_sandbox.lib")
#endif


#if defined(OS_WIN)
int APIENTRY wWinMain(HINSTANCE hInstance,
                      HINSTANCE hPrevInstance,
                      LPTSTR lpCmdLine,
                      int nCmdShow) {
  UNREFERENCED_PARAMETER(hPrevInstance);
  UNREFERENCED_PARAMETER(lpCmdLine);


  CefEnableHighDPISupport();

  void* sandbox_info = nullptr;


  CefMainArgs main_args(hInstance);
  std::vector<JavascriptBinding>placeHolder;
  std::vector<JavascriptPythonBinding>placeHolderPython;
  CefRefPtr<CefWrapperApp> app(new CefWrapperApp("", placeHolder, placeHolderPython));

  CefExecuteProcess(main_args, app.get(), sandbox_info);

  return 0;
}
#elif defined(OS_MAC)
int main(int argc, char *argv[]) {
  // libcef is not linked: the helper loads the framework that sits next to its app bundle
  // (Contents/Frameworks, where cefsubprocess.app keeps the helper apps).
  CefScopedLibraryLoader library_loader;
  if (!library_loader.LoadInHelper()) {
    return 1;
  }

  CefMainArgs main_args(argc, argv);
  std::vector<JavascriptBinding>placeHolder;
  std::vector<JavascriptPythonBinding>placeHolderPython;
  CefRefPtr<CefWrapperApp> app(new CefWrapperApp("", placeHolder, placeHolderPython));

  return CefExecuteProcess(main_args, app.get(), nullptr);
}
#else
// Chromium's zygote forks the child processes and they leave through this
// frame, with a stack canary that no longer matches the one stored on entry.
// A stack protector check here would abort every such child at exit
// ("stack smashing detected"), so it is disabled for this function only.
__attribute__((no_stack_protector))
int main(int argc, char *argv[]) {
  CefMainArgs main_args(argc, argv);
  std::vector<JavascriptBinding>placeHolder;
  std::vector<JavascriptPythonBinding>placeHolderPython;
  CefRefPtr<CefWrapperApp> app(new CefWrapperApp("", placeHolder, placeHolderPython));

  // Returns the process exit code for sub-processes (>= 0).
  return CefExecuteProcess(main_args, app.get(), nullptr);
}
#endif
