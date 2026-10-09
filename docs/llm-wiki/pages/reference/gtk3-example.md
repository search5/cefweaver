---
title: GTK 3 예제 (오프스크린 위젯)
type: reference
sources:
  - cefweaver/ui/toolkits/gtk3.py
  - cefweaver/ui/view.py
  - examples/gtk3/browser.py
  - examples/gtk3/smoke.py
  - examples/gtk3/pyproject.toml
  - examples/gtk3/README.md
updated: 2026-10-09
---

# GTK 3 예제

`examples/gtk3/`에 `Gtk.DrawingArea`로 오프스크린 브라우저를 보여 주는 예제가 있습니다. 환경 구성과 실행은 그 디렉터리의 `README.md`에 있고, 여기에는 실제로 돌려서 확인한 것과 발견한 것을 적습니다([F67](verified-findings-handlers.md)).

## 구성

**`cefweaver.ui` 위에 있습니다**([UI 어댑터 API](ui-api.md)). 핸들러, 이벤트 조립, 클릭 횟수, 입력기 호출, 드래그 앤 드롭의 순서는 `BrowserView`가 맡고, 이 파일은 GTK가 해야 하는 일만 합니다(663줄에서 555줄). 아래 `Runtime`은 `ui.Session`의 얇은 하위 클래스입니다.

- **`Runtime`**: `CefApp` 하나, `JavascriptBridge`, `MessagePump`를 만들고 GLib 메인 루프에 잇습니다. `MessagePump`의 `wake`(CEF의 어느 스레드에서나 불림)는 `GLib.idle_add`로, 기한은 `GLib.timeout_add`로 받으므로 폴링이 없습니다([F62](verified-findings-handlers.md)).
- **`CefWidget`**: `on_paint`의 BGRA 버퍼를 dirty rect의 행만 `bytearray`에 복사해 cairo `ImageSurface`(ARGB32)로 그립니다. HiDPI는 `set_device_scale`로 맞춥니다. 팝업(`<select>`)은 두 번째 표면으로 그립니다. 마우스, 휠, 키는 GTK 이벤트를 CEF 이벤트로 바꾸고(`windows_key_code` 표, 수정자, `RAWKEYDOWN`/`CHAR`/`KEYUP`), 한글은 `Gtk.IMMulticontext`의 `commit`과 `preedit-changed`를 `ime_commit_text`와 `ime_set_composition`으로 잇습니다. `on_ime_composition_range_changed`의 글자 경계로 입력기의 후보 창 위치를 정합니다.

## 확인한 것 (실제 GTK 창, Xvfb, 3번 연속과 HiDPI)

`smoke.py`가 실제 X 이벤트(xdotool)로 구동해 33개를 점검하고 `ALL OK`로 끝납니다. 1배와 `GDK_SCALE=2` 모두 통과했고 1배는 3번 연속 통과했습니다. **`cefweaver.ui` 위로 옮긴 뒤에도 점검을 하나도 바꾸지 않고 같은 27개가 통과했습니다**(1배 3번과 배율 2). 배율 2는 창이 장치 픽셀로 1280x1024 화면을 넘으므로 `xvfb-run -s "-screen 0 2560x2048x24"`로 실행합니다(작은 화면에서는 아래쪽 드래그 원본 위젯이 화면 밖에 놓여 드래그 점검 3개가 실패했고, 이식 전의 위젯도 같았습니다). 데모 페이지의 `drop zone`(하늘색)은 놓은 내용을 바로 아래의 표시 줄(`#dropinfo`)에 보여 줍니다(`dropped text "..."`나 `dropped files ...`). 표시 줄은 처음부터 높이가 고정이라 놓아도 레이아웃이 움직이지 않습니다(로그에 한 줄씩 더하면 아래 요소가 밀려 드롭 영역의 좌표가 어긋나고, 파일을 영역 밖에 놓으면 Chromium이 그 파일로 이동해 버립니다). 노란 `drag me`를 끌어다 놓거나 다른 프로그램의 텍스트와 파일을 놓아 손으로 시험할 수 있고, 점검이 이것을 지킵니다(2026-10-09). 컨텍스트 메뉴는 어댑터의 `show_menu`가 `Gtk.Menu`로 보여 주고, 점검이 실제 오른쪽 클릭과 항목 클릭(앱의 항목을 훅으로 더함), Escape로 닫기를 지킵니다. CEF의 응답이 이벤트 처리 밖에서 오므로 오른쪽 버튼 `Gdk.Event`를 만들어 팝업에 넘겨 GTK의 "no trigger event for menu popup" 경고를 없앴습니다(2026-10-09).

- 그림의 크기가 위젯과 같고(HiDPI에서는 장치 픽셀) 페이지의 `devicePixelRatio`가 화면 배율과 같습니다. 스크린샷으로 선명함을 확인했습니다.
- 제목이 창에, 주소가 주소창에 반영되고 클릭으로 입력란에 포커스가 가며, 입력한 키와 BackSpace와 `Ctrl+A`가 입력란에 닿습니다.
- 한글 조합(`set_preedit`)과 확정(`commit_text`)이 입력란에 들어가고 페이지가 `compositionupdate`를 봅니다.
- 페이지가 Python을 부르고(`add(2, 3)`, `appReady`), Python이 페이지를 불러 값을 받습니다(`evaluate`).
- `<select>`의 팝업이 그려지고 `Escape`로 닫힙니다. 휠이 스크롤하고, 링크 클릭으로 이동하면 주소창이 따라가며 뒤로 가기가 됩니다. 창 크기가 페이지 크기가 됩니다.
- **복사, 잘라내기, 붙여넣기**: `Ctrl+C`가 입력란의 선택과 일반 문단의 선택을 GTK 클립보드에 넣고, `Ctrl+X`가 잘라내며, `Ctrl+V`가 GTK 클립보드의 텍스트(한글 포함)를 붙여 넣습니다. **위젯에 따로 쓴 코드는 없습니다.** 키 이벤트를 CEF에 그대로 전달하면 Chromium이 자체 클립보드(X11 선택)로 처리하고 그것이 GTK 클립보드와 오갑니다(구현 전에 통과해서 확인).
- **드래그 앤 드롭** (실제 XDND, 마우스를 누른 채 움직임): GTK의 텍스트를 페이지에 떨어뜨림, GTK의 **파일**을 페이지에 떨어뜨림(`ondrop`의 `files`에 이름이 옴), 페이지의 `draggable` 요소를 GTK 입력란에 떨어뜨림, 페이지 안에서 끌어다 놓음(위젯이 원본이자 대상).
- 창을 닫으면 브라우저가 닫히고 CEF가 종료됩니다.
- 확인하지 못한 것: 실제 한글 입력기(ibus, fcitx)와의 동작(Xvfb에 없음), 서식이 있는(HTML) 붙여넣기와 이미지 복사, Wayland 네이티브 GTK.

## 발견한 것

1. **`on_after_created`에서 `CefApp`을 쓸 수 없던 결함(수정함)**: 첫 브라우저는 `initialize()` 안에서 만들어지고 그 핸들러가 `initialize()`가 끝나기 전에 불리는데, 그때 `add_resource`와 `load_url`이 "초기화되지 않았다"고 거부했고 `load_url`은 첫 브라우저를 아직 몰라 `False`였습니다. GUI 응용이 가장 먼저 하는 일이라 `initialize()`가 CEF를 부르기 전에 상태를 정하고 첫 브라우저를 `on_after_created`에서 알도록 고쳤습니다(시험 `test_the_app_can_be_used_from_on_after_created_of_the_first_browser`).
2. **뒤로 가기 캐시로 복원된 페이지가 크기 변경을 받지 않음(원인 미확인, 우회 있음)**: 링크 클릭으로 이동했다가 뒤로 가면, 위젯과 CEF가 그리는 그림은 새 크기를 따르는데 페이지의 `innerWidth`는 이전 값(900)에 머뭅니다. `reload`한 페이지는 정상입니다. `disable-features=BackForwardCache`를 주면 사라집니다. 일반 `was_resized()`, 포커스 토글, `invalidate`는 소용없고 `notify_screen_info_changed()`와 `was_hidden(True)` 뒤 `was_hidden(False)`는 페이지를 깨웁니다. 그래서 위젯이 로딩이 끝날 때마다 `notify_screen_info_changed()`를 부릅니다. **GTK 없이 순수 cefweaver 오프스크린 스크립트에서는 재현되지 않았고**(포커스, 마우스 이동, 화면 정보, 브리지와 라우터, 대기 시간을 바꿔 가며 확인), 예제의 최소 재현(`클릭으로 이동 → 뒤로 → 창 크기 변경`)에서는 결정적입니다. 원인이 CEF인지 위젯인지 가르지 못했으므로 CEF의 한계로 적지 않습니다.
3. **uv와 로컬 wheel**: wheel을 다시 만들면 `uv.lock`의 해시가 어긋나 `uv sync`가 멈춥니다(`--upgrade-package cefweaver`로 해결). PyGObject와 pycairo는 PyPI에서 소스 빌드로 설치되었고(`libgirepository-2.0-dev`, `libcairo2-dev` 필요) 약 5초 걸렸습니다.
4. **HiDPI 좌표(시험 쪽)**: GTK는 논리 픽셀로, X 서버와 xdotool은 장치 픽셀로 셉니다. 위젯은 GTK의 논리 좌표를 그대로 CEF에 주면 맞고, 시험이 xdotool에 줄 때 배율을 곱해야 했습니다.

## 드래그 앤 드롭에서 찾은 것

OSR 수준의 시험(CEF의 `drag_target_*`와 `start_dragging`)이 통과해도 툴킷 쪽 번역이 맞는 것은 아니어서, 실제 GTK 드래그로 시험해서 위젯의 결함 둘을 찾았습니다.

1. **CEF의 응답이 비동기**: `drag_target_drag_over`에 대한 `update_drag_cursor`(드롭 동작)는 렌더러에서 나중에 옵니다. 그 전의 응답(0)으로만 GTK에 알리면 드롭 영역 위에서도 GTK가 드롭을 거부합니다. 응답이 올 때 `Gdk.drag_status`를 다시 불러야 합니다(위젯의 `set_drag_operation`).
2. **드래그 종료 처리의 오류가 CEF의 드래그 상태를 막음**: `drag-end`에서 예외가 나 `drag_source_ended_at`을 부르지 못하자 이어지는 드롭이 실패했습니다.

또 GTK는 드롭 대상이 먼저 데이터를 요청해야 내용을 알 수 있어(`drag_get_data`), CEF에 `drag_target_drag_enter`를 부르기 전에 비동기로 받아야 하고, `drag-drop` 직전에도 `drag-leave`가 오므로 이탈과 드롭을 구분합니다. **페이지 쪽 규칙**으로, 드롭 영역은 `dragover`뿐 아니라 `dragenter`도 `preventDefault` 해야 합니다(다른 요소에서 들어와 영역으로 옮기는 드래그가 거부됨. CEF 직접 호출로 가려 확인).

## 관련 페이지

- [메시지 펌프](verified-findings-handlers.md)(F62)와 [JavascriptBridge](javascript-bridge.md)
- [오프스크린 렌더링](offscreen-rendering.md)
- [cefpython과 cefweaver의 API 차이](../analyses/cefpython-comparison.md)
