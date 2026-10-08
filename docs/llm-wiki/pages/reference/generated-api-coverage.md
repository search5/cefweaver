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

범위(`scope.py`)는 클래스 17개와 전역 함수 3개입니다. 클래스의 메서드(가상과 정적) 294개 가운데 242개가 생성되고 52개가 제외되며, 함수 3개를 더해 245개입니다.

| 클래스 | 쪽 | 생성/전체 | 제외 사유 |
| --- | --- | --- | --- |
| `CefResourceHandler` | 핸들러 | 7/7 | |
| `CefSchemeHandlerFactory` | 핸들러 | 1/1 | |
| `CefCallback` | 라이브러리 | 2/2 | |
| `CefResourceReadCallback` | 라이브러리 | 1/1 | |
| `CefResourceSkipCallback` | 라이브러리 | 1/1 | |
| `CefRequest` | 라이브러리 | 18/23 | `CefPostData`가 범위 밖(3), 헤더 맵(멀티맵) 2 |
| `CefResponse` | 라이브러리 | 16/18 | 헤더 맵(멀티맵) 2 |
| `CefFrame` | 라이브러리 | 20/26 | `CefStringVisitor`, `CefV8Context`, `CefDOMVisitor`, `CefURLRequest`, `CefProcessMessage`가 범위 밖(6) |
| `CefBrowser` | 라이브러리 | 21/21 | |
| `CefDisplay` | 라이브러리 | 15/16 | 벡터 1(`get_all_displays`는 `Display` 객체의 목록) |
| `CefMenuModel` | 라이브러리 | 57/57 | |
| `CefMenuModelDelegate` | 핸들러 | 7/7 | |
| `CefBrowserHost` | 라이브러리 | 53/72 | 범위 밖 클래스 7(`CefRequestContext`, `CefNavigationEntry` 등), 값 타입 4(`CefWindowHandle` 2, `CefKeyEvent`, `CefTouchEvent`), 구조체 4(`cef_window_info_t` 3, `cef_pdf_print_settings_t`), 벡터 2(`run_file_dialog`는 라이브러리 메서드에 주는 벡터, `ime_set_composition`은 요소가 문자열이 아님), 핸들러 객체 반환 1(`get_client`), 타입 없는 포인터 1 |
| `CefClient` | 핸들러 | 3/19 | 다른 핸들러 15개가 범위 밖(`CefRequestHandler`, `CefContextMenuHandler` 등), `CefProcessMessage`가 범위 밖(1) |
| `CefLoadHandler` | 핸들러 | 4/4 | |
| `CefLifeSpanHandler` | 핸들러 | 4/6 | 값 타입 `CefPopupFeatures`(`on_before_popup`), 구조체 `cef_window_info_t`(`on_before_dev_tools_popup`) |
| `CefDisplayHandler` | 핸들러 | 12/13 | 값 타입 `CefCursorHandle`(`on_cursor_change`) |

제외된 52개의 사유는 범위 밖 클래스 32, 값 타입 6과 구조체 5, 멀티맵 4, 벡터 3, 핸들러 객체 반환 1, 타입 없는 포인터 1입니다. 범위 밖 클래스 가운데 16개는 `CefClient`가 돌려줄 다른 핸들러와 `CefProcessMessage`입니다. 범위 밖 클래스는 그 클래스를 추가하면 열립니다([새 클래스를 생성 범위에 추가하기](../procedures/add-class-to-generator.md)).

## 모든 클래스를 범위에 넣는다면

보고서는 "모든 클래스를 범위에 넣었을 때 타입 지원만으로 어디까지 되는가"도 계산합니다. 154 헤더에서 메서드와 함수 1,598개 가운데 1,398개(87%)입니다. 값 타입 구조체를 지원하기 전에는 1,287개(81%), 문자열 벡터를 지원하기 전에는 1,354개(85%), 라이브러리 출력 인자를 지원하기 전에는 1,373개(86%)였습니다. 남은 장애물은 다음과 같습니다.

| 개수 | 사유 | 대응 |
| --- | --- | --- |
| 36 | 벡터(요소가 문자열이 아닌 것: `CefRect`, `CefV8Value`, `CefRefPtr<...>` 등) | 요소 종류 추가 |
| 3 | 라이브러리 메서드에 주는 벡터 | 입력 방향 추가 |
| 33 | 값 타입(`CefKeyEvent`, `CefBaseTime`, `CefWindowHandle`, `CefTouchEvent` 등 평범한 데이터가 아닌 것) | 구조체 종류의 확장 |
| 32 | 소유 포인터(`CefOwnPtr`) | 소유권 이전 규칙 |
| 24 | 타입 없는 포인터(`void*` 단독 등) | |
| 18 | C 구조체(`cef_*_t`: 설정, 쿠키, `cef_window_info_t` 등) | 구조체 종류의 확장 |
| 11 | 라이브러리 메서드가 핸들러 객체를 반환 | |
| 11 | 원시 포인터(`CefRawPtr`) | |
| 8 | 포인터 | |
| 8 | 멀티맵 | |
| 4 | 맵 | |
| 5 | 핸들러 메서드가 구조체를 값으로 반환(`CefSize` 4, `CefRect` 1) | 반환 규칙 |
| 4 | `CefRefPtr` 참조 | |
| 2 | 클래스 | |
| 1 | 핸들러 메서드가 라이브러리 객체를 반환 | |

표의 사유는 보고서의 묶음 이름을 한국어로 옮긴 것입니다. 클래스별 지원 비율은 [커버리지 보고서](coverage-report.md)의 "Per class" 절에 있습니다(모든 클래스가 나열되고 지금 범위 안의 클래스에는 `*`가 붙습니다). 메서드가 많은 클래스는 `CefV8Value`(67개), `CefView`(52개), `CefWindow`(43개), `CefBrowserHost`(72개) 같은 V8과 뷰 계열입니다.

## 생성기의 한계와 다음 단계

생성기를 만든 직후(기준 커밋 `f9e459c`, 1단계: 리소스 핸들러)에 정리한 메모를 이 절로 옮겼습니다. 이전에는 `tools/gen/STATUS.md`에 있었습니다.

### 한계와 미검증

- Windows와 다른 CEF 버전에서의 재생성은 확인하지 못했습니다. 파서는 CEF master의 것(2026-09-29)이고 154 헤더에서 정상 동작했지만, 다른 버전의 헤더에서는 시험하지 않았습니다.
- `CefClient`는 표시, 수명 주기, 로드 핸들러만 돌려줄 수 있습니다. 나머지 핸들러 15개(`CefRequestHandler`, `CefContextMenuHandler`, `CefKeyboardHandler`, `CefFocusHandler` 등)와 `OnProcessMessageReceived`는 생성하지 않았습니다. 래퍼가 컨텍스트 메뉴와 JavaScript 바인딩 메시지를 스스로 처리하므로, 이 둘을 사용자에게 열려면 래퍼의 처리와 사용자의 처리를 어떻게 합칠지 정해야 합니다.
- `on_before_popup`(`CefPopupFeatures`는 `size` 머리가 있음), `on_before_dev_tools_popup`(`cef_window_info_t`), `on_cursor_change`(`CefCursorHandle`)는 아직 열리지 않았습니다. 평범한 데이터가 아닌 구조체(`size` 머리, 열거형 필드, 문자 필드)는 지원하지 않습니다.
- 헤더의 한국어 설명(`cef_origin` 위키)은 아직 스텁에 쓰지 않았고 헤더의 영어 주석을 그대로 쓰고 있습니다.
- 대상 클래스를 상속하는 클래스(예: `CefDictionaryValue` 계열)는 아직 처리하지 않습니다.
- 생성기를 만든 변경(기준 커밋 `f9e459c`)은 문서와 시험이 생성기, 모듈 연결, 시험이라는 여러 묶음에 걸쳐 있고 묶음별 커밋은 `cef_api.pxi` 없이 빌드되지 않아서, 합의한 기준(파일이 겹치면 한 번에)대로 커밋 하나로 했습니다.

### 다음 단계

`CefClient`를 사용자 객체로 위임하는 구조와 `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`는 2026-10-08에 구현했고([설계 결정 기록](design-decisions.md)), 이어서 값 타입 구조체(`Point`, `Rect`, `Size`, `Insets`, `Range`, `MouseEvent`), `CefBrowserHost`, 문자열 벡터(`browser.get_frame_names()`, `on_favicon_url_change`), 라이브러리 메서드의 출력 인자(`MenuModel`, `Display`)를 지원했습니다. 남은 선택지는 보고서 기준으로 다음과 같으며 어느 쪽을 먼저 진행할지는 아직 정해지지 않았습니다.

1. 벡터의 요소 종류를 넓힙니다(36건과 라이브러리 메서드에 주는 벡터 3건): 구조체 목록(`dirty_rects`), 객체 목록(`get_all_displays`) 등. 오프스크린 렌더링의 `on_paint`가 이 위에 있습니다.
2. 나머지 핸들러를 `CefClient`에 추가합니다. `MenuModel`을 열었으므로 컨텍스트 메뉴 핸들러의 `on_before_context_menu(browser, frame, params, model)`에 필요한 `MenuModel`은 준비되었습니다. 컨텍스트 메뉴와 프로세스 메시지는 위의 "합치는 방법" 결정이 먼저입니다.
3. 구조체 종류를 넓힙니다(`size` 머리가 있는 `CefKeyEvent`, `CefPopupFeatures` 등).

확인하지 못한 항목 전체는 [알려진 제약과 미검증 항목](known-constraints.md)에 있습니다.

## 관련 페이지

- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [새 타입 지원 추가하기](../procedures/add-type-to-generator.md)
- [Python API 참조](python-api.md)
