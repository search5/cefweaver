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
Generated now: 560 methods/functions in 55 classes, 3 global functions

Skipped inside the generated classes (type not supported yet):
    25  class
     7  struct
     5  multimap of values
     4  struct-like value type
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  a library method returning a client object
  ----  43 skipped

If every class were generated, the type support alone would cover 1469 of 1598 methods/functions (92%).
What blocks the rest, by type:
    32  ownptr pointer
    19  struct
    12  struct-like value type
    11  a library method returning a client object
    11  rawptr pointer
     9  multimap of values
     8  vector of values
     5  reference to a CefRefPtr
     4  vector of objects passed to a library method
     4  map of values
     2  pointer to
     2  CEF keeps the pointer the handler returns, so the bytes would have to outlive every use
     2  a pointer into memory that V8 owns and can free while Python still holds it
     2  class
     1  a pointer into memory that CEF owns and can free while Python still holds it (get_data() copies the bytes)
     1  a pointer into memory that CEF's shared memory region owns and can free while Python still holds it
     1  a pointer into memory that CEF's shared memory builder owns and can free while Python still holds it
     1  the release of memory that V8 shared with the host (see CreateArrayBuffer)
     1  V8 would share this memory and free it through a callback, so Python's bytes cannot be lent to it (CreateArrayBufferWithCopy copies)
     1  a client method returning a library object

Per class (supported/total methods, when every class is generated):
    CefAccessibilityHandler                client    2/2  
    CefApiVersionTest                      library  12/36 
    CefApiVersionTestRefPtrClient          client    5/5  
    CefApiVersionTestRefPtrClientChild     client    2/2  
    CefApiVersionTestRefPtrClientChildV2   client    2/2  
    CefApiVersionTestRefPtrLibrary         library  12/12 
    CefApiVersionTestRefPtrLibraryChild    library   4/4  
    CefApiVersionTestRefPtrLibraryChildChild library   3/3  
    CefApiVersionTestRefPtrLibraryChildChildV1 library   4/4  
    CefApiVersionTestRefPtrLibraryChildChildV2 library   4/4  
    CefApiVersionTestScopedClient          client    5/5  
    CefApiVersionTestScopedClientChild     client    2/2  
    CefApiVersionTestScopedClientChildV2   client    2/2  
    CefApiVersionTestScopedLibrary         library  10/12 
    CefApiVersionTestScopedLibraryChild    library   2/4  
    CefApiVersionTestScopedLibraryChildChild library   2/3  
    CefApiVersionTestScopedLibraryChildChildV1 library   2/4  
    CefApiVersionTestScopedLibraryChildChildV2 library   2/4  
    CefApp                                 client    4/5  
    CefAudioHandler                        client    4/5  
  * CefAuthCallback                        library   2/2  
  * CefBeforeDownloadCallback              library   1/1  
  * CefBinaryValue                         library   8/9  
    CefBoxLayout                           library   2/2  
  * CefBrowser                             library  21/21 
  * CefBrowserHost                         library  65/72 
    CefBrowserProcessHandler               client    6/7  
    CefBrowserView                         library   5/6  
    CefBrowserViewDelegate                 client    9/10 
    CefButton                              library   6/6  
    CefButtonDelegate                      client    2/2  
  * CefCallback                            library   2/2  
  * CefClient                              client   19/19 
    CefCommandHandler                      client    5/5  
    CefCommandLine                         library  21/23 
    CefCompletionCallback                  client    1/1  
    CefComponent                           library   4/4  
    CefComponentUpdateCallback             client    1/1  
    CefComponentUpdater                    library   5/5  
  * CefContextMenuHandler                  client    7/7  
  * CefContextMenuParams                   library  20/20 
    CefCookieAccessFilter                  client    0/2  
    CefCookieManager                       library   5/6  
    CefCookieVisitor                       client    0/1  
    CefDOMDocument                         library  14/14 
    CefDOMNode                             library  25/26 
    CefDOMVisitor                          client    1/1  
    CefDeleteCookiesCallback               client    1/1  
    CefDevToolsMessageObserver             client    5/5  
  * CefDialogHandler                       client    1/1  
  * CefDictionaryValue                     library  30/30 
  * CefDisplay                             library  16/16 
  * CefDisplayHandler                      client   12/13 
  * CefDownloadHandler                     client    3/3  
    CefDownloadImageCallback               client    1/1  
  * CefDownloadItem                        library  20/20 
  * CefDownloadItemCallback                library   3/3  
    CefDragData                            library  28/28 
  * CefDragHandler                         client    2/2  
    CefEndTracingCallback                  client    1/1  
  * CefFileDialogCallback                  library   2/2  
    CefFindHandler                         client    1/1  
  * CefFocusHandler                        client    3/3  
  * CefFrame                               library  26/26 
    CefFrameHandler                        client    5/5  
    CefImage                               library  14/14 
  * CefJSDialogCallback                    library   1/1  
  * CefJSDialogHandler                     client    4/4  
  * CefKeyboardHandler                     client    2/2  
    CefLabelButton                         library  12/12 
    CefLayout                              library   3/3  
  * CefLifeSpanHandler                     client    4/6  
  * CefListValue                           library  29/29 
  * CefLoadHandler                         client    4/4  
    CefMediaAccessCallback                 library   2/2  
    CefMediaObserver                       client    4/4  
    CefMediaRoute                          library   5/5  
    CefMediaRouteCreateCallback            client    1/1  
    CefMediaRouter                         library   6/6  
    CefMediaSink                           library   7/7  
    CefMediaSinkDeviceInfoCallback         client    0/1  
    CefMediaSource                         library   3/3  
    CefMenuButton                          library   3/3  
    CefMenuButtonDelegate                  client    1/1  
  * CefMenuModel                           library  57/57 
  * CefMenuModelDelegate                   client    7/7  
    CefNavigationEntry                     library  10/10 
    CefNavigationEntryVisitor              client    1/1  
    CefOverlayController                   library  19/19 
    CefPanel                               library  13/13 
    CefPdfPrintCallback                    client    1/1  
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
  * CefRequest                             library  20/23 
    CefRequestContext                      library  24/26 
    CefRequestContextHandler               client    2/2  
  * CefRequestHandler                      client   11/11 
    CefResolveCallback                     client    1/1  
    CefResourceBundle                      library   4/4  
    CefResourceBundleHandler               client    1/3  
  * CefResourceHandler                     client    7/7  
  * CefResourceReadCallback                library   1/1  
  * CefResourceRequestHandler              client    8/8  
  * CefResourceSkipCallback                library   1/1  
  * CefResponse                            library  16/18 
    CefResponseFilter                      client    2/2  
  * CefRunContextMenuCallback              library   2/2  
    CefRunFileDialogCallback               client    1/1  
  * CefRunQuickMenuCallback                library   2/2  
  * CefSSLInfo                             library   2/2  
    CefSSLStatus                           library   5/5  
  * CefSchemeHandlerFactory                client    1/1  
    CefSchemeRegistrar                     library   1/1  
    CefScrollView                          library   8/8  
    CefSelectClientCertificateCallback     library   1/1  
    CefServer                              library  13/14 
    CefServerHandler                       client    8/8  
    CefSetCookieCallback                   client    1/1  
    CefSettingObserver                     client    1/1  
    CefSharedMemoryRegion                  library   2/3  
    CefSharedProcessMessageBuilder         library   4/5  
  * CefStreamReader                        library   8/8  
  * CefStreamWriter                        library   7/7  
    CefStringVisitor                       client    1/1  
    CefTask                                client    1/1  
  * CefTaskManager                         library   5/6  
    CefTaskRunner                          library   5/7  
    CefTestServer                          library   3/3  
    CefTestServerConnection                library   4/5  
    CefTestServerHandler                   client    1/1  
    CefTextfield                           library  32/32 
    CefTextfieldDelegate                   client    2/2  
    CefThread                              library   4/5  
    CefTranslatorTest                      library  37/61 
    CefTranslatorTestRefPtrClient          client    1/1  
    CefTranslatorTestRefPtrClientChild     client    1/1  
    CefTranslatorTestRefPtrLibrary         library   3/3  
    CefTranslatorTestRefPtrLibraryChild    library   3/3  
    CefTranslatorTestRefPtrLibraryChildChild library   3/3  
    CefTranslatorTestScopedClient          client    1/1  
    CefTranslatorTestScopedClientChild     client    1/1  
    CefTranslatorTestScopedLibrary         library   2/3  
    CefTranslatorTestScopedLibraryChild    library   2/3  
    CefTranslatorTestScopedLibraryChildChild library   2/3  
    CefURLRequest                          library   7/8  
    CefURLRequestClient                    client    5/5  
  * CefUnresponsiveProcessCallback         library   2/2  
    CefV8Accessor                          client    1/2  
    CefV8ArrayBufferReleaseCallback        client    0/1  
    CefV8BackingStore                      library   3/4  
    CefV8Context                           library  11/12 
    CefV8Exception                         library   8/8  
    CefV8Handler                           client    0/1  
    CefV8Interceptor                       client    2/4  
    CefV8StackFrame                        library   8/8  
    CefV8StackTrace                        library   4/4  
    CefV8Value                             library  59/67 
  * CefValue                               library  23/23 
    CefView                                library  51/52 
    CefViewDelegate                        client   11/11 
    CefWaitableEvent                       library   6/6  
    CefWindow                              library  42/43 
    CefWindowDelegate                      client   21/23 
  * CefWriteHandler                        client    5/5  
    CefX509CertPrincipal                   library   7/7  
    CefX509Certificate                     library  10/10 
    CefXmlReader                           library  30/30 
  * CefZipReader                           library  13/13 
  (* = generated now)

Opened by java-cef, not generated yet (the gaps):
  CefBrowserHost                   5/30   type not supported yet
  CefCommandLine                  12/12   class not generated yet
  CefCookieAccessFilter            2/2    class not generated yet
  CefCookieManager                 6/6    class not generated yet
  CefDevToolsMessageObserver       2/2    class not generated yet
  CefDisplayHandler                1/7    type not supported yet
  CefDragData                     24/24   class not generated yet
  CefDragHandler                   1/1    type not supported yet
  CefFrame                         2/19   type not supported yet
  CefLifeSpanHandler               1/4    type not supported yet
  CefRenderHandler                 1/9    type not supported yet
  CefRequest                       3/23   type not supported yet
  CefRequestContext                3/3    class not generated yet
  CefRequestContextHandler         1/1    class not generated yet
  CefResourceRequestHandler        1/7    type not supported yet
  CefResponse                      2/14   type not supported yet
  CefSchemeRegistrar               1/1    class not generated yet
  CefURLRequest                    5/5    class not generated yet
  CefURLRequestClient              5/5    class not generated yet
  ----  78 methods

Generated, and not opened by java-cef (beyond the floor):
  CefBinaryValue                   8  the whole class
  CefBrowser                       2  2 methods
  CefBrowserHost                  33  33 methods
  CefClient                        1  1 methods
  CefContextMenuHandler            4  4 methods
  CefContextMenuParams             2  2 methods
  CefDictionaryValue              30  the whole class
  CefDisplay                      16  the whole class
  CefDisplayHandler                6  6 methods
  CefDownloadHandler               1  1 methods
  CefDownloadItem                  4  4 methods
  CefDragHandler                   1  1 methods
  CefFrame                         4  4 methods
  CefLifeSpanHandler               1  1 methods
  CefListValue                    29  the whole class
  CefMenuModel                     8  8 methods
  CefMenuModelDelegate             7  the whole class
  CefPostData                      1  1 methods
  CefProcessMessage                6  the whole class
  CefReadHandler                   5  the whole class
  CefRenderHandler                 6  6 methods
  CefRequestHandler                4  4 methods
  CefResponse                      4  4 methods
  CefRunContextMenuCallback        2  the whole class
  CefRunQuickMenuCallback          2  the whole class
  CefSSLInfo                       1  the whole class
  CefStreamReader                  8  the whole class
  CefStreamWriter                  7  the whole class
  CefTaskManager                   5  the whole class
  CefUnresponsiveProcessCallback   2  the whole class
  CefValue                        23  the whole class
  CefZipReader                    13  the whole class
  ----  246 methods
```

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
