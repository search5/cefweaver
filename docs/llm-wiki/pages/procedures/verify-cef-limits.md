---
title: CEF의 한계를 CEF 예제로 검증하기
type: procedure
sources:
  - tests/test_smoke.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
updated: 2026-10-09
---

# CEF의 한계를 CEF 예제로 검증하기

**규칙**: 어떤 현상이 "CEF의 한계"로 보여도 래퍼의 문제와 가르기 전에는 한계라고 적지 않습니다. 검증하지 못했으면 "원인 미조사"로 적고, 검증했으면 방법과 근거(실행한 예제, 소스 위치)를 함께 적습니다. (BrowserSettings의 글꼴 크기가 되돌아가는 현상을 CEF의 한계로 적으려다가 이 규칙이 생겼습니다.)

## 방법 1: 래퍼 없이 같은 설정을 CEF 예제에 넣는다

1. CEF 배포본의 예제(`third_party/cef/cef_binary_*/tests/cefsimple/simple_app.cc`)를 백업하고, `CefBrowserSettings browser_settings;` 다음에 환경 변수를 읽는 줄을 넣습니다.

   ```cpp
   if (const char* v = getenv("BS_DEFAULT_FONT_SIZE")) browser_settings.default_font_size = atoi(v);
   if (getenv("BS_IMAGES_OFF")) browser_settings.image_loading = STATE_DISABLED;
   ```

2. 예제만 빌드합니다. 빌드 트리가 있으면 `make cefsimple`입니다(`-Werror=unused-variable`이므로 쓰지 않는 변수를 남기지 않습니다). 시험이 끝나면 원본을 되돌리고 다시 빌드합니다.
3. 로컬 HTTP 서버가 내는 페이지를 `--url`로 열고 `--remote-debugging-port`로 DevTools 프로토콜(`Runtime.evaluate`)에 연결해 값을 읽습니다. 페이지가 로드 때 자기 값을 `window.__early`에 적어 두면 처음 값과 나중 값을 비교할 수 있습니다.
4. **두 스타일을 모두** 확인합니다. 기본은 Chrome 스타일이고 `--use-alloy-style`이 Alloy 스타일입니다(cefweaver는 Alloy만 씁니다).
5. 가상 X 서버에서만 실행합니다(`env -u WAYLAND_DISPLAY xvfb-run -a ...`). 주의: 스크래치 디렉터리에 `bisect.py`처럼 표준 라이브러리와 같은 이름의 파일을 두면 `websocket` 같은 모듈이 그것을 불러 엉뚱한 오류가 납니다.

## 방법 2: CEF 소스를 읽는다

CEF 소스(`/home/jiho/cef_framework/cef_origin`)에서 값이 어디서 쓰이는지 찾아 줄 번호를 적습니다. Chromium의 소스는 이 환경에 없어서, CEF가 값을 넘기는 데까지만 확인할 수 있고 그 뒤의 동작은 관찰로만 적습니다.

## 지금까지의 검증

| 현상 | 검증 | 결과 |
| --- | --- | --- |
| 글꼴 크기(`default_font_size` 등)가 되돌아감 | `cefsimple`, 두 스타일 | **CEF**: Chrome 스타일은 처음 30px/50px에서 16px로 되돌아가고 Alloy 스타일은 처음부터 16px입니다. 래퍼와 무관 |
| `default_encoding`이 반영되지 않음 | `cefsimple`, 두 스타일 | **CEF**: `document.characterSet`이 `windows-1252`. 래퍼와 무관 |
| `data:` 이미지가 `image_loading` 비활성에서도 그려짐 | `cefsimple`, 두 스타일 | **Chromium/Blink**: `http:` 이미지는 막히고(`naturalWidth` 0) `data:`는 로드됨 |
| 오프스크린에서 전역 `background_color`가 무시됨 | CEF 소스 `libcef/browser/context.cc`(`GetColor`, `GetBackgroundColor`) | **CEF의 규칙**(알파 0은 투명으로 확정) |
| `DragData.get_file_name()`이 프로세스를 죽임 | CEF 소스 `libcef/common/drag_data_impl.cc` 113~117줄 | CEF가 확인 없이 Chromium의 `DropData::GetSafeFilenameForImageFileContents()`를 부름. `CHECK`는 Chromium 안(소스 없음) |
| 밑줄 색이 화면에 없음 | CEF 소스 `libcef/browser/osr/render_widget_host_view_osr.cc` 853~860줄 | CEF는 색을 `ImeTextSpan`의 `underline_color`로 **전달함**. 그리지 않는 쪽은 Chromium 렌더러이고 소스가 없어 확인하지 못함 |
| 허용한 인증서 오류가 다시 묻지 않음 | 래퍼로 `/first` 허용 뒤 `/second`, `/third`를 거부하도록 해도 `on_certificate_error`가 다시 불리지 않고 페이지가 로드됨 | **Chromium의 호스트별 예외 기억**. CEF는 `Continue()`를 Chromium으로 넘기기만 함(`libcef/browser/certificate_query.cc`) |
| 창 모드가 Wayland에서 코드로 닫히지 않고 종료 때 죽음 | `cefsimple --use-native --use-alloy-style`에 `CLOSE_AFTER_MS`(시작 후 몇 ms 뒤 `CloseAllBrowsers(true)`)를 더해 빌드하고 종료 시각을 잼. 뒤에 원본으로 되돌려 다시 빌드 | **CEF**: X11은 4.3초에 종료, Wayland는 40초 안에 끝나지 않음. 래퍼와 무관 |

## 관련 페이지

- [실행해서 확인한 핸들러](../reference/verified-findings-handlers.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
- [충돌 조사 방법](debug-crashes.md)
