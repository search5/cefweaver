---
title: 열지 않은 CEF 메서드와 cefpython의 비교
type: analysis
sources:
  - tools/gen/scope.py
  - tools/gen/report.py
  - cefweaver/_cefweaver.pyi
  - llm-wiki/pages/reference/coverage-report.md
updated: 2026-10-10
---

# 열지 않은 CEF 메서드와 cefpython의 비교

CEF 154 헤더의 메서드와 함수 2,255개 가운데 cefweaver가 연 것은 708개이고, **열지 않은 것은 약 1,530개**입니다(2026-10-10 `Image` 등 17개를 연 뒤. 본문의 묶음별 수는 연 것을 빼기 전 값)(`coverage-report.md`). 그것이 무엇인지 묶고, cefpython(`cefpython147` 브랜치, CEF 123 계열)이 그 가운데 무엇을 여는지 대조했습니다. 집계는 일회성 스크립트로 했으며 아래의 묶음별 수는 집계 방식(전역 함수, 손으로 쓴 `AppHandler` 보정)에 따라 **±10개 안팎의 오차**가 있습니다.

## cefpython의 열린 범위를 구한 방법 (한계 포함)

cefpython에는 CEF 클래스별 목록이 없어서 두 곳에서 뽑았습니다: (1) Cython이 선언한 CEF 클래스의 메서드(`src/extern/cef/*.pxd`의 `cppclass`), (2) cefpython이 C++로 구현한 핸들러가 재정의하는 메서드(`src/client_handler/*.h`, `src/subprocess/*.h`, `src/*.h`). 이름이 CEF 154에도 있는 `(클래스, 메서드)`만 셌습니다. **"선언했다"가 "파이썬에 열었다"와 같지는 않습니다**(선언만 하고 쓰지 않은 것이 있을 수 있음). 결과: cefpython 318개, 그 가운데 cefweaver도 여는 것 275개, cefpython만 여는 것 약 37~43개입니다.

## 열지 않은 것 (묶음별)

| 묶음 | 미개방 | 비고 |
| --- | --- | --- |
| ~~**Views 프레임워크**(22개 클래스, 789개 메서드)~~ **열었음**(2026-10-10 사용자 결정, [F96~F98](../reference/verified-findings-views.md)) | 306개 생성, 3개는 열지 못함(`View.GetDelegate`, `GetDelegateForPopupBrowserView`, `GetParentWindow`) | 외부 메시지 펌프에서는 CEF 창의 X11 입력이 오지 않아 **폴링**으로 돌려야 함 |
| **CEF 자체의 시험용 클래스** (`CefTranslatorTest*`, `CefApiVersionTest*`, `CefTestServer*`) | 326 | CEF의 API 번역기와 버전 시험용이라 열 대상이 아님 |
| **V8** (`CefV8Value`, `CefV8Context`, `CefV8Handler` 등 10개 클래스) | 약 111 | 렌더러 프로세스의 JavaScript 엔진 객체. 우리의 렌더러는 C++이라 Python에 줄 수 없음 |
| 인증서, SSL, 서버, 리소스 번들, 응답 필터, 환경설정 | 약 65 | `CefX509Certificate` 7개 클래스 등. 필터와 인증서 정보는 실제 필요가 있으면 열 수 있음 |
| XML, ZIP 디렉터리, 공유 메모리, 스레드, 작업 실행기, 대기 이벤트 | 약 56 | `CefXmlReader`는 타입은 지원하지만 범위에 안 넣음(26/30) |
| DOM (`CefDOMDocument`, `CefDOMNode`, `CefDOMVisitor`) | 약 41 | 렌더러 프로세스에서만 의미 있음 |
| 미디어 라우터(캐스트) | 약 27 | `CefMediaRouter`, 경로, 싱크 |
| 이미지 | 14 | `CefImage` |
| 그 밖의 클래스 | 약 128 | 아래 표 |
| (전역 함수) | 46 | 아래 |

### 그 밖의 클래스

| 클래스 | 열지 않은 것 |
| --- | --- |
| `CefNavigationEntry`(10), `CefNavigationEntryVisitor` | 탐색 항목. `BrowserHost.GetNavigationEntries`, `GetVisibleNavigationEntry`도 그 때문에 못 엶 |
| `CefRenderProcessHandler`(9) | 렌더러의 `OnContextCreated` 등. **Python이 렌더러에 없어서** 의도적으로 열지 않음 |
| `CefFrameHandler`(5), `CefFindHandler`(1), `CefCommandHandler`(5, Chrome 스타일용) | 핸들러. `Client.get_frame_handler`, `get_find_handler`, `get_command_handler`도 같이 없음 |
| `CefComponent`, `CefComponentUpdater`와 콜백(11) | 구성요소 업데이트 |
| `CefAccessibilityHandler`(2) | 접근성 트리 알림 |
| `CefResolveCallback`, `CefSettingObserver`, `CefSelectClientCertificateCallback`, `CefDownloadImageCallback`, `CefEndTracingCallback` | 콜백 객체. 해당 메서드(`RequestContext.ResolveHost`, `AddSettingObserver`, `RequestHandler.OnSelectClientCertificate`, `BrowserHost.DownloadImage`, `BeginTracing`)도 같이 없음 |
| 부분 개방 클래스의 남은 메서드 | `BrowserHost`(`DownloadImage`, `GetNavigationEntries`, `GetVisibleNavigationEntry`, `ShowDevTools`, `GetClient`, `CreateBrowser`/`Sync`), `Frame`(`GetV8Context`, `VisitDOM`), `RequestContext`(`AddPreferenceObserver`, `GetHandler`, `ResolveHost`, `GetMediaRouter`, `AddSettingObserver`), `BrowserProcessHandler`(`OnRegisterCustomPreferences`, `GetDefaultClient` 등), `BinaryValue.GetRawData`(CEF 소유 메모리), `CommandLine.InitFromArgv`, `ProcessMessage.GetSharedMemoryRegion`, `ResourceRequestHandler.GetResourceResponseFilter` |

### 전역 함수 (cefweaver가 연 것: `RegisterSchemeHandlerFactory`, `ClearSchemeHandlerFactories`, `CurrentlyOn`, `PostTask`, `PostDelayedTask`, `GetMimeType`)

- **CefApp이 대신하는 것**: `CefInitialize`, `CefShutdown`, `CefDoMessageLoopWork`, `CefExecuteProcess`는 `CefApp.initialize()`와 `shutdown()`, `do_message_loop_work()`가 대신합니다.
- **열지 않은 것**: 파일과 경로(`CefCreateDirectory`, `CefDeleteFile`, `CefDirectoryExists`, `CefGetPath`, `CefGetTempDirectory`, `CefZipDirectory` 등), 인코딩(`CefBase64Encode/Decode`, `CefURIEncode/Decode`), URL(`CefParseURL`, `CefCreateURL`, `CefResolveURL`, `CefFormatUrlForSecurityDisplay`), JSON(`CefParseJSON`, `CefWriteJSON`), 교차 출처 허용 목록(`CefAddCrossOriginWhitelistEntry` 등), 추적(`CefBeginTracing`, `CefEndTracing`), 크래시 키(`CefSetCrashKeyValue`), 프로세스 실행(`CefLaunchProcess`), 확장 등록(`CefRegisterExtension`), 메시지 루프(`CefRunMessageLoop`, `CefQuitMessageLoop`: 외부 펌프만 씀) 등. 파이썬 표준 라이브러리로 대신할 수 있는 것이 많습니다.

## cefpython에서는 무엇을 여는가

위 가운데 cefpython이 여는 것은 **약 40개**뿐이고 대부분은 의도적으로 열지 않은 것입니다.

| cefpython이 여는 것 | 개수 | cefweaver의 상태 |
| --- | --- | --- |
| **`CefRenderProcessHandler`**(`OnContextCreated`, `OnContextReleased`, `OnBrowserCreated` 등)와 `CefV8Handler.Execute` | 9 | 렌더러에 Python이 없어서 열지 않음. 대신 메시지 라우터 위의 `JavascriptBridge`가 JSON으로 함수를 노출함([JavascriptBridge](../reference/javascript-bridge.md)) |
| **Views의 `CefWindow`(14), `CefPanel`, `CefBoxLayout`** | 16 | cefpython도 `window_title`을 줄 때 **최상위 창을 만드는 한 곳**(`cefpython.pyx`)에서만 씀. 우리는 열지 않음 |
| `CefAccessibilityHandler`와 `RenderHandler.GetAccessibilityHandler` | 3 | 열지 않음 |
| `CefImage`(`GetAsBitmap`, `GetAsPNG`, `GetWidth`, `GetHeight`)와 `DragData.GetImage` | 5 | 열지 않음 |
| `BrowserHost.ShowDevTools` | 1 | 창 정보 구조체가 필요해 열지 않음(`devtools_menu`와 원격 디버깅 포트로 대신) |
| `CefApp.GetResourceBundleHandler`, `BrowserProcessHandler.OnBeforeChildProcessLaunch` | 2 | 안 엶(전자는 리소스 번들, 후자는 내부에서 브리지 이름을 넘기는 데만 씀) |
| `URLRequest.GetClient` | 1 | 열지 않음 |
| 전역 함수 `CefFormatUrlForSecurityDisplay`, `CefGetExtensionsForMimeType`, `CefGetPath`, `CefLoadCRLSetsFile`, `CefRunMessageLoop`, `CefQuitMessageLoop` | 6 | 열지 않음(메시지 루프는 설계상 외부 펌프만) |

반대로 **cefpython이 열지 않았는데 cefweaver가 연 것**은 약 430개입니다(`AudioHandler`, `PermissionHandler`, 값 컨테이너 일부, 스트림, ZIP 읽기, `Display`, `TaskManager`, 메뉴 모델 전체, `BrowserHost`의 IME와 줌과 인쇄 등).

## 열 수 있는 것 (우회 포함, 우리 구조상 불가능한 것은 뺌)

기준: 생성기의 타입 판정(`plan_class`)이 막지 않거나, 손으로 쓴 래퍼(`SchemeRegistrar`처럼)나 복사로 우회할 수 있는 것입니다. **"열 수 있다"는 타입 판정과 설계에서 본 것이고, 실제 컴파일과 동작은 열어 봐야 압니다.** 효과가 큰 순서로 적었습니다.

### A. `scope.py`에 더하면 되는 것 (타입 판정이 막지 않음, 약 130개)

| 대상 | 개수 | 쓸모 |
| --- | --- | --- |
| **`FindHandler`**(`OnFindResult`)와 `Client.get_find_handler` | 1+1 | **실제 격차**: `host.find()`는 열려 있는데 결과(개수, 현재 위치)를 받을 곳이 없음 |
| **`NavigationEntry`**(10)와 `NavigationEntryVisitor`, `BrowserHost.GetNavigationEntries`, `GetVisibleNavigationEntry` | 약 13 | 탐색 이력 목록(뒤로와 앞으로 메뉴), 제목과 URL, 전환 종류, HTTP 상태, SSL 상태 |
| **`FrameHandler`**(`OnFrameCreated`, `OnFrameDestroyed`, `OnFrameAttached`, `OnFrameDetached`, `OnMainFrameChanged`)와 `Client.get_frame_handler` | 6 | iframe의 생성과 제거 추적 |
| ~~**`Image`**(14), `DragData.GetImage`, `BrowserHost.DownloadImage`와 `DownloadImageCallback`~~ **열었음**(2026-10-10, [F95](../reference/verified-findings-handlers.md)) | 17 | 파비콘 가져오기, 드래그 이미지, 비트맵과 PNG로 변환. cefpython이 여는 것 |
| **인증서 정보**: `X509Certificate`(10), `X509CertPrincipal`(7), `SSLStatus`(5), `SSLInfo.GetX509Certificate`, `RequestHandler.OnSelectClientCertificate`와 `SelectClientCertificateCallback` | 약 24 | 인증서의 발급자와 만료일 표시, 클라이언트 인증서 선택 |
| **`Server`**(14)와 `ServerHandler`(8) | 22 | CEF가 브라우저 프로세스에 HTTP와 WebSocket 서버를 띄움(Python에서 핸들러 구현). 콜백은 서버 스레드에서 오지만 생성되는 콜백은 `with gil`로 처리됨 |
| **`ResponseFilter`**(`InitFilter`, `Filter`)와 `ResourceRequestHandler.GetResourceResponseFilter` | 3 | 응답 본문을 걸러서 바꿈. 입출력 버퍼가 `memoryview`(쓰기 가능)와 읽은 양과 쓴 양의 반환값으로 나오는 기존 규칙을 따름 |
| `AccessibilityHandler`(2)와 `RenderHandler.GetAccessibilityHandler` | 3 | 접근성 트리 알림. cefpython이 여는 것 |
| `RequestContext`의 `ResolveHost`와 `ResolveCallback`, `AddSettingObserver`와 `SettingObserver`, `AddPreferenceObserver`와 `PreferenceObserver` | 약 5 | DNS 조회, 설정과 환경설정 변경 관찰 |
| 전역 함수 약 35개 중 쓸 만한 것 | 약 20 | 교차 출처 허용 목록(`CefAddCrossOriginWhitelistEntry`, `CefRemoveCrossOriginWhitelistEntry`, `CefClearCrossOriginWhitelist`: 사용자 스킴과 함께 필요), 인증서 상태(`CefIsCertStatusError`), `CefFormatUrlForSecurityDisplay`, `CefGetExtensionsForMimeType`, `CefLoadCRLSetsFile`, 추적(`CefBeginTracing`, `CefEndTracing`, `EndTracingCallback`), 크래시 키(`CefSetCrashKeyValue`), `CefCrashReportingEnabled`, `CefIsRTL`, `CefGetPath` |

### B. 손을 더 써서 열 수 있는 것 (약 25개)

| 대상 | 막힌 이유 | 우회 |
| --- | --- | --- |
| **`BrowserHost.ShowDevTools`** | 창 정보, 클라이언트, 설정, 좌표(포인터가 든 구조체) | 래퍼가 `create_browser`처럼 창 정보를 직접 구성하는 `show_dev_tools(x, y)`를 손으로 씀. 지금은 `devtools_menu`와 원격 디버깅 포트로 대신 |
| `BrowserProcessHandler.OnRegisterCustomPreferences` | `CefRawPtr<CefPreferenceRegistrar>` | `SchemeRegistrar`와 같은 방식으로 손으로 쓴 `PreferenceRegistrar` |
| `BrowserProcessHandler.OnBeforeChildProcessLaunch`, `GetDefaultClient`, `GetDefaultRequestContextHandler` | 래퍼가 내부에서 이미 씀(브리지 이름 전달) | 사용자 훅을 뒤에 호출하도록 손으로 연결 |
| `BrowserHost.GetClient`, `RequestContext.GetHandler` | 라이브러리 메서드가 클라이언트 객체를 돌려줌 | 래퍼가 보관한 Python 객체를 돌려줌 |
| `ProcessMessage.GetSharedMemoryRegion`, `SharedMemoryRegion`, `SharedProcessMessageBuilder` | CEF가 소유한 메모리를 가리키는 포인터 | `BinaryValue.get_data()`처럼 **복사**하는 메서드(`bytes`)로 열음. 큰 데이터의 프로세스 간 전달에 쓸 수 있음 |
| `ResourceBundleHandler`(3)와 `CefApp.GetResourceBundleHandler` | CEF가 핸들러가 준 포인터를 계속 쥠 | 래퍼가 바이트를 C++ 쪽에 보관하고 그 포인터를 줌. 현지화 문자열과 리소스를 바꾸는 용도 |
| `LifeSpanHandler.OnBeforeDevToolsPopup` | 창 정보, 클라이언트, 설정 포인터 | URL과 이름만 넘기는 축소 형태(`OnBeforePopup`과 같은 규칙) |
| `XmlReader`의 오버로드 4개 | 같은 이름의 오버로드 | 한 이름으로 합치거나 이름을 구분해 열음. 파이썬 표준 XML이 있어 실익이 낮음 |

### C. 구조를 바꾸는 우회

| 대상 | 방법 | 한계 |
| --- | --- | --- |
| **렌더러 이벤트 중계**: `RenderProcessHandler`의 `OnUncaughtException`(JS 오류), `OnFocusedNodeChanged`, `OnContextCreated`와 `OnContextReleased`, `OnBrowserCreated`와 `OnBrowserDestroyed`, `OnProcessMessageReceived` | 렌더러의 **C++ 핸들러**가 값을 읽어 프로세스 메시지로 브라우저에 보내고 Python은 그 메시지를 받음(이미 `Client.on_process_message_received`가 있음) | **알림과 값 복사만** 가능. 렌더러에서 Python 코드를 실행하지는 못함 |
| `Frame.VisitDOM`, DOM 객체 | 열지 않고 **`evaluate`로 JS를 실행**해 값을 JSON으로 받음(이미 열려 있음) | 노드 객체를 직접 쥘 수는 없음 |
| V8 값과 함수 | **`JavascriptBridge`**가 JSON으로 대신함(이미 열려 있음) | 객체 참조와 속성 바인딩은 안 됨 |
| **Views 프레임워크**(`CefWindow`, `CefBrowserView`, 버튼, 메뉴 등 약 773개, 타입 판정은 762개 통과) | scope에 더하고 델리게이트를 Python 핸들러로 | **규모가 가장 크고 이 컴퓨터에서 동작을 확인하지 못함**(외부 메시지 펌프와 Alloy 스타일에서 Views 창이 도는지). 열면 툴킷 없이 CEF가 창, 메뉴, 단추를 만들어 Windows 지원의 길이 될 수 있지만 cefpython도 창 하나만 만드는 데 씀 |

### Views를 전부 여는 이유와 측정 (2026-10-10)

- **결정의 근거(사용자)**: Views는 CEF가 창, 단추, 텍스트 필드, 메뉴, 레이아웃을 직접 만들어 주는 **독립적인 UI 구성**입니다. java-cef는 AWT와 Swing 위에 얹혀서 쓰는 구조라서 열지 않았다고 판단합니다. java-cef의 네이티브(`native/`)와 Java 소스 어디에도 Views 클래스(`CefWindow`, `CefBrowserView`, `CefPanel` 등)의 참조가 **없음**은 확인했습니다(`grep`). 이유가 AWT와 Swing 때문이라는 것은 문서로 확인한 것이 아니라 추정입니다(윈도우드는 AWT 컴포넌트의 네이티브 창 핸들을 CEF에 주고 오프스크린은 JOGL로 그리므로, Views가 만드는 창과 겹침).
- **범위**: `include/views/`의 22개 클래스(라이브러리 15개: `View`, `Panel`, `Window`, `BrowserView`, `Button`, `LabelButton`, `MenuButton`, `MenuButtonPressedLock`, `Textfield`, `ScrollView`, `Layout`, `BoxLayout`, `FillLayout`, `OverlayController`, `Display`(이미 열려 있음), 델리게이트 7개: `ViewDelegate`, `PanelDelegate`, `WindowDelegate`, `BrowserViewDelegate`, `ButtonDelegate`, `MenuButtonDelegate`, `TextfieldDelegate`). 789개 메서드입니다.
- **측정**(`scope.py`를 메모리에서만 확장해 `generate.build_all`을 실행, 저장소는 바꾸지 않음): 오류 없이 생성되고 0.3초가 걸립니다. 생성 텍스트는 합계 약 1.02MB에서 1.69MB로 **약 65% 늘어납니다**(프록시 +74KB, Cython 선언 +44KB, `.pxi` 약 +265KB, 타입 스텁 +196KB). 컴파일 시간과 wheel 크기는 측정하지 않았습니다.
- **타입 판정(구현 전 측정, 펼친 789개 기준)**: **770개가 막힘 없음**이었고 막힌 19개는 다음과 같았습니다(상속을 구현하고 `Image`를 열어 **3개로 줄었음**, F96): `CefImage`가 범위에 없어서 8개(`SetImage`, `GetImage`, `SetWindowIcon`, `GetWindowIcon`, `SetWindowAppIcon`, `GetWindowAppIcon`; **`Image`를 열어서 풀림**), 라이브러리 메서드가 클라이언트 객체를 돌려주는 `GetDelegate` 9개(**B 묶음의 "보관한 Python 객체를 돌려줌" 방식으로 우회**), `BrowserViewDelegate.GetDelegateForPopupBrowserView`(클라이언트 객체를 출력 인자로 넘김: 손으로 써야 함), `WindowDelegate.GetParentWindow`(클라이언트 메서드가 라이브러리 객체를 돌려줌: 새 타입 종류가 필요함).
- **남은 불확실성**: (1) ~~외부 메시지 펌프로 Views 창이 도는지~~ 그려지고 레이아웃도 되지만 입력이 안 옴, 폴링이면 됨(F97), (2) macOS에서 우리가 준비한 `NSApp`과 Views의 `NSWindow`의 관계, (3) Linux에서 X11(`ozone-platform=x11`)로만 확인할 수 있고 Wayland는 별개, (4) 델리게이트의 많은 콜백을 GIL과 함께 안전하게 부르는지.
- **열 순서와 결과**: `Image`(완료) → Views 22개(**완료**: 상속은 Python 상속으로 구현, 막힌 3개는 아직) → 툴킷 없는 예제 `examples/views/`(창, 단추와 주소 입력칸, `BrowserView`)로 확인(**완료**, `smoke.py` 13개 연속 3회 통과). 확인 중 **외부 메시지 펌프로는 CEF 자신의 창에 입력이 오지 않는** 것을 찾았습니다(F97).

### 열 수 있지만 실익이 낮거나 동작이 불확실한 것

- **Chrome 스타일 전용**: `CommandHandler`(5, `OnChromeCommand` 등), `ComponentUpdater`와 `Component`(10). 우리는 Alloy 스타일을 써서 불리지 않을 가능성이 큼(미확인).
- **미디어 라우터(캐스트)**(`MediaRouter`, `MediaRoute`, `MediaSink`, `MediaSource`, `MediaObserver`, 콜백 약 27개): 타입은 막힘 없음, 실제 장치와 동작은 미확인.
- **파이썬이 이미 대신하는 것**: `TaskRunner`(7), `WaitableEvent`(6), `Thread`(5)는 `threading`, 파일과 경로 함수는 `os`와 `pathlib`, `CefBase64*`와 `CefURI*`는 `base64`와 `urllib`, `CefParseJSON`과 `CefWriteJSON`은 `json`, `CefParseURL`, `CefCreateURL`, `CefResolveURL`은 `urllib.parse`, `CefZipDirectory`는 `zipfile`, `XmlReader`는 `xml`.

### 열지 않는 것 (구조상 불가능이거나 의도적)

- **렌더러 프로세스에서 Python 코드가 돌아야 하는 것**: `V8Handler.Execute`, `V8Value`와 `V8Context`를 직접 조작하는 코드, `RenderProcessHandler.OnContextCreated`에서 Python을 실행하는 것, `CefRegisterExtension`(JS 확장). 우리 렌더러는 C++이라 불가능하고, 바꾸려면 cefpython처럼 렌더러에 Python을 임베드해야 함(아키텍처의 변경).
- 시험용 클래스(326개), `CefRunMessageLoop`와 `CefQuitMessageLoop`(외부 펌프만 씀), `CefInitialize`와 `CefExecuteProcess`(`CefApp`이 대신하고 `CefMainArgs`는 타입이 막음), `CommandLine.InitFromArgv`(`char**`).

## 해석

- 열지 않은 약 1,547개의 **대부분(약 1,100개)은 Views, 시험용, V8, DOM**입니다. 그 가운데 열 수 있는 것은 위 "열 수 있는 것"에 정리했고, **가장 값이 큰 후보는 `FindHandler`(`find()`의 결과를 받을 곳이 없음), `NavigationEntry`, `FrameHandler`, `Image`, 인증서 정보, `Server`, 응답 필터**입니다.
- **cefpython만 여는 것 가운데 실제 격차는 `CefImage`와 접근성 핸들러** 정도이고, 나머지는 렌더러의 Python(의도적으로 안 함)과 Views의 창 만들기(cefpython도 한 곳에서만)입니다.
- 새 클래스를 열려면 `tools/gen/scope.py`에 더하면 됩니다([새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)).

## 관련 페이지

- [cefpython과 cefweaver의 API 차이](cefpython-comparison.md)
- [java-cef를 바닥으로 보았을 때 어디까지 왔는가](beyond-java-cef.md)
- [생성 범위와 커버리지](../reference/generated-api-coverage.md)
- [커버리지 보고서 (생성됨)](../reference/coverage-report.md)
