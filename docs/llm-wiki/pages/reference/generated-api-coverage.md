---
title: 생성 범위와 커버리지
type: reference
sources:
  - docs/llm-wiki/pages/reference/coverage-report.md
  - tools/gen/scope.py
  - tools/gen/report.py
updated: 2026-10-08
---

# 생성 범위와 커버리지

[커버리지 보고서](coverage-report.md)(`python tools/gen/generate.py --report`)의 요약입니다. 수치는 CEF 154.0.34 헤더 기준이며, 버전이 바뀌면 보고서를 다시 읽어야 합니다. 원본은 항상 그 보고서입니다.

## 지금 생성되는 것

범위(`scope.py`)는 클래스 53개와 전역 함수 3개입니다. 클래스의 메서드(가상과 정적) 583개 가운데 535개가 생성되고 48개가 제외되며, 함수 3개를 더해 538개입니다.

| 클래스 | 쪽 | 생성/전체 | 제외 사유 |
| --- | --- | --- | --- |
| `CefResourceHandler` | 핸들러 | 7/7 | |
| `CefSchemeHandlerFactory` | 핸들러 | 1/1 | |
| `CefCallback` | 라이브러리 | 2/2 | |
| `CefResourceReadCallback` | 라이브러리 | 1/1 | |
| `CefResourceSkipCallback` | 라이브러리 | 1/1 | |
| `CefRequest` | 라이브러리 | 18/23 | `CefPostData`가 범위 밖(3), 헤더 맵(멀티맵) 2 |
| `CefResponse` | 라이브러리 | 16/18 | 헤더 맵(멀티맵) 2 |
| `CefFrame` | 라이브러리 | 21/26 | `CefStringVisitor`(2), `CefV8Context`, `CefDOMVisitor`, `CefURLRequest`가 범위 밖(5) |
| `CefBrowser` | 라이브러리 | 21/21 | |
| `CefDisplay` | 라이브러리 | 16/16 | |
| `CefPrintSettings` | 라이브러리 | 23/23 | |
| `CefTaskManager` | 라이브러리 | 5/6 | 구조체 `cef_task_info_t`(`get_task_info`) |
| `CefMenuModel` | 라이브러리 | 57/57 | |
| `CefMenuModelDelegate` | 핸들러 | 7/7 | |
| `CefContextMenuHandler` | 핸들러 | 7/7 | |
| `CefContextMenuParams` | 라이브러리 | 20/20 | |
| `CefRunContextMenuCallback`, `CefRunQuickMenuCallback` | 라이브러리 | 2/2씩 | |
| `CefProcessMessage` | 라이브러리 | 6/7 | 범위 밖 클래스 `CefSharedMemoryRegion` |
| `CefValue` | 라이브러리 | 23/23 | |
| `CefListValue` | 라이브러리 | 29/29 | |
| `CefDictionaryValue` | 라이브러리 | 30/30 | |
| `CefStreamReader`, `CefStreamWriter`, `CefZipReader` | 라이브러리 | 8/8, 7/7, 12/13 | `CefZipReader.get_file_last_modified`(`CefBaseTime`). [스트림과 ZIP 읽기](streams.md) |
| `CefReadHandler`, `CefWriteHandler` | 핸들러 | 5/5씩 | |
| `CefBinaryValue` | 라이브러리 | 8/9 | 타입 없는 포인터 1(`get_raw_data`, 일부러 열지 않음) |
| `CefDragHandler` | 핸들러 | 1/2 | 범위 밖 클래스 `CefDragData`(`on_drag_enter`) |
| `CefBrowserHost` | 라이브러리 | 58/72 | 범위 밖 클래스 11(`CefRequestContext`, `CefNavigationEntry`, `CefDragData` 등), 값 타입 `CefWindowHandle` 2, 구조체 `cef_window_info_t`(`show_dev_tools`), `cef_pdf_print_settings_t`(`print_to_pdf`), 클라이언트 객체 반환 1(`get_client`) |
| `CefClient` | 핸들러 | 14/19 | 다른 핸들러 5개가 범위 밖(`CefAudioHandler`, `CefCommandHandler`, `CefFindHandler`, `CefFrameHandler`, `CefPermissionHandler`; java-cef도 구현하지 않음) |
| `CefLoadHandler` | 핸들러 | 4/4 | |
| `CefLifeSpanHandler` | 핸들러 | 4/6 | 값 타입 `CefPopupFeatures`(`on_before_popup`), 구조체 `cef_window_info_t`(`on_before_dev_tools_popup`) |
| `CefDisplayHandler` | 핸들러 | 12/13 | 값 타입 `CefCursorHandle`(`on_cursor_change`) |
| `CefRenderHandler` | 핸들러 | 14/17 | 범위 밖 클래스 `CefAccessibilityHandler`, `CefDragData`, 값 타입 `CefAcceleratedPaintInfo` |
| `CefFocusHandler`, `CefJSDialogHandler`, `CefDialogHandler`, `CefDownloadHandler`, `CefKeyboardHandler`, `CefPrintHandler` | 핸들러 | 3/3, 4/4, 1/1, 3/3, 2/2, 6/6 | 키보드의 `os_event`는 Python에 넘기지 않음 |
| `CefJSDialogCallback`, `CefFileDialogCallback`, `CefBeforeDownloadCallback`, `CefDownloadItemCallback`, `CefPrintDialogCallback`, `CefPrintJobCallback` | 라이브러리 | 1/1, 2/2, 1/1, 3/3, 2/2, 1/1 | |
| `CefRequestHandler` | 핸들러 | 10/11 | 범위 밖 클래스 `CefX509Certificate`(`on_select_client_certificate`) |
| `CefResourceRequestHandler` | 핸들러 | 6/8 | 범위 밖 클래스 `CefCookieAccessFilter`(`get_cookie_access_filter`, 쿠키 구조체), `CefResponseFilter`(`get_resource_response_filter`) |
| `CefAuthCallback`, `CefSSLInfo`, `CefUnresponsiveProcessCallback` | 라이브러리 | 2/2, 1/2, 2/2 | `CefSSLInfo.get_x509_certificate`(범위 밖 `CefX509Certificate`) |
| `CefDownloadItem` | 라이브러리 | 18/20 | 값 타입 `CefBaseTime`(`get_start_time`, `get_end_time`) |

제외된 48개의 사유는 범위 밖 클래스 28, 구조체 `cef_window_info_t` 5, 멀티맵 4, 값 타입 `CefWindowHandle` 2와 `CefBaseTime` 3, 구조체 `cef_pdf_print_settings_t`와 `cef_task_info_t` 각 1, 값 타입 `CefCursorHandle`과 `CefAcceleratedPaintInfo` 각 1, 타입 없는 포인터 1(`get_raw_data`), 클라이언트 객체 반환 1입니다. 범위 밖 클래스 가운데 5개는 `CefClient`가 돌려줄 다른 핸들러입니다. 범위 밖 클래스는 그 클래스를 추가하면 열립니다([새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)).

## 모든 클래스를 범위에 넣는다면

보고서는 "모든 클래스를 범위에 넣었을 때 타입 지원만으로 어디까지 되는가"도 계산합니다. 154 헤더에서 메서드와 함수 1,598개 가운데 1,458개(91%)입니다. 지원을 넓힌 순서대로 81%(1,287), 85%(1,354, 값 타입 구조체와 문자열 벡터), 86%(1,373), 87%(1,398, 라이브러리 출력 인자), 89%(1,422, 벡터의 요소 종류 확대), 90%(1,432, 구조체 종류 확대), 90%(1,446, 바이트열), 91%(1,454, 구조체 반환과 `T*` 출력 인자)였습니다. 남은 장애물은 다음과 같습니다.

| 개수 | 사유 | 대응 |
| --- | --- | --- |
| 34 | 값 타입(`CefKeyEvent`, `CefBaseTime`, `CefWindowHandle`, `CefTouchEvent` 등 평범한 데이터가 아닌 것) | 구조체 종류의 확장 |
| 32 | 소유 포인터(`CefOwnPtr`) | 소유권 이전 규칙 |
| 24 | 타입 없는 포인터(`void*` 단독 등) | |
| 18 | C 구조체(`cef_*_t`: 설정, 쿠키, `cef_window_info_t` 등) | 구조체 종류의 확장 |
| 11 | 라이브러리 메서드가 핸들러 객체를 반환 | |
| 11 | 원시 포인터(`CefRawPtr`) | |
| 9 | 벡터(요소가 `CefCompositionUnderline`처럼 평범하지 않은 구조체이거나 `CefRawPtr`) | 요소 종류 추가 |
| 8 | 포인터 | |
| 8 | 멀티맵 | |
| 5 | `CefRefPtr` 참조(객체 참조 출력 인자) | 방향 규칙 |
| 4 | 라이브러리 메서드에 주는 객체 목록(`CefV8Value` 목록 등) | 입력 방향 추가 |
| 4 | 맵 | |
| 5 | 핸들러 메서드가 구조체를 값으로 반환(`CefSize` 4, `CefRect` 1) | 반환 규칙 |
| 2 | 클래스 | |
| 1 | 핸들러 메서드가 라이브러리 객체를 반환 | |

표의 사유는 보고서의 묶음 이름을 한국어로 옮긴 것입니다. 클래스별 지원 비율은 [커버리지 보고서](coverage-report.md)의 "Per class" 절에 있습니다(모든 클래스가 나열되고 지금 범위 안의 클래스에는 `*`가 붙습니다). 메서드가 많은 클래스는 `CefV8Value`(67개), `CefView`(52개), `CefWindow`(43개), `CefBrowserHost`(72개) 같은 V8과 뷰 계열입니다.

## 생성기의 한계와 다음 단계

생성기를 만든 직후(기준 커밋 `f9e459c`, 1단계: 리소스 핸들러)에 정리한 메모를 이 절로 옮겼습니다. 이전에는 `tools/gen/STATUS.md`에 있었습니다.

### 한계와 미검증

- Windows와 다른 CEF 버전에서의 재생성은 확인하지 못했습니다. 파서는 CEF master의 것(2026-09-29)이고 154 헤더에서 정상 동작했지만, 다른 버전의 헤더에서는 시험하지 않았습니다.
- `CefClient`는 표시, 수명 주기, 로드 핸들러만 돌려줄 수 있습니다. 나머지 핸들러 15개(`CefRequestHandler`, `CefContextMenuHandler`, `CefKeyboardHandler`, `CefFocusHandler` 등)와 `OnProcessMessageReceived`는 생성하지 않았습니다. 래퍼가 컨텍스트 메뉴와 JavaScript 바인딩 메시지를 스스로 처리하므로, 이 둘을 사용자에게 열려면 래퍼의 처리와 사용자의 처리를 어떻게 합칠지 정해야 합니다.
- `on_before_popup`(`CefPopupFeatures`는 열렸지만 `CefWindowInfo`, `CefBrowserSettings`가 남음), `on_before_dev_tools_popup`(`cef_window_info_t`), `on_cursor_change`(`CefCursorHandle`)는 아직 열리지 않았습니다. 포인터, 배열, 문자열이 있는 구조체는 지원하지 않습니다.
- 헤더의 한국어 설명(`cef_origin` 위키)은 아직 스텁에 쓰지 않았고 헤더의 영어 주석을 그대로 쓰고 있습니다.
- 대상 클래스를 상속하는 클래스(예: `CefDictionaryValue` 계열)는 아직 처리하지 않습니다.
- 생성기를 만든 변경(기준 커밋 `f9e459c`)은 문서와 시험이 생성기, 모듈 연결, 시험이라는 여러 묶음에 걸쳐 있고 묶음별 커밋은 `cef_api.pxi` 없이 빌드되지 않아서, 합의한 기준(파일이 겹치면 한 번에)대로 커밋 하나로 했습니다.

### 다음 단계

`CefClient`를 사용자 객체로 위임하는 구조와 `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`는 2026-10-08에 구현했고([설계 결정 기록](design-decisions.md)), 이어서 값 타입 구조체(`Point`, `Rect`, `Size`, `Insets`, `Range`, `MouseEvent`, `DraggableRegion`), `CefBrowserHost`, 문자열 벡터, 라이브러리 메서드의 출력 인자(`MenuModel`, `Display`), 벡터의 요소 종류 확대(구조체 목록, 객체 목록, 정수 목록, 중첩 구조체)와 `DragHandler`, 컨텍스트 메뉴(`ContextMenuHandler`, `ContextMenuParams`), 프로세스 메시지와 값 컨테이너(`ProcessMessage`, `Value`, `ListValue`, `DictionaryValue`, `BinaryValue`)를 지원했습니다. 남은 선택지는 보고서 기준으로 다음과 같으며 어느 쪽을 먼저 진행할지는 아직 정해지지 않았습니다.

1. (완료) java-cef가 구현하는 핸들러 13개를 모두 추가했습니다(`CefRenderHandler`는 [오프스크린 렌더링](offscreen-rendering.md), 요청 핸들러는 래퍼의 라우터용 요청 핸들러와 결합). java-cef가 구현하는데 우리에게 없는 것: `CefCookieAccessFilter`(쿠키 구조체), `CefRequestContextHandler`(`CefRequestContext`), `GetResourceHandler`는 있음.
2. (완료) 구조체 종류를 `size` 머리, 열거형, `char16_t`까지 넓혔습니다(`CefKeyEvent`, `CefScreenInfo`, `CefPopupFeatures`, `CefTouchEvent`, `CefTouchHandleState`, `CefCompositionUnderline`). 남은 구조체는 `CefWindowInfo`, `CefBrowserSettings`, `CefCookie`처럼 문자열이나 포인터가 있는 것입니다.
3. (완료) 버퍼 종류: 핸들러의 `on_paint`는 읽기 전용 `memoryview`(크기 규칙 표 `SIZED_BUFFERS`), 라이브러리 메서드의 `const void*`와 `size_t` 쌍은 `bytes` 입력, `BinaryValue.get_data`는 `bytes` 출력(`BYTES_OUT` 표)입니다. 메시지 라우터는 손으로 쓴 중계로 열렸습니다([메시지 라우터](message-router.md)).
4. 객체 참조 출력 인자(`CefRefPtr<T>&`, 5건)와 라이브러리 메서드에 주는 객체 목록(4건).
5. 네이티브 Wayland에서 Alloy 스타일이 죽는 원인 조사(나중에 하기로 함). 지금은 `DISPLAY`가 있으면 X11을 기본으로 써서 피했을 뿐입니다. 순수 Wayland 세션(`DISPLAY` 없음)과 GUI 툴킷 임베딩에 필요합니다. 첫 실험은 래퍼를 `cefsimple`처럼 `CefRunMessageLoop`으로 돌려 비교하는 것입니다([Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)).

확인하지 못한 항목 전체는 [알려진 제약과 미검증 항목](known-constraints.md)에 있습니다.

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
- [Python API 참조](python-api.md)
