---
title: GTK 3 예제 (오프스크린 위젯)
type: reference
sources:
  - examples/gtk3/cefgtk.py
  - examples/gtk3/browser.py
  - examples/gtk3/smoke.py
  - examples/gtk3/pyproject.toml
  - examples/gtk3/README.md
updated: 2026-10-08
---

# GTK 3 예제

`examples/gtk3/`에 `Gtk.DrawingArea`로 오프스크린 브라우저를 보여 주는 예제가 있습니다. 환경 구성과 실행은 그 디렉터리의 `README.md`에 있고, 여기에는 실제로 돌려서 확인한 것과 발견한 것을 적습니다([F67](verified-findings-handlers.md)).

## 구성

- **`Runtime`**: `CefApp` 하나, `JavascriptBridge`, `MessagePump`를 만들고 GLib 메인 루프에 잇습니다. `MessagePump`의 `wake`(CEF의 어느 스레드에서나 불림)는 `GLib.idle_add`로, 기한은 `GLib.timeout_add`로 받으므로 폴링이 없습니다([F62](verified-findings-handlers.md)).
- **`CefWidget`**: `on_paint`의 BGRA 버퍼를 더러운 사각형의 행만 `bytearray`에 복사해 cairo `ImageSurface`(ARGB32)로 그립니다. HiDPI는 `set_device_scale`로 맞춥니다. 팝업(`<select>`)은 두 번째 표면으로 그립니다. 마우스, 휠, 키는 GTK 이벤트를 CEF 이벤트로 바꾸고(`windows_key_code` 표, 수정자, `RAWKEYDOWN`/`CHAR`/`KEYUP`), 한글은 `Gtk.IMMulticontext`의 `commit`과 `preedit-changed`를 `ime_commit_text`와 `ime_set_composition`으로 잇습니다. `on_ime_composition_range_changed`의 글자 경계로 입력기의 후보 창 위치를 정합니다.

## 확인한 것 (실제 GTK 창, Xvfb, 3번 연속과 HiDPI)

`smoke.py`가 실제 X 이벤트(xdotool)로 구동해 19개를 점검하고 `ALL OK`로 끝납니다. 1배와 `GDK_SCALE=2` 모두 통과했습니다.

- 그림의 크기가 위젯과 같고(HiDPI에서는 장치 픽셀) 페이지의 `devicePixelRatio`가 화면 배율과 같습니다. 스크린샷으로 선명함을 확인했습니다.
- 제목이 창에, 주소가 주소창에 반영되고 클릭으로 입력란에 포커스가 가며, 입력한 키와 BackSpace와 `Ctrl+A`가 입력란에 닿습니다.
- 한글 조합(`set_preedit`)과 확정(`commit_text`)이 입력란에 들어가고 페이지가 `compositionupdate`를 봅니다.
- 페이지가 Python을 부르고(`add(2, 3)`, `appReady`), Python이 페이지를 불러 값을 받습니다(`evaluate`).
- `<select>`의 팝업이 그려지고 `Escape`로 닫힙니다. 휠이 스크롤하고, 링크 클릭으로 이동하면 주소창이 따라가며 뒤로 가기가 됩니다. 창 크기가 페이지 크기가 됩니다.
- 창을 닫으면 브라우저가 닫히고 CEF가 종료됩니다.
- 확인하지 못한 것: 실제 한글 입력기(ibus, fcitx)와의 동작(Xvfb에 없음), 복사와 붙여넣기, 드래그 앤 드롭, Wayland 네이티브 GTK.

## 발견한 것

1. **`on_after_created`에서 `CefApp`을 쓸 수 없던 결함(수정함)**: 첫 브라우저는 `initialize()` 안에서 만들어지고 그 핸들러가 `initialize()`가 끝나기 전에 불리는데, 그때 `add_resource`와 `load_url`이 "초기화되지 않았다"고 거부했고 `load_url`은 첫 브라우저를 아직 몰라 `False`였습니다. GUI 응용이 가장 먼저 하는 일이라 `initialize()`가 CEF를 부르기 전에 상태를 정하고 첫 브라우저를 `on_after_created`에서 알도록 고쳤습니다(시험 `test_the_app_can_be_used_from_on_after_created_of_the_first_browser`).
2. **뒤로 가기 캐시로 복원된 페이지가 크기 변경을 받지 않음(원인 미확인, 우회 있음)**: 링크 클릭으로 이동했다가 뒤로 가면, 위젯과 CEF가 그리는 그림은 새 크기를 따르는데 페이지의 `innerWidth`는 이전 값(900)에 머뭅니다. `reload`한 페이지는 정상입니다. `disable-features=BackForwardCache`를 주면 사라집니다. 일반 `was_resized()`, 포커스 토글, `invalidate`는 소용없고 `notify_screen_info_changed()`와 `was_hidden(True)` 뒤 `was_hidden(False)`는 페이지를 깨웁니다. 그래서 위젯이 로딩이 끝날 때마다 `notify_screen_info_changed()`를 부릅니다. **GTK 없이 순수 cefweaver 오프스크린 스크립트에서는 재현되지 않았고**(포커스, 마우스 이동, 화면 정보, 브리지와 라우터, 대기 시간을 바꿔 가며 확인), 예제의 최소 재현(`클릭으로 이동 → 뒤로 → 창 크기 변경`)에서는 결정적입니다. 원인이 CEF인지 위젯인지 가르지 못했으므로 CEF의 한계로 적지 않습니다.
3. **uv와 로컬 wheel**: wheel을 다시 만들면 `uv.lock`의 해시가 어긋나 `uv sync`가 멈춥니다(`--upgrade-package cefweaver`로 해결). PyGObject와 pycairo는 PyPI에서 소스 빌드로 설치되었고(`libgirepository-2.0-dev`, `libcairo2-dev` 필요) 약 5초 걸렸습니다.
4. **HiDPI 좌표(시험 쪽)**: GTK는 논리 픽셀로, X 서버와 xdotool은 장치 픽셀로 셉니다. 위젯은 GTK의 논리 좌표를 그대로 CEF에 주면 맞고, 시험이 xdotool에 줄 때 배율을 곱해야 했습니다.

## 관련 페이지

- [메시지 펌프](verified-findings-handlers.md)(F62)와 [JavascriptBridge](javascript-bridge.md)
- [오프스크린 렌더링](offscreen-rendering.md)
- [cefpython과 cefweaver의 API 차이](../analyses/cefpython-comparison.md)
