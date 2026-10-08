---
title: 커버리지 보고서 (생성됨)
type: reference
generated: true
sources:
  - tools/gen/scope.py
  - tools/gen/report.py
  - tools/gen/typesys.py
updated: 2026-10-08
---

# 커버리지 보고서 (생성됨)

이 페이지는 `python tools/gen/generate.py`가 CEF 154.0.34+g14c5a08+chromium-154.0.8037.98 헤더로 생성합니다. 직접 고치지 않습니다. 같은 내용을 `python tools/gen/generate.py --report`로 출력할 수 있고, 해석과 다음 단계는 [생성 범위와 커버리지](generated-api-coverage.md)에 있습니다.

```
Generated now: 690 methods/functions in 72 classes, 3 global functions

Skipped inside the generated classes (type not supported yet):
    20  class
     4  struct
     3  a library method returning a client object
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  pointer to
     1  struct-like value type
     1  another overload of CreateContext is generated (Python has one name)
  ----  31 skipped

If every class were generated, the type support alone would cover 2131 of 2255 methods/functions (95%).
What blocks the rest, by type:
    32  ownptr pointer
    19  a library method returning a client object
    11  rawptr pointer
     8  vector of values
     8  struct-like value type
     7  struct
     5  reference to a CefRefPtr
     4  vector of objects passed to a library method
     4  another overload of Create is generated (Python has one name)
     2  pointer to
     2  CEF keeps the pointer the handler returns, so the bytes would have to outlive every use
     2  a pointer into memory that V8 owns and can free while Python still holds it
     2  another overload of SetValue is generated (Python has one name)
     2  class
     2  another overload of GetAttribute is generated (Python has one name)
     2  another overload of MoveToAttribute is generated (Python has one name)
     1  another overload of SetChildRefPtrClient is generated (Python has one name)
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  another overload of CreateContext is generated (Python has one name)
     1  a pointer into memory that CEF's shared memory region owns and can free while Python still holds it
     1  a pointer into memory that CEF's shared memory builder owns and can free while Python still holds it
     1  the release of memory that V8 shared with the host (see CreateArrayBuffer)
     1  another overload of Set is generated (Python has one name)
     1  another overload of HasValue is generated (Python has one name)
     1  another overload of DeleteValue is generated (Python has one name)
     1  another overload of GetValue is generated (Python has one name)
     1  V8 would share this memory and free it through a callback, so Python's bytes cannot be lent to it (CreateArrayBufferWithCopy copies)
     1  a client method returning a library object

Per class (supported/total methods, when every class is generated):
    CefAccessibilityHandler                client    2/2  
    CefApiVersionTest                      library  11/36 
    CefApiVersionTestRefPtrClient          client    5/5  
    CefApiVersionTestRefPtrClientChild     client    7/7  
    CefApiVersionTestRefPtrClientChildV2   client    7/7  
    CefApiVersionTestRefPtrLibrary         library  11/12 
    CefApiVersionTestRefPtrLibraryChild    library  13/14 
    CefApiVersionTestRefPtrLibraryChildChild library  15/15 
    CefApiVersionTestRefPtrLibraryChildChildV1 library  15/16 
    CefApiVersionTestRefPtrLibraryChildChildV2 library  15/16 
    CefApiVersionTestScopedClient          client    5/5  
    CefApiVersionTestScopedClientChild     client    7/7  
    CefApiVersionTestScopedClientChildV2   client    7/7  
    CefApiVersionTestScopedLibrary         library  10/12 
    CefApiVersionTestScopedLibraryChild    library  12/14 
    CefApiVersionTestScopedLibraryChildChild library  14/15 
    CefApiVersionTestScopedLibraryChildChildV1 library  14/16 
    CefApiVersionTestScopedLibraryChildChildV2 library  14/16 
    CefApp                                 client    4/5  
    CefAudioHandler                        client    4/5  
  * CefAuthCallback                        library   2/2  
  * CefBeforeDownloadCallback              library   1/1  
  * CefBinaryValue                         library   8/9  
    CefBoxLayout                           library   5/5  
  * CefBrowser                             library  21/21 
  * CefBrowserHost                         library  68/72 
    CefBrowserProcessHandler               client    6/7  
    CefBrowserView                         library  56/58 
    CefBrowserViewDelegate                 client   20/21 
    CefButton                              library  57/58 
    CefButtonDelegate                      client   13/13 
  * CefCallback                            library   2/2  
  * CefClient                              client   19/19 
    CefCommandHandler                      client    5/5  
  * CefCommandLine                         library  22/23 
  * CefCompletionCallback                  client    1/1  
    CefComponent                           library   4/4  
    CefComponentUpdateCallback             client    1/1  
    CefComponentUpdater                    library   5/5  
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
    CefDownloadImageCallback               client    1/1  
  * CefDownloadItem                        library  20/20 
  * CefDownloadItemCallback                library   3/3  
  * CefDragData                            library  28/28 
  * CefDragHandler                         client    2/2  
    CefEndTracingCallback                  client    1/1  
  * CefFileDialogCallback                  library   2/2  
    CefFillLayout                          library   3/3  
    CefFindHandler                         client    1/1  
  * CefFocusHandler                        client    3/3  
  * CefFrame                               library  26/26 
    CefFrameHandler                        client    5/5  
    CefImage                               library  14/14 
  * CefJSDialogCallback                    library   1/1  
  * CefJSDialogHandler                     client    4/4  
  * CefKeyboardHandler                     client    2/2  
    CefLabelButton                         library  69/70 
    CefLayout                              library   3/3  
  * CefLifeSpanHandler                     client    5/6  
  * CefListValue                           library  29/29 
  * CefLoadHandler                         client    4/4  
    CefMediaAccessCallback                 library   2/2  
    CefMediaObserver                       client    4/4  
    CefMediaRoute                          library   5/5  
    CefMediaRouteCreateCallback            client    1/1  
    CefMediaRouter                         library   6/6  
    CefMediaSink                           library   7/7  
    CefMediaSinkDeviceInfoCallback         client    1/1  
    CefMediaSource                         library   3/3  
    CefMenuButton                          library  71/72 
    CefMenuButtonDelegate                  client   14/14 
  * CefMenuModel                           library  57/57 
  * CefMenuModelDelegate                   client    7/7  
    CefNavigationEntry                     library  10/10 
    CefNavigationEntryVisitor              client    1/1  
    CefOverlayController                   library  19/19 
    CefPanel                               library  64/65 
    CefPanelDelegate                       client   11/11 
  * CefPdfPrintCallback                    client    1/1  
    CefPermissionHandler                   client    3/3  
    CefPermissionPromptCallback            library   1/1  
  * CefPostData                            library   8/8  
  * CefPostDataElement                     library   9/9  
    CefPreferenceManager                   library   9/9  
    CefPreferenceObserver                  client    1/1  
    CefPreferenceRegistrar                 library   1/1  
  * CefPrintDialogCallback                 library   2/2  
  * CefPrintHandler                        client    6/6  
  * CefPrintJobCallback                    library   1/1  
  * CefPrintSettings                       library  23/23 
  * CefProcessMessage                      library   7/7  
  * CefReadHandler                         client    5/5  
  * CefRenderHandler                       client   16/17 
    CefRenderProcessHandler                client    9/9  
  * CefRequest                             library  23/23 
  * CefRequestContext                      library  30/32 
  * CefRequestContextHandler               client    2/2  
  * CefRequestHandler                      client   11/11 
    CefResolveCallback                     client    1/1  
    CefResourceBundle                      library   4/4  
    CefResourceBundleHandler               client    1/3  
  * CefResourceHandler                     client    7/7  
  * CefResourceReadCallback                library   1/1  
  * CefResourceRequestHandler              client    8/8  
  * CefResourceSkipCallback                library   1/1  
  * CefResponse                            library  18/18 
    CefResponseFilter                      client    2/2  
  * CefRunContextMenuCallback              library   2/2  
  * CefRunFileDialogCallback               client    1/1  
  * CefRunQuickMenuCallback                library   2/2  
  * CefSSLInfo                             library   2/2  
    CefSSLStatus                           library   5/5  
  * CefSchemeHandlerFactory                client    1/1  
    CefSchemeRegistrar                     library   1/1  
    CefScrollView                          library  59/60 
    CefSelectClientCertificateCallback     library   1/1  
    CefServer                              library  14/14 
    CefServerHandler                       client    8/8  
  * CefSetCookieCallback                   client    1/1  
    CefSettingObserver                     client    1/1  
    CefSharedMemoryRegion                  library   2/3  
    CefSharedProcessMessageBuilder         library   4/5  
  * CefStreamReader                        library   8/8  
  * CefStreamWriter                        library   7/7  
  * CefStringVisitor                       client    1/1  
    CefTask                                client    1/1  
  * CefTaskManager                         library   6/6  
    CefTaskRunner                          library   5/7  
    CefTestServer                          library   3/3  
    CefTestServerConnection                library   5/5  
    CefTestServerHandler                   client    1/1  
    CefTextfield                           library  83/84 
    CefTextfieldDelegate                   client   13/13 
    CefThread                              library   4/5  
    CefTranslatorTest                      library  41/61 
    CefTranslatorTestRefPtrClient          client    1/1  
    CefTranslatorTestRefPtrClientChild     client    2/2  
    CefTranslatorTestRefPtrLibrary         library   3/3  
    CefTranslatorTestRefPtrLibraryChild    library   5/5  
    CefTranslatorTestRefPtrLibraryChildChild library   7/7  
    CefTranslatorTestScopedClient          client    1/1  
    CefTranslatorTestScopedClientChild     client    2/2  
    CefTranslatorTestScopedLibrary         library   2/3  
    CefTranslatorTestScopedLibraryChild    library   4/5  
    CefTranslatorTestScopedLibraryChildChild library   6/7  
  * CefURLRequest                          library   7/8  
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
    CefV8Value                             library  54/67 
  * CefValue                               library  23/23 
    CefView                                library  51/52 
    CefViewDelegate                        client   11/11 
    CefWaitableEvent                       library   6/6  
    CefWindow                              library 106/107
    CefWindowDelegate                      client   33/34 
  * CefWriteHandler                        client    5/5  
    CefX509CertPrincipal                   library   7/7  
    CefX509Certificate                     library  10/10 
    CefXmlReader                           library  26/30 
  * CefZipReader                           library  13/13 
  (* = generated now)

Opened by java-cef, not generated yet (the gaps):
  ----  0 methods

Generated, and not opened by java-cef (beyond the floor):
  CefBinaryValue                   8  the whole class
  CefBrowser                       2  2 methods
  CefBrowserHost                  35  35 methods
  CefClient                        1  1 methods
  CefCommandLine                  10  10 methods
  CefCompletionCallback            1  the whole class
  CefContextMenuHandler            4  4 methods
  CefContextMenuParams             2  2 methods
  CefCookieVisitor                 1  the whole class
  CefDeleteCookiesCallback         1  the whole class
  CefDevToolsMessageObserver       3  3 methods
  CefDictionaryValue              30  the whole class
  CefDisplay                      16  the whole class
  CefDisplayHandler                6  6 methods
  CefDownloadHandler               1  1 methods
  CefDownloadItem                  4  4 methods
  CefDragData                      3  3 methods
  CefDragHandler                   1  1 methods
  CefFrame                         5  5 methods
  CefLifeSpanHandler               1  1 methods
  CefListValue                    29  the whole class
  CefMenuModel                     8  8 methods
  CefMenuModelDelegate             7  the whole class
  CefPdfPrintCallback              1  the whole class
  CefPostData                      1  1 methods
  CefProcessMessage                6  the whole class
  CefReadHandler                   5  the whole class
  CefRenderHandler                 6  6 methods
  CefRequestContext               18  18 methods
  CefRequestContextHandler         1  1 methods
  CefRequestHandler                4  4 methods
  CefResponse                      4  4 methods
  CefRunContextMenuCallback        2  the whole class
  CefRunFileDialogCallback         1  the whole class
  CefRunQuickMenuCallback          2  the whole class
  CefSSLInfo                       1  the whole class
  CefSetCookieCallback             1  the whole class
  CefStreamReader                  8  the whole class
  CefStreamWriter                  7  the whole class
  CefStringVisitor                 1  the whole class
  CefTaskManager                   6  the whole class
  CefURLRequest                    2  2 methods
  CefUnresponsiveProcessCallback   2  the whole class
  CefValue                        23  the whole class
  CefZipReader                    13  the whole class
  ----  294 methods
```

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
