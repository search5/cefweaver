#include "cef_wrapper_client_handler.h"

#include <windows.h>
#include <string>

#include "include/cef_browser.h"

bool CefWrapperClientHandler::PlatformCloseView(CefRefPtr<CefBrowser>) { return false; }
bool CefWrapperClientHandler::PlatformCloseFinishing(CefRefPtr<CefBrowser>) { return false; }

void CefWrapperClientHandler::PlatformTitleChange(CefRefPtr<CefBrowser> browser,
                                        const CefString& title) {
  CefWindowHandle hwnd = browser->GetHost()->GetWindowHandle();
  if (hwnd)
    SetWindowText(hwnd, reinterpret_cast<LPCWSTR>(title.c_str()));
}
