---
title: 커버리지 보고서 (생성됨)
type: reference
generated: true
sources:
  - tools/gen/scope.py
  - tools/gen/report.py
  - tools/gen/typesys.py
updated: 2026-10-10
---

# 커버리지 보고서 (생성됨)

이 페이지는 `python tools/gen/generate.py`가 CEF 154.0.34+g14c5a08+chromium-154.0.8037.98 헤더로 생성합니다. 직접 고치지 않습니다. 같은 내용을 `python tools/gen/generate.py --report`로 출력할 수 있고, 해석과 다음 단계는 [생성 범위와 커버리지](generated-api-coverage.md)에 있습니다.

```
Generated now: 1182 methods/functions in 129 classes, 20 global functions

Skipped inside the generated classes (type not supported yet):
     4  struct
     3  class
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  pointer to
     1  another overload of CreateContext is generated (Python has one name)
     1  a pointer into memory that CEF's shared memory region owns and can free while Python still holds it
     1  a pointer into memory that CEF's shared memory builder owns and can free while Python still holds it
  ----  12 skipped

If every class were generated, the type support alone would cover 1563 of 1654 methods/functions (94%).
What blocks the rest, by type:
    30  ownptr pointer
    10  rawptr pointer
     8  vector of values
     5  struct
     5  reference to a CefRefPtr
     4  vector of objects passed to a library method
     4  another overload of Create is generated (Python has one name)
     2  CEF keeps the pointer the handler returns, so the bytes would have to outlive every use
     2  a pointer into memory that V8 owns and can free while Python still holds it
     2  another overload of SetValue is generated (Python has one name)
     2  class
     2  another overload of GetAttribute is generated (Python has one name)
     2  another overload of MoveToAttribute is generated (Python has one name)
     2  struct-like value type
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  pointer to
     1  another overload of CreateContext is generated (Python has one name)
     1  a pointer into memory that CEF's shared memory region owns and can free while Python still holds it
     1  a pointer into memory that CEF's shared memory builder owns and can free while Python still holds it
     1  the release of memory that V8 shared with the host (see CreateArrayBuffer)
     1  another overload of Set is generated (Python has one name)
     1  another overload of HasValue is generated (Python has one name)
     1  another overload of DeleteValue is generated (Python has one name)
     1  another overload of GetValue is generated (Python has one name)
     1  V8 would share this memory and free it through a callback, so Python's bytes cannot be lent to it (CreateArrayBufferWithCopy copies)

Per class (supported/total methods, when every class is generated):
  * CefAccessibilityHandler                client    2/2  
    CefApiVersionTest                      library  13/31 
    CefApiVersionTestRefPtrClient          client    3/3  
    CefApiVersionTestRefPtrClientChild     client    4/4  
    CefApiVersionTestRefPtrClientChildV2   client    5/5  
    CefApiVersionTestRefPtrLibrary         library   7/8  
    CefApiVersionTestRefPtrLibraryChild    library   3/4  
    CefApiVersionTestRefPtrLibraryChildChild library   3/3  
    CefApiVersionTestRefPtrLibraryChildChildV1 library   3/4  
    CefApiVersionTestRefPtrLibraryChildChildV2 library   3/4  
    CefApiVersionTestScopedClient          client    3/3  
    CefApiVersionTestScopedClientChild     client    4/4  
    CefApiVersionTestScopedClientChildV2   client    5/5  
    CefApiVersionTestScopedLibrary         library   6/8  
    CefApiVersionTestScopedLibraryChild    library   2/4  
    CefApiVersionTestScopedLibraryChildChild library   2/3  
    CefApiVersionTestScopedLibraryChildChildV1 library   2/4  
    CefApiVersionTestScopedLibraryChildChildV2 library   2/4  
    CefApp                                 client    4/5  
  * CefAudioHandler                        client    5/5  
  * CefAuthCallback                        library   2/2  
  * CefBeforeDownloadCallback              library   1/1  
  * CefBinaryValue                         library   8/9  
  * CefBoxLayout                           library   2/2  
  * CefBrowser                             library  21/21 
  * CefBrowserHost                         library  69/72 
    CefBrowserProcessHandler               client    6/7  
  * CefBrowserView                         library   6/6  
  * CefBrowserViewDelegate                 client   21/21 
  * CefButton                              library   6/6  
  * CefButtonDelegate                      client   13/13 
  * CefCallback                            library   2/2  
  * CefClient                              client   19/19 
  * CefCommandHandler                      client    5/5  
  * CefCommandLine                         library  22/23 
  * CefCompletionCallback                  client    1/1  
  * CefComponent                           library   4/4  
  * CefComponentUpdateCallback             client    1/1  
  * CefComponentUpdater                    library   5/5  
  * CefContextMenuHandler                  client    7/7  
  * CefContextMenuParams                   library  20/20 
  * CefCookieAccessFilter                  client    2/2  
  * CefCookieManager                       library   6/6  
  * CefCookieVisitor                       client    1/1  
    CefDOMDocument                         library  14/14 
    CefDOMNode                             library  26/26 
    CefDOMVisitor                          client    1/1  
  * CefDeleteCookiesCallback               client    1/1  
  * CefDevToolsMessageObserver             client    5/5  
  * CefDialogHandler                       client    1/1  
  * CefDictionaryValue                     library  30/30 
  * CefDisplay                             library  16/16 
  * CefDisplayHandler                      client   13/13 
  * CefDownloadHandler                     client    3/3  
  * CefDownloadImageCallback               client    1/1  
  * CefDownloadItem                        library  20/20 
  * CefDownloadItemCallback                library   3/3  
  * CefDragData                            library  28/28 
  * CefDragHandler                         client    2/2  
  * CefEndTracingCallback                  client    1/1  
  * CefFileDialogCallback                  library   2/2  
  * CefFindHandler                         client    1/1  
  * CefFocusHandler                        client    3/3  
  * CefFrame                               library  26/26 
  * CefFrameHandler                        client    5/5  
  * CefImage                               library  14/14 
  * CefJSDialogCallback                    library   1/1  
  * CefJSDialogHandler                     client    4/4  
  * CefKeyboardHandler                     client    2/2  
  * CefLabelButton                         library  12/12 
  * CefLayout                              library   3/3  
  * CefLifeSpanHandler                     client    5/6  
  * CefListValue                           library  29/29 
  * CefLoadHandler                         client    4/4  
  * CefMediaAccessCallback                 library   2/2  
  * CefMediaObserver                       client    4/4  
  * CefMediaRoute                          library   5/5  
  * CefMediaRouteCreateCallback            client    1/1  
  * CefMediaRouter                         library   6/6  
  * CefMediaSink                           library   7/7  
  * CefMediaSinkDeviceInfoCallback         client    1/1  
  * CefMediaSource                         library   3/3  
  * CefMenuButton                          library   3/3  
  * CefMenuButtonDelegate                  client   14/14 
  * CefMenuModel                           library  57/57 
  * CefMenuModelDelegate                   client    7/7  
  * CefNavigationEntry                     library  10/10 
  * CefNavigationEntryVisitor              client    1/1  
  * CefOverlayController                   library  19/19 
  * CefPanel                               library  13/13 
  * CefPanelDelegate                       client   11/11 
  * CefPdfPrintCallback                    client    1/1  
  * CefPermissionHandler                   client    3/3  
  * CefPermissionPromptCallback            library   1/1  
  * CefPostData                            library   8/8  
  * CefPostDataElement                     library   9/9  
    CefPreferenceManager                   library   9/9  
  * CefPreferenceObserver                  client    1/1  
    CefPreferenceRegistrar                 library   1/1  
  * CefPrintDialogCallback                 library   2/2  
  * CefPrintHandler                        client    6/6  
  * CefPrintJobCallback                    library   1/1  
  * CefPrintSettings                       library  23/23 
  * CefProcessMessage                      library   7/7  
  * CefReadHandler                         client    5/5  
  * CefRenderHandler                       client   17/17 
    CefRenderProcessHandler                client    9/9  
  * CefRequest                             library  23/23 
  * CefRequestContext                      library  25/26 
  * CefRequestContextHandler               client    2/2  
  * CefRequestHandler                      client   11/11 
  * CefResolveCallback                     client    1/1  
    CefResourceBundle                      library   4/4  
    CefResourceBundleHandler               client    1/3  
  * CefResourceHandler                     client    7/7  
  * CefResourceReadCallback                library   1/1  
  * CefResourceRequestHandler              client    8/8  
  * CefResourceSkipCallback                library   1/1  
  * CefResponse                            library  18/18 
  * CefResponseFilter                      client    2/2  
  * CefRunContextMenuCallback              library   2/2  
  * CefRunFileDialogCallback               client    1/1  
  * CefRunQuickMenuCallback                library   2/2  
  * CefSSLInfo                             library   2/2  
  * CefSSLStatus                           library   5/5  
  * CefSchemeHandlerFactory                client    1/1  
    CefSchemeRegistrar                     library   1/1  
  * CefScrollView                          library   8/8  
  * CefSelectClientCertificateCallback     library   1/1  
  * CefServer                              library  14/14 
  * CefServerHandler                       client    8/8  
  * CefSetCookieCallback                   client    1/1  
  * CefSettingObserver                     client    1/1  
  * CefSharedMemoryRegion                  library   2/3  
  * CefSharedProcessMessageBuilder         library   4/5  
  * CefStreamReader                        library   8/8  
  * CefStreamWriter                        library   7/7  
  * CefStringVisitor                       client    1/1  
  * CefTask                                client    1/1  
  * CefTaskManager                         library   6/6  
    CefTaskRunner                          library   7/7  
    CefTestServer                          library   3/3  
    CefTestServerConnection                library   5/5  
    CefTestServerHandler                   client    1/1  
  * CefTextfield                           library  25/25 
  * CefTextfieldDelegate                   client   13/13 
    CefThread                              library   4/5  
    CefTranslatorTest                      library  43/61 
    CefTranslatorTestRefPtrClient          client    1/1  
    CefTranslatorTestRefPtrClientChild     client    2/2  
    CefTranslatorTestRefPtrLibrary         library   3/3  
    CefTranslatorTestRefPtrLibraryChild    library   3/3  
    CefTranslatorTestRefPtrLibraryChildChild library   3/3  
    CefTranslatorTestScopedClient          client    1/1  
    CefTranslatorTestScopedClientChild     client    2/2  
    CefTranslatorTestScopedLibrary         library   2/3  
    CefTranslatorTestScopedLibraryChild    library   2/3  
    CefTranslatorTestScopedLibraryChildChild library   2/3  
  * CefURLRequest                          library   8/8  
  * CefURLRequestClient                    client    5/5  
  * CefUnresponsiveProcessCallback         library   2/2  
    CefV8Accessor                          client    1/2  
    CefV8ArrayBufferReleaseCallback        client    0/1  
    CefV8BackingStore                      library   3/4  
    CefV8Context                           library  11/12 
    CefV8Exception                         library   8/8  
    CefV8Handler                           client    0/1  
    CefV8Interceptor                       client    1/4  
    CefV8StackFrame                        library   8/8  
    CefV8StackTrace                        library   4/4  
    CefV8Value                             library  56/67 
  * CefValue                               library  23/23 
  * CefView                                library  52/52 
  * CefViewDelegate                        client   11/11 
    CefWaitableEvent                       library   6/6  
  * CefWindow                              library  43/43 
  * CefWindowDelegate                      client   34/34 
  * CefWriteHandler                        client    5/5  
  * CefX509CertPrincipal                   library   7/7  
  * CefX509Certificate                     library  10/10 
    CefXmlReader                           library  26/30 
  * CefZipReader                           library  13/13 
  (* = generated now)

Opened by java-cef, not generated yet (the gaps):
  ----  0 methods

Generated, and not opened by java-cef (beyond the floor):
  CefAccessibilityHandler          2  the whole class
  CefAudioHandler                  5  the whole class
  CefBinaryValue                   8  the whole class
  CefBoxLayout                     2  the whole class
  CefBrowser                       2  2 methods
  CefBrowserHost                  39  39 methods
  CefBrowserView                   6  the whole class
  CefBrowserViewDelegate          21  the whole class
  CefButton                        6  the whole class
  CefButtonDelegate               13  the whole class
  CefClient                        6  6 methods
  CefCommandHandler                5  the whole class
  CefCommandLine                  10  10 methods
  CefComponent                     4  the whole class
  CefComponentUpdateCallback       1  the whole class
  CefComponentUpdater              5  the whole class
  CefContextMenuHandler            4  4 methods
  CefContextMenuParams             2  2 methods
  CefDeleteCookiesCallback         1  the whole class
  CefDevToolsMessageObserver       3  3 methods
  CefDictionaryValue              30  the whole class
  CefDisplay                      16  the whole class
  CefDisplayHandler                6  6 methods
  CefDownloadHandler               1  1 methods
  CefDownloadImageCallback         1  the whole class
  CefDownloadItem                  4  4 methods
  CefDragData                      4  4 methods
  CefDragHandler                   1  1 methods
  CefEndTracingCallback            1  the whole class
  CefFindHandler                   1  the whole class
  CefFrame                         5  5 methods
  CefFrameHandler                  5  the whole class
  CefImage                        14  the whole class
  CefLabelButton                  12  the whole class
  CefLayout                        3  the whole class
  CefLifeSpanHandler               1  1 methods
  CefListValue                    29  the whole class
  CefMediaAccessCallback           2  the whole class
  CefMediaObserver                 4  the whole class
  CefMediaRoute                    5  the whole class
  CefMediaRouteCreateCallback      1  the whole class
  CefMediaRouter                   6  the whole class
  CefMediaSink                     7  the whole class
  CefMediaSinkDeviceInfoCallback   1  the whole class
  CefMediaSource                   3  the whole class
  CefMenuButton                    3  the whole class
  CefMenuButtonDelegate           14  the whole class
  CefMenuModel                     8  8 methods
  CefMenuModelDelegate             7  the whole class
  CefNavigationEntry              10  the whole class
  CefNavigationEntryVisitor        1  the whole class
  CefOverlayController            19  the whole class
  CefPanel                        13  the whole class
  CefPanelDelegate                11  the whole class
  CefPermissionHandler             3  the whole class
  CefPermissionPromptCallback      1  the whole class
  CefPostData                      1  1 methods
  CefPreferenceObserver            1  the whole class
  CefProcessMessage                7  the whole class
  CefReadHandler                   5  the whole class
  CefRenderHandler                 8  8 methods
  CefRequestContext               23  23 methods
  CefRequestContextHandler         1  1 methods
  CefRequestHandler                5  5 methods
  CefResolveCallback               1  the whole class
  CefResourceRequestHandler        1  1 methods
  CefResponse                      4  4 methods
  CefResponseFilter                2  the whole class
  CefRunContextMenuCallback        2  the whole class
  CefRunQuickMenuCallback          2  the whole class
  CefSSLInfo                       2  the whole class
  CefSSLStatus                     5  the whole class
  CefScrollView                    8  the whole class
  CefSelectClientCertificateCallback   1  the whole class
  CefServer                       13  the whole class
  CefServerHandler                 8  the whole class
  CefSetCookieCallback             1  the whole class
  CefSettingObserver               1  the whole class
  CefSharedMemoryRegion            2  the whole class
  CefSharedProcessMessageBuilder   4  the whole class
  CefStreamReader                  8  the whole class
  CefStreamWriter                  7  the whole class
  CefTask                          1  the whole class
  CefTaskManager                   6  the whole class
  CefTextfield                    25  the whole class
  CefTextfieldDelegate            13  the whole class
  CefURLRequest                    3  3 methods
  CefUnresponsiveProcessCallback   2  the whole class
  CefValue                        23  the whole class
  CefView                         52  the whole class
  CefViewDelegate                 11  the whole class
  CefWindow                       43  the whole class
  CefWindowDelegate               34  the whole class
  CefX509CertPrincipal             7  the whole class
  CefX509Certificate              10  the whole class
  CefZipReader                    13  the whole class
  ----  764 methods
```

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
