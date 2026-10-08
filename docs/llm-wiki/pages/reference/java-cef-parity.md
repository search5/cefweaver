---
title: java-cef 동등성 (바닥과 그 위)
type: reference
sources:
  - tools/gen/surface.py
  - tools/gen/derive_surface.py
  - tools/gen/report.py
  - tests/test_generator.py
updated: 2026-10-08
---

# java-cef 동등성 (바닥과 그 위)

## 방침

**java-cef가 여는 것은 cefweaver의 바닥**입니다. java-cef가 여는 것은 java-cef의 동작에 맞춰 모두 구현하고, 그보다 더 연 것은 닫지 않고 이 페이지에 정리해 둡니다(사용자 결정). java-cef가 열지 않은 이유는 대개 그쪽 사정(JNI로 일일이 감싸는 비용)이라서 우리가 따라 닫지 않습니다. 안전 때문에 닫은 것(예: CEF가 소유한 메모리를 가리키는 포인터)은 그대로 둡니다.

## 목록의 출처

`tools/gen/surface.py`는 java-cef의 네이티브 코드에서 뽑은 "CEF 클래스 → java-cef가 여는 메서드"입니다(`python tools/gen/derive_surface.py /경로/java-cef`로 다시 만듭니다). 라이브러리 클래스는 `native/Cef<클래스>_N.cpp`의 JNI 함수, 핸들러는 `native/*_handler.cpp`가 재정의하는 CEF 메서드입니다. `CefBrowser`, `CefBrowserHost`, `CefFrame`은 java-cef에서 객체 둘(`CefBrowser_N`, `CefFrame_N`)이라 합쳐서 봅니다. 목록은 생성기가 만드는 파일이 아니라 커밋된 입력이고, 커버리지 보고서(`coverage-report.md`)의 마지막 두 절이 "바닥의 격차"와 "바닥 위"를 계산합니다.

## 바닥의 격차 (java-cef는 열고 우리는 아직 안 연 것)

**지금은 없습니다**(389개 가운데 0개). 시험 `test_the_gaps_to_the_java_cef_floor_are_the_listed_ones`가 목록이 비어 있음을 고정합니다. java-cef가 CEF 클래스의 메서드로 여는 것은 모두 생성되었거나 직접 써서(`SchemeRegistrar`) 열려 있습니다. java-cef의 Java 쪽 사정이라 해당이 없는 것은 아래에 적었습니다.

해당이 없어 열지 않은 것:

- `onScheduleMessagePumpWork`, `onBeforeTerminate`, `stateHasChanged`(앱 핸들러): 우리는 호출하는 쪽이 `do_message_loop_work()`를 부르는 구조입니다([앱 핸들러](app-handler.md)).
- Java 객체의 관리(`Dispose`)와 AWT 창(`SetParent`, `SetWindowVisibility`, `UpdateUI`, `WindowHandler`, `CreateBrowser`, `CreateDevTools`).
- java-cef의 `CefMessageRouter`/`CefQueryCallback`에 해당하는 것은 `add_query_handler`, `remove_query_handler`, `cancel_pending_queries`, `QueryCallback`입니다.

### 메운 격차

- 드래그(`CefDragData` 24개, `DragHandler.OnDragEnter`, `RenderHandler.StartDragging`, `BrowserHost.DragTargetDragEnter`)와 라우터의 `CancelPending`([검증](verified-findings-more.md) F54).
- 명령줄(`CefCommandLine` 12개)과 앱 훅(`AppHandler`: 명령줄 처리, 사용자 스킴 등록과 렌더러 전파, 컨텍스트 초기화, 두 번째 시작), `SchemeRegistrar`(직접 쓴 클래스)([검증](verified-findings-more.md) F53, [앱 핸들러](app-handler.md)). 하지 않은 것: java-cef의 `onScheduleMessagePumpWork`, `onBeforeTerminate`, `stateHasChanged`(우리 구조에는 해당 없음).
- 요청 컨텍스트(`CefRequestContext`, 부모 `CefPreferenceManager`의 환경설정 메서드 포함, `CefRequestContextHandler`)와 URL 요청(`CefURLRequest`, `CefURLRequestClient`)([검증](verified-findings-more.md) F52).
- 쿠키(`CookieManager` 6개, `CookieVisitor`, 완료 콜백들, `CookieAccessFilter` 2개, `ResourceRequestHandler.GetCookieAccessFilter`)([검증](verified-findings-more.md) F51).
- PDF 인쇄(`BrowserHost.PrintToPDF`, `PdfPrintCallback`): 문자열이 든 구조체(`PdfPrintSettings`)를 열어서. 같은 능력으로 `Cookie`, `RequestContextSettings` 등 22개 구조체가 공개됨([검증](verified-findings-more.md) F50).
- 문자열 방문자(`Frame.GetSource`/`GetText`), 파일 대화상자 콜백(`BrowserHost.RunFileDialog`), DevTools 메시지 관찰자(`AddDevToolsMessageObserver`, `Registration`)([검증](verified-findings-more.md) F49).
- 창 핸들(`BrowserHost.GetWindowHandle`): Linux의 X11 창 번호를 정수로([검증](verified-findings-more.md) F48).
- 헤더 맵(`Request.GetHeaderMap`/`SetHeaderMap`/`Set`, `Response.GetHeaderMap`/`SetHeaderMap`): 문자열 멀티맵 ↔ `dict`([검증](verified-findings-more.md) F47).
- 팝업(`OnBeforePopup`), 커서 변경(`OnCursorChange`), 인증서 오류의 `ssl_info`: java-cef가 넘기지 않는 인자를 무시하는 규칙으로([검증](verified-findings-more.md) F46).

## 바닥 위 (우리가 더 연 것, java-cef에는 없음)

닫지 않고 둡니다(사용자 결정). 총 289개 메서드이고 클래스별 목록은 `coverage-report.md`의 "beyond the floor" 절에 있습니다. 묶음별 구성은 다음과 같습니다.

| 묶음 | 항목 | 메서드 |
| --- | --- | --- |
| 값 컨테이너와 프로세스 메시지 | `Value`, `ListValue`, `DictionaryValue`, `BinaryValue`, `ProcessMessage` | 96 |
| 스트림 | `StreamReader`, `StreamWriter`, `ZipReader`, `ReadHandler` (java-cef는 드래그 파일 내용용 `WriteHandler`만 안에서 씀) | 33 |
| 화면과 작업 | `Display`, `TaskManager` | 22 |
| 메뉴 | `MenuModelDelegate`, `RunContextMenuCallback`, `RunQuickMenuCallback`, `ContextMenuHandler`의 4개, `MenuModel`의 8개, `ContextMenuParams`의 2개 | 25 |
| 핸들러의 추가 메서드 | `DisplayHandler` 6, `RenderHandler` 6(스크롤, IME, 텍스트 선택, 터치, 가상 키보드), `RequestHandler` 4, `DevToolsMessageObserver` 3, `LifeSpanHandler`, `DownloadHandler`, `DragHandler`, `Client`(프로세스 메시지), `RequestContextHandler` 각 1 | 24 |
| 라이브러리 클래스의 추가 메서드 | `BrowserHost` 35(IME, 터치, 줌, 탐색 항목 등), `RequestContext` 18(웹사이트 설정, 색상 등), `CommandLine` 10, `Frame` 5, `DownloadItem` 4, `Response` 4, `DragData` 3, `Browser` 2, `URLRequest` 2, `PostData` 1 | 84 |
| 쿠키 콜백 | `SetCookieCallback`, `DeleteCookiesCallback`(java-cef는 완료 콜백만) | 2 |
| 그 밖 | `SSLInfo`, `UnresponsiveProcessCallback` | 3 |

메서드 수에 잡히지 않는 것도 있습니다.

- **메시지 라우터의 바이트열**: 요청과 응답을 `bytes`로 주고받습니다(java-cef는 문자열만).
- **유형 모듈**: 모든 CEF 열거형과 구조체 22개(java-cef는 쓰는 것만 Java 클래스로 둠), 구조체 필드의 기본값.
- **시간, 헤더 맵**: `datetime`(마이크로초)과 `dict`(java-cef는 `Date` 밀리초, `Map`).
- **래퍼 고유**: `devtools_menu`, `add_javascript_binding`, `add_resource`는 java-cef에 없는 기능입니다(래퍼에서 온 것).
- **PostData의 추가, 요청 컨텍스트의 `create_context` 중복 오버로드**(첫 번째만).

## 열지 않고 정리만 하는 것 (java-cef 수준을 넘음)

- **응답 필터**(`CefResponseFilter`, `ResourceRequestHandler.get_resource_response_filter`): java-cef는 구현하지 않습니다.
- **창 정보로 팝업을 꾸미는 일**(`CefWindowInfo`, `CefBrowserSettings`가 든 `on_before_popup`, `on_before_dev_tools_popup`, `BrowserHost.show_dev_tools`): java-cef도 URL과 프레임 이름만 넘깁니다. 열려면 포인터가 든 구조체 종류가 필요합니다.
- **브라우저를 여럿 만들기와 브라우저별 요청 컨텍스트**: java-cef는 `createBrowser`에 컨텍스트를 주지만 래퍼는 브라우저를 하나만 만듭니다. 첫 브라우저에 주는 `set_request_context`만 있습니다.

## 아직 열지 않은 것 (java-cef도 열지 않았거나 해당 없음)

- `CommandLine.init_from_argv`(`char* const*`), `AudioHandler.on_audio_stream_packet`(`float**`): java-cef도 열지 않은 포인터 배열이라 같은 수준(안 엶)에 둡니다.
- `get_raw_data` 등 CEF가 소유한 메모리를 가리키는 `void*`: 안전을 위해 닫아 둡니다([바이트열과 시간](bytes-and-times.md)).

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [커버리지 보고서 (생성됨)](coverage-report.md)
- [설계 결정 기록](design-decisions.md)
