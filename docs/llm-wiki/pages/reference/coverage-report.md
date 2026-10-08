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
Generated now: 245 methods/functions in 17 classes, 3 global functions

Skipped inside the generated classes (type not supported yet):
    32  class
     6  struct-like value type
     5  struct
     4  multimap of values
     2  vector of values
     1  a library method returning a client object
     1  vector of values passed to a library method
     1  untyped pointer
  ----  52 skipped

If every class were generated, the type support alone would cover 1398 of 1598 methods/functions (87%).
What blocks the rest, by type:
    36  vector of values
    33  struct-like value type
    32  ownptr pointer
    24  untyped pointer
    18  struct
    11  a library method returning a client object
    11  rawptr pointer
     8  pointer to
     8  multimap of values
     4  map of values
     4  a client method returning the value type CefSize
     4  reference to a CefRefPtr
     3  vector of values passed to a library method
     2  class
     1  a client method returning a library object
     1  a client method returning the value type CefRect

Per class (supported/total methods, when every class is generated):
    CefAccessibilityHandler                client    2/2  
    CefApiVersionTest                      library  11/36 
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
    CefAudioHandler                        client    2/5  
    CefAuthCallback                        library   2/2  
    CefBeforeDownloadCallback              library   1/1  
    CefBinaryValue                         library   6/9  
    CefBoxLayout                           library   2/2  
  * CefBrowser                             library  21/21 
  * CefBrowserHost                         library  60/72 
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
    CefComponentUpdater                    library   4/5  
    CefContextMenuHandler                  client    7/7  
    CefContextMenuParams                   library  20/20 
    CefCookieAccessFilter                  client    0/2  
    CefCookieManager                       library   5/6  
    CefCookieVisitor                       client    0/1  
    CefDOMDocument                         library  14/14 
    CefDOMNode                             library  25/26 
    CefDOMVisitor                          client    1/1  
    CefDeleteCookiesCallback               client    1/1  
    CefDevToolsMessageObserver             client    5/5  
    CefDialogHandler                       client    1/1  
    CefDictionaryValue                     library  30/30 
  * CefDisplay                             library  15/16 
  * CefDisplayHandler                      client   12/13 
    CefDownloadHandler                     client    3/3  
    CefDownloadImageCallback               client    1/1  
    CefDownloadItem                        library  18/20 
    CefDownloadItemCallback                library   3/3  
    CefDragData                            library  28/28 
    CefDragHandler                         client    1/2  
    CefEndTracingCallback                  client    1/1  
    CefFileDialogCallback                  library   1/2  
    CefFindHandler                         client    1/1  
    CefFocusHandler                        client    3/3  
  * CefFrame                               library  26/26 
    CefFrameHandler                        client    5/5  
    CefImage                               library  11/14 
    CefJSDialogCallback                    library   1/1  
    CefJSDialogHandler                     client    4/4  
    CefKeyboardHandler                     client    0/2  
    CefLabelButton                         library  12/12 
    CefLayout                              library   3/3  
  * CefLifeSpanHandler                     client    4/6  
    CefListValue                           library  29/29 
  * CefLoadHandler                         client    4/4  
    CefMediaAccessCallback                 library   2/2  
    CefMediaObserver                       client    2/4  
    CefMediaRoute                          library   4/5  
    CefMediaRouteCreateCallback            client    1/1  
    CefMediaRouter                         library   6/6  
    CefMediaSink                           library   7/7  
    CefMediaSinkDeviceInfoCallback         client    0/1  
    CefMediaSource                         library   3/3  
    CefMenuButton                          library   3/3  
    CefMenuButtonDelegate                  client    1/1  
  * CefMenuModel                           library  57/57 
  * CefMenuModelDelegate                   client    7/7  
    CefNavigationEntry                     library   9/10 
    CefNavigationEntryVisitor              client    1/1  
    CefOverlayController                   library  19/19 
    CefPanel                               library  12/13 
    CefPdfPrintCallback                    client    1/1  
    CefPermissionHandler                   client    3/3  
    CefPermissionPromptCallback            library   1/1  
    CefPostData                            library   7/8  
    CefPostDataElement                     library   7/9  
    CefPreferenceManager                   library   9/9  
    CefPreferenceObserver                  client    1/1  
    CefPreferenceRegistrar                 library   1/1  
    CefPrintDialogCallback                 library   2/2  
    CefPrintHandler                        client    5/6  
    CefPrintJobCallback                    library   1/1  
    CefPrintSettings                       library  21/23 
    CefProcessMessage                      library   7/7  
    CefReadHandler                         client    5/5  
    CefRenderHandler                       client   12/17 
    CefRenderProcessHandler                client    9/9  
  * CefRequest                             library  20/23 
    CefRequestContext                      library  24/26 
    CefRequestContextHandler               client    2/2  
    CefRequestHandler                      client   10/11 
    CefResolveCallback                     client    1/1  
    CefResourceBundle                      library   4/4  
    CefResourceBundleHandler               client    1/3  
  * CefResourceHandler                     client    7/7  
  * CefResourceReadCallback                library   1/1  
    CefResourceRequestHandler              client    8/8  
  * CefResourceSkipCallback                library   1/1  
  * CefResponse                            library  16/18 
    CefResponseFilter                      client    2/2  
    CefRunContextMenuCallback              library   2/2  
    CefRunFileDialogCallback               client    1/1  
    CefRunQuickMenuCallback                library   2/2  
    CefSSLInfo                             library   2/2  
    CefSSLStatus                           library   5/5  
  * CefSchemeHandlerFactory                client    1/1  
    CefSchemeRegistrar                     library   1/1  
    CefScrollView                          library   8/8  
    CefSelectClientCertificateCallback     library   1/1  
    CefServer                              library  10/14 
    CefServerHandler                       client    8/8  
    CefSetCookieCallback                   client    1/1  
    CefSettingObserver                     client    1/1  
    CefSharedMemoryRegion                  library   2/3  
    CefSharedProcessMessageBuilder         library   4/5  
    CefStreamReader                        library   6/8  
    CefStreamWriter                        library   6/7  
    CefStringVisitor                       client    1/1  
    CefTask                                client    1/1  
    CefTaskManager                         library   4/6  
    CefTaskRunner                          library   5/7  
    CefTestServer                          library   3/3  
    CefTestServerConnection                library   2/5  
    CefTestServerHandler                   client    1/1  
    CefTextfield                           library  32/32 
    CefTextfieldDelegate                   client    1/2  
    CefThread                              library   4/5  
    CefTranslatorTest                      library  31/61 
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
    CefUnresponsiveProcessCallback         library   2/2  
    CefV8Accessor                          client    1/2  
    CefV8ArrayBufferReleaseCallback        client    0/1  
    CefV8BackingStore                      library   3/4  
    CefV8Context                           library  11/12 
    CefV8Exception                         library   8/8  
    CefV8Handler                           client    0/1  
    CefV8Interceptor                       client    2/4  
    CefV8StackFrame                        library   8/8  
    CefV8StackTrace                        library   4/4  
    CefV8Value                             library  56/67 
    CefValue                               library  23/23 
    CefView                                library  51/52 
    CefViewDelegate                        client    8/11 
    CefWaitableEvent                       library   6/6  
    CefWindow                              library  41/43 
    CefWindowDelegate                      client   18/23 
    CefWriteHandler                        client    5/5  
    CefX509CertPrincipal                   library   7/7  
    CefX509Certificate                     library   6/10 
    CefXmlReader                           library  30/30 
    CefZipReader                           library  11/13 
  (* = generated now)
```

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
