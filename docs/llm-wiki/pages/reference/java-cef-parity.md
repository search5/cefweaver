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

- `onBeforeTerminate`, `stateHasChanged`(앱 핸들러): Java 쪽 사정입니다. `onScheduleMessagePumpWork`는 java-cef가 쓰지 않지만 GUI 툴킷에 넣을 때 필요해 열었습니다([앱 핸들러](app-handler.md), [F62](verified-findings-handlers.md)).
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

닫지 않고 둡니다(사용자 결정). 총 304개 메서드이고 클래스별 목록은 `coverage-report.md`의 "beyond the floor" 절에 있습니다. 묶음별 구성은 다음과 같습니다.

| 묶음 | 항목 | 메서드 |
| --- | --- | --- |
| 값 컨테이너와 프로세스 메시지 | `Value`, `ListValue`, `DictionaryValue`, `BinaryValue`, `ProcessMessage` | 96 |
| 스트림 | `StreamReader`, `StreamWriter`, `ZipReader`, `ReadHandler` (java-cef는 드래그 파일 내용용 `WriteHandler`만 안에서 씀) | 33 |
| 화면과 작업 | `Display`, `TaskManager` | 22 |
| 메뉴 | `MenuModelDelegate`, `RunContextMenuCallback`, `RunQuickMenuCallback`, `ContextMenuHandler`의 4개, `MenuModel`의 8개, `ContextMenuParams`의 2개 | 25 |
| 핸들러의 추가 메서드 | `DisplayHandler` 6, `RenderHandler` 6(스크롤, IME, 텍스트 선택, 터치, 가상 키보드), `RequestHandler` 4, `DevToolsMessageObserver` 3, `LifeSpanHandler`, `DownloadHandler`, `DragHandler`, `Client`(프로세스 메시지), `RequestContextHandler` 각 1 | 24 |
| 라이브러리 클래스의 추가 메서드 | `BrowserHost` 35(IME, 터치, 줌, 탐색 항목 등), `RequestContext` 18(웹사이트 설정, 색상 등), `CommandLine` 10, `Frame` 5, `DownloadItem` 4, `Response` 4, `DragData` 3, `Browser` 2, `URLRequest` 2, `PostData` 1 | 84 |
| 쿠키 콜백 | `SetCookieCallback`, `DeleteCookiesCallback`(java-cef는 완료 콜백만) | 2 |
| 오디오 | `AudioHandler` 5(스트림 시작, 패킷, 정지, 오류, 매개변수), `Client.get_audio_handler` 1 ([F72](verified-findings-media.md)) | 6 |
| 권한(마이크, 카메라) | `PermissionHandler` 3, `MediaAccessCallback` 2, `PermissionPromptCallback` 1, `Client.get_permission_handler` 1 ([F71](verified-findings-media.md)) | 7 |
| 그 밖 | `SSLInfo`, `UnresponsiveProcessCallback` | 3 |

메서드 수에 잡히지 않는 것도 있습니다.

- **메시지 라우터의 바이트열**: 요청과 응답을 `bytes`로 주고받습니다(java-cef는 문자열만).
- **유형 모듈**: 모든 CEF 열거형과 구조체 22개(java-cef는 쓰는 것만 Java 클래스로 둠), 구조체 필드의 기본값.
- **시간, 헤더 맵**: `datetime`(마이크로초)과 `dict`(java-cef는 `Date` 밀리초, `Map`).
- **래퍼 고유**: `devtools_menu`, `add_javascript_binding`, `add_resource`는 java-cef에 없는 기능입니다(래퍼에서 온 것).
- **PostData의 추가, 요청 컨텍스트의 `create_context` 중복 오버로드**(첫 번째만).
- **공유 텍스처**(`shared_texture`, `on_accelerated_paint`, `read_plane`): java-cef의 OSR은 CPU 버퍼만 씁니다([공유 텍스처](shared-textures.md)).
- **`JavascriptBridge`**(JSON으로 함수를 노출하고 `Promise`와 콜백, `evaluate`): cefpython의 `JavascriptBindings`에 해당하며 java-cef에는 없습니다([JavascriptBridge](javascript-bridge.md)).
- **메시지 펌프 예약과 스레드 작업**(`on_schedule_message_pump_work`, `MessagePump`, `Task`와 `post_task` 등 함수 3개): cefpython에는 있고 java-cef에는 없습니다. GUI 툴킷에 넣기 위해 열었습니다([F62](verified-findings-handlers.md), F63).

## JNI 목록 밖의 격차 (2026-10-08 점검)

도출 도구(`derive_surface.py`)는 java-cef의 네이티브 함수를 세므로 CEF 클래스의 메서드만 봅니다. Java 쪽 공개 API를 따로 대조해서 찾은, 아직 없는 것입니다(java-cef의 `CefApp`, `CefClient`, `CefSettings`, `CefBrowserSettings`).

| 항목 | java-cef | cefweaver |
| --- | --- | --- |
| `CefSettings`의 필드 20개 (**해결**: [F58](verified-findings-handlers.md)) | 모두 | 모두. `CefApp.settings`의 15개(`root_cache_path` 포함)와 `set_subprocess_path()`, `set_cache_path()`, `set_resources_path()`(리소스와 로케일 디렉터리), `offscreen`의 5개 |
| 버전 조회 (**해결**: [F59](verified-findings-handlers.md)) | `CefApp.getVersion()`: JCEF, CEF, Chrome 버전 | `cefweaver.get_version()`, `CefApp.get_version()` |
| 브라우저 여러 개 (**해결**: [F60](verified-findings-handlers.md)) | `CefClient.createBrowser(url, osr, transparent, requestContext)`를 몇 번이든 | `CefApp.create_browser(url, offscreen, transparent, request_context)` |
| 투명한 오프스크린 (**해결**) | `createBrowser`의 `isTransparent` | `CefApp.transparent` |

설정 가운데 일부(`user_agent`, `locale`, `log_file`, `log_severity`, `javascript_flags`, `remote_debugging_port`)는 같은 뜻의 명령줄 스위치를 `add_command_line_switch`로 줄 수 있을 가능성이 있으나, 설정 필드와 같은지는 확인하지 않았습니다. 나머지 필드는 스위치가 없어 설정 구조체로만 줄 수 있습니다.

java-cef의 Java 보조 클래스(`BoolRef`, `IntRef`, `StringRef`, 어댑터 클래스, AWT 창과 드롭 대상, `CefRenderer`)는 파이썬에서 필요가 없어 대응하지 않습니다.

## 열지 않고 정리만 하는 것 (java-cef 수준을 넘음)

- **응답 필터**(`CefResponseFilter`, `ResourceRequestHandler.get_resource_response_filter`): java-cef는 구현하지 않습니다.
- **창 정보로 팝업을 꾸미는 일**(`CefWindowInfo`, `CefBrowserSettings`가 든 `on_before_popup`, `on_before_dev_tools_popup`, `BrowserHost.show_dev_tools`): java-cef도 URL과 프레임 이름만 넘깁니다. 열려면 포인터가 든 구조체 종류가 필요합니다.

## 아직 열지 않은 것 (java-cef도 열지 않았거나 해당 없음)

- `CommandLine.init_from_argv`(`char* const*`): java-cef도 열지 않은 포인터 배열이라 같은 수준(안 엶)에 둡니다. (이전에 `AudioHandler.on_audio_stream_packet`도 여기 적었는데 틀렸습니다: java-cef에는 `CefAudioHandler`가 아예 없습니다. 아래 "오디오, WebRTC"를 보십시오.)
- `get_raw_data` 등 CEF가 소유한 메모리를 가리키는 `void*`: 안전을 위해 닫아 둡니다([바이트열과 시간](bytes-and-times.md)).

## 오디오, WebRTC (2026-10-08 점검)

java-cef 소스(`java/org/cef/handler/`의 핸들러 목록과 `native/client_handler.h`의 `ClientHandler`)에서 확인했습니다. 위키에는 이 주제의 페이지가 없었고(컨텍스트 메뉴 페이지에만 `MediaType`이 나옴), 소스로 직접 찾았습니다.

- **java-cef에 없는 것**: `CefAudioHandler`(오디오 스트림 시작, 패킷, 정지, 오류)와 `CefPermissionHandler`(`OnRequestMediaAccessPermission`: getUserMedia, `OnShowPermissionPrompt`)가 모두 없습니다. `ClientHandler`가 `GetAudioHandler`나 `GetPermissionHandler`를 재정의하지 않고, 저장소 전체에 `webrtc`, `media-stream`, `getUserMedia`, `MediaAccess`, `PermissionHandler`, `AudioHandler`, 자동 재생 관련 스위치가 한 군데도 없습니다.
- **있는 것은 둘뿐입니다**: (1) `CefBrowser_N.cpp`의 리눅스 키 변환이 `XF86XK_Audio*` 키(음량, 재생, 다음 곡)를 `VKEY_MEDIA_*`로 바꿔 줍니다. 오디오 처리가 아니라 키보드 입력입니다. (2) 컨텍스트 메뉴의 `CefContextMenuParams.MediaType`에 `CM_MEDIATYPE_AUDIO`가 있습니다.
- **CEF에는 있음**: 이 저장소가 쓰는 CEF 154 헤더에 `cef_audio_handler.h`(`GetAudioParameters`, `OnAudioStreamStarted`, `OnAudioStreamPacket`, `OnAudioStreamStopped`, `OnAudioStreamError`)와 `cef_permission_handler.h`(`CefPermissionHandler`의 세 메서드, `CefMediaAccessCallback`, `CefPermissionPromptCallback`)가 있습니다. java-cef가 쓰는 CEF 152에 있는지는 `third_party/cef`가 내려받아져 있지 않아 확인하지 못했습니다.
- **핸들러를 두지 않으면 어떻게 되는가**(CEF 154 헤더 주석): 마이크나 카메라 요청은 Chrome 스타일이면 권한 UI를 띄우고 **Alloy 스타일이면 거부**합니다. `--enable-media-stream` 스위치를 주면 모든 권한을 허용하고 이 메서드는 불리지 않습니다. 이 기본 동작을 실제로 실행해서 확인하지는 않았습니다.
- **cefweaver**: `PermissionHandler`는 열었습니다(2026-10-08, [F71](verified-findings-media.md)). `AudioHandler`도 열었습니다(2026-10-08, [F72](verified-findings-media.md)): 패킷의 `const float**`는 새 종류 `Planes`로 채널마다 `memoryview`를 줍니다. 둘 다 java-cef가 열지 않았으므로 우리 방침상 "바닥 위(더 여는 것)"에 해당합니다. cefpython은 `cefpython147` 브랜치(CEF 123)에서도 `enable-media-stream` 스위치 문서뿐이고 두 핸들러를 감싸지 않았습니다(헤더 `cef_audio_handler.h`, `cef_permission_handler.h`는 CEF 123 헤더 모음에 있으나 `src/*.pyx`와 `src/handlers/`에는 없음).

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [커버리지 보고서 (생성됨)](coverage-report.md)
- [설계 결정 기록](design-decisions.md)
- [cefpython과 cefweaver의 API 차이](../analyses/cefpython-comparison.md)
