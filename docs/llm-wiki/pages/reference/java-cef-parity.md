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

시험 `test_the_gaps_to_the_java_cef_floor_are_the_listed_ones`가 이 목록을 고정합니다. 격차를 메우면 시험의 기대값에서 지웁니다. 지금 389개 가운데 64개입니다.

| 묶음 | 항목 | 필요한 것 |
| --- | --- | --- |
| PDF 인쇄 | `BrowserHost.PrintToPDF`(+`PdfPrintCallback`) | 문자열이 있는 구조체(`PdfPrintSettings`) |
| 드래그 | `CefDragData`(24), `DragHandler.OnDragEnter`, `RenderHandler.StartDragging`, `BrowserHost.DragTargetDragEnter` | `DragData`, 쓰기 핸들러 |
| 쿠키 | `CefCookieManager`(6), `CefCookieAccessFilter`(2), `ResourceRequestHandler.GetCookieAccessFilter` | 쿠키 구조체, 방문자와 완료 콜백 |
| URL 요청 | `CefURLRequest`(5), `CefURLRequestClient`(5) | 클래스 추가 |
| 요청 컨텍스트 | `CefRequestContext`(3), `CefRequestContextHandler`(1) | 설정 구조체, 값 컨테이너(이미 있음) |
| 기타 | `CefCommandLine`(12), `CefSchemeRegistrar`(1), 앱 훅(명령줄 처리, 사용자 스킴 등록) | 맵(`GetSwitches`), 클래스 추가 |

### 메운 격차

- 문자열 방문자(`Frame.GetSource`/`GetText`), 파일 대화상자 콜백(`BrowserHost.RunFileDialog`), DevTools 메시지 관찰자(`AddDevToolsMessageObserver`, `Registration`)([검증](verified-findings-more.md) F49).
- 창 핸들(`BrowserHost.GetWindowHandle`): Linux의 X11 창 번호를 정수로([검증](verified-findings-more.md) F48).
- 헤더 맵(`Request.GetHeaderMap`/`SetHeaderMap`/`Set`, `Response.GetHeaderMap`/`SetHeaderMap`): 문자열 멀티맵 ↔ `dict`([검증](verified-findings-more.md) F47).
- 팝업(`OnBeforePopup`), 커서 변경(`OnCursorChange`), 인증서 오류의 `ssl_info`: java-cef가 넘기지 않는 인자를 무시하는 규칙으로([검증](verified-findings-more.md) F46).

## 바닥 위 (우리가 더 연 것, java-cef에는 없음)

닫지 않고 둡니다. 총 252개 메서드이고 목록은 `coverage-report.md`의 "beyond the floor" 절에 있습니다. 묶음별로는 다음과 같습니다.

- **값 컨테이너와 프로세스 메시지**: `Value`, `ListValue`, `DictionaryValue`, `BinaryValue`, `ProcessMessage`. (`RequestContext`의 설정은 `Value`가 필요해서 바닥이 이것을 쓰게 됩니다.)
- **스트림**: `StreamReader`, `StreamWriter`, `ZipReader`, `ReadHandler`, `WriteHandler`(java-cef는 드래그 파일 내용용 쓰기 핸들러만 안에서 씀).
- **화면과 작업**: `Display`, `TaskManager`.
- **메뉴**: `MenuModelDelegate`, `RunContextMenuCallback`, `RunQuickMenuCallback`, 컨텍스트 메뉴 핸들러의 `RunContextMenu`/`RunQuickMenu` 등 4개.
- **핸들러의 추가 메서드**: `DisplayHandler`(6), `RenderHandler`(6: 스크롤, IME, 텍스트 선택, 터치, 가상 키보드), `RequestHandler`(4), `LifeSpanHandler`(1), `DownloadHandler`(1), `DragHandler`(1), `Client`(1: 프로세스 메시지).
- **브라우저 호스트 등의 추가 메서드**: `BrowserHost` 33개(IME, 터치, 줌, 탐색 항목 등), `Browser` 2개, `Frame` 4개, `MenuModel` 8개, `ContextMenuParams` 2개, `DownloadItem` 4개, `Response` 4개, `PostData` 1개.
- **그 밖**: `SSLInfo`, `UnresponsiveProcessCallback`, 시간(`datetime`)과 바이트열 규칙의 일반 규칙들(`bytes-and-times.md`).
- **메시지 라우터**: 바이트열 요청과 응답은 java-cef에 없습니다(문자열만).

## 관련 페이지

- [생성 범위와 커버리지](generated-api-coverage.md)
- [커버리지 보고서 (생성됨)](coverage-report.md)
- [설계 결정 기록](design-decisions.md)
