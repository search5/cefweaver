---
title: UI 어댑터 API (cefweaver.ui)
type: reference
sources:
  - cefweaver/ui/__init__.py
  - cefweaver/ui/adapter.py
  - cefweaver/ui/view.py
  - cefweaver/ui/session.py
  - cefweaver/ui/keys.py
  - cefweaver/ui/headless.py
  - examples/tk/quickstart.py
  - cefweaver/ui/toolkits/__init__.py
  - cefweaver/ui/toolkits/gtk3.py
  - cefweaver/ui/toolkits/qt.py
  - cefweaver/ui/audio.py
  - cefweaver/ui/permissions.py
  - cefweaver/ui/menu.py
  - cefweaver/ui/toolkits/tk.py
  - cefweaver/ui/toolkits/sdl2.py
  - cefweaver/ui/toolkits/wx.py
  - cefweaver/ui/toolkits/kivy.py
  - tests/test_ui.py
updated: 2026-10-09
---

# UI 어댑터 API (cefweaver.ui)

GUI 툴킷에 오프스크린 브라우저를 붙일 때 [툴킷 예제](toolkit-examples.md)의 위젯 코드를 베끼지 않고 **툴킷이 해야 하는 일만** 구현하게 하는 하위 패키지입니다. 실험적이며 인터페이스가 바뀔 수 있습니다. 설계와 근거는 [UI 어댑터 설계](../analyses/ui-adapter-design.md)에 있고, 여기에는 구현된 것(계획의 2단계)을 적습니다. 순수 Python이고 CEF 프로세스 없이 시험할 수 있습니다.

## 구성

| 이름 | 내용 |
| --- | --- |
| `BrowserView(adapter)` | 브라우저 하나와 CEF 쪽 규칙 전부: 핸들러 5종(`view.client`), 입력 이벤트의 조립, 클릭 횟수, 입력기, 클립보드 키, 드래그 앤 드롭의 순서 |
| `ToolkitAdapter` | 툴킷이 구현할 필수 7개: `view_size`, `scale`, `screen_origin`, `screen_size`, `present(frame)`, `post(fn)`, `call_later(seconds, fn)` |
| 선택 메서드 | `set_cursor`, `clipboard_get`과 `clipboard_set`, `set_ime_rect`, `start_drag_out`, `drag_operation_changed`. 있으면 그 기능이 켜집니다 |
| `capabilities` | 어댑터의 속성(집합). `"native_clipboard"`는 CEF가 클립보드 키를 직접 처리해도 된다는 뜻(지금은 쓰는 툴킷이 없음: CEF의 클립보드는 Wayland에서 컴포지터의 것이라 GTK 3도 어댑터가 처리하게 바꿈, F76), `"drag_out"`은 `start_drag_out`으로 툴킷의 드래그를 시작할 수 있다는 뜻 |
| `Session(adapter, switches, cache_path)` | `CefApp`, `JavascriptBridge`, `MessagePump`. `ozone-platform`을 주지 않으면 Wayland 컴포지터가 있을 때 `wayland`를 더합니다(`session.default_ozone_platform()`, 시험하지 못한 환경에서 문제가 나면 `("ozone-platform", "x11")`를 주세요). 실제로 CEF에 준 스위치는 `session.switches`입니다. CEF의 깨움을 `adapter.post`로, 기한을 `adapter.call_later`로 받아 폴링 없이 돌립니다. `start(target, url)`(`BrowserView`이나 `BrowserWidget`을 받음), `shutdown(done)`(끝나면 어댑터의 선택 메서드 `release()`를 부름: 루프가 놓을 것이 있을 때, 예를 들어 파이프). 툴킷마다 `Session` 하위 클래스를 둘 필요가 없고 `ui.Session(툴킷의 루프, ...)`로 충분합니다 |
| `Frame` | `present()`가 받는 그림: `kind`(`VIEW`, `POPUP`, `POPUP_HIDDEN`), `width`, `height`, `buffer`(BGRA, 호출 동안만 유효), `dirty_rects`, 팝업은 `rect`, 뷰의 `PictureStore`가 이 프레임으로 한 일 `change` |
| `keys` | CEF 이벤트 플래그(`SHIFT`, `CONTROL`, `ALT`, 단추)와 가상 키 코드(`VK_*`), `vk_for_char`, `vk_for_function` |
| `PictureStore`, `write_png` | 뷰가 모든 프레임을 보관하는 저장소(`view.store`)와 의존성 없는 PNG 쓰기(`view.snapshot(path)`, `BrowserWidget.snapshot`): 툴킷마다 snapshot을 구현할 필요가 없습니다. 그림의 픽셀을 프레임 사이에 보관: CEF의 버퍼는 `present()` 동안만 유효하므로 복사본(`pixels`, 팝업은 `popup_pixels`와 `popup_rect`)을 두고, 같은 크기의 프레임은 dirty rect의 행만 제자리에서 고칩니다. `apply(frame)`이 `NEW`(새 표면을 만들 것), `DIRTY`(바뀐 사각형, 그림 안으로 잘림), `POPUP`, `POPUP_HIDDEN`을 돌려줌. cairo나 `QImage`처럼 픽셀을 복사 없이 감싸는 툴킷용(GTK 3, Qt) |
| `BrowserWidget` | 툴킷 위젯의 기반 클래스(맨 앞에 둠): `attach_view(adapter)`로 `view`를 만들고, `browser`, `popup_visible`, `popup_rect`, `load_url`, `go_back`, `go_forward`, `reload`, `close_browser`, `commit_text`, `set_preedit`를 갖는다. 알림은 훅 `browser_title`, `browser_address`, `browser_loading`, `browser_ready`를 재정의해서 받음 |
| `KeyTable`, `function_range` | 툴킷 키의 가상 키 코드: 특수 키 표, 기능 키 범위(`function_range(첫 기능 키 코드)`), 문자 키(`char`), 가상 키가 없는 글자는 코드 포인트(`others_as_code_point`) |
| `MaskModifiers`, `NamedModifiers`, `EventModifiers` | 툴킷의 수정 키와 단추 상태를 CEF 플래그로: 비트 마스크(GTK, Tk, SDL2, Qt), 이름 목록(Kivy), 이벤트에 묻기(wx). 단추가 따로 오는 툴킷은 `flags(state, buttons)` |
| `CursorTable` | `types.CursorType`에 대한 툴킷의 커서와 기본값 |
| `headless.HeadlessAdapter` | 툴킷 없는 어댑터: 자체 루프(`run_until`, `run_for`), 마지막 그림 보관, `save_png`, `pixel` |

## 툴킷이 부르는 입력

`resized()`, `focus(bool)`, `shown(bool)`, `mouse_move(x, y, mods, leave=False)`, `mouse_button(x, y, "left"|"middle"|"right", pressed, mods, clicks=None)`, `wheel(x, y, dx, dy, mods)`, `key(down, windows_key_code, native_code, mods, char=None)`(클립보드 키를 처리했으면 True), `text(str)`, `preedit(str, cursor)`. 좌표는 논리 픽셀이고 수정 키는 `keys`의 합입니다.

드래그 앤 드롭은 툴킷이 말하는 방식에 따라 갈립니다. 단계마다 데이터와 함께 알려 주는 툴킷(GTK, Qt)은 `drag_enter(x, y, ops, text=, html=, url=, files=)`, `drag_over`, `drag_leave`, `drag_drop`을 부릅니다. 데이터를 놓는 순간에야 주는 툴킷(wx)은 같은 메서드를 데이터 없이 부르고 `drag_drop(..., text=)`에 데이터를 실으며, 데이터 없는 단계는 페이지 자신의 드래그가 아니면 뷰가 무시합니다. 놓는 순간만 아는 툴킷(SDL2, Kivy)은 `drop(x, y, text=, ...)`을 부릅니다.

나가는 드래그는 어댑터에 `start_drag_out`이 없으면 뷰가 페이지 안에서만 중계하고, 있으면 `DragPayload`를 받아 툴킷의 드래그를 시작합니다. **언제 시작하는지는 어댑터의 `drag_start` 속성**이 정하고 뷰가 일정을 맡습니다: `"immediate"`(GTK. 호출 안에서), `"posted"`(Qt. CEF의 콜백이 끝난 뒤 루프에서), `"on_motion"`(wx. 버튼을 누른 채 포인터가 다음에 움직일 때. 그 전에 버튼을 떼면 뷰가 `NONE`으로 끝냄). 시작한 호출은 드래그가 끝날 때까지 돌아오지 않아도 되고, 끝나면 `drag_out_finished(x, y, operation)`을 부릅니다. `view.dragging_out`은 페이지의 드래그가 진행 중인지 알려 줍니다.

## 예제에서 옮겨 온 규칙 (시험으로 지킴)

- 클릭 횟수는 0.4초와 4픽셀 안에서 3까지 세고, 툴킷이 횟수를 주면 그것을 씁니다. 누르면 `focus(True)`를 줍니다(SDL2 예제에서 필요했음).
- Ctrl이나 Alt가 눌리면 `CHAR`를 보내지 않습니다. Enter, Tab, BackSpace는 항상 `CHAR`를 보냅니다.
- 클립보드 키는 어댑터에 `clipboard_get`과 `clipboard_set`이 있고 `native_clipboard`가 없을 때만 뷰가 처리합니다(키를 뗄 때도 소비).
- 로딩이 끝나면 `notify_screen_info_changed()`를 부릅니다([F67](verified-findings-handlers.md)).
- `leave`는 한 박자 미루고(GTK는 놓기 직전에 `leave`를 보냄), 한꺼번에 오는 드롭은 `dragover`의 답(`update_drag_cursor`)을 기다린 뒤 놓되 0.5초가 한계입니다([F69](verified-findings-handlers.md)).

## 사용: quickstart

툴킷마다 `examples/<툴킷>/quickstart.py`가 가장 작은 프로그램입니다(Tk는 15줄 안팎: `ui.Session(TkLoop(root))`, `CefCanvas(root, session)`, `on_ready`에서 `load_url`, 창을 닫을 때 `session.shutdown(root.destroy)`, `session.start(canvas)`). 같은 코드가 각 예제의 `README.md`와 프로젝트의 `README.rst`(Tk)에 실려 있고, 시험이 파일과 문서가 어긋나지 않는지(`QuickstartDocs`), 그리고 **실제로 뜨고 창을 닫으면 종료 코드 0으로 끝나는지**(`Quickstarts`: 데이터 URL을 띄워 제목을 받고 WM_DELETE_WINDOW를 보냄) 확인합니다. `Quickstarts`는 예제의 uv 환경이 있고 X 서버가 있을 때만 돌고 아니면 건너뜁니다. 어댑터를 쓰는 사용자는 이 코드 외에 복사할 것이 없습니다(키 표와 커서 표 같은 툴킷의 어휘는 어댑터 모듈 안에 있음).

## 툴킷별 어댑터는 패키지에 둡니다

여섯 어댑터는 `cefweaver.ui.toolkits.{gtk3,qt,tk,sdl2,wx,kivy}` 모듈입니다. 사용: `from cefweaver.ui.toolkits import qt`. **`cefweaver`와 `cefweaver.ui`는 이 모듈들을 임포트하지 않으므로**(시험이 지킴) 툴킷이 없어도 `import cefweaver`는 영향받지 않고, 선택 의존성은 `cefweaver[qt]`, `[gtk3]`, `[tk]`, `[sdl2]`, `[kivy]`입니다(wxPython은 PyPI에 wheel이 없어 extras에 넣지 않았고 [예제의 설치 방법](toolkit-examples.md)을 따름).

**왜 별도 배포판이 아닌가**: 핵심 API(`cefweaver.ui`)가 아직 바뀝니다(이식할 때마다 고쳤음). 어댑터가 같은 저장소에 있으면 핵심과 어댑터를 한 커밋에서 고치고 점검으로 확인할 수 있습니다. 어댑터마다 책임질 사람이 아직 없어서 따로 배포하면 사용자에게 불편만 더합니다. **나누는 기준**: 어댑터에 대한 외부 이슈나 PR이 우리가 처리할 수 있는 속도를 넘으면, 또는 툴킷의 버전을 따라가는 일을 맡을 사람이 생기면 그 어댑터부터 별도 배포판으로 나눕니다.

**나누기 쉽도록 지키는 규칙**(시험이 지킴, `ToolkitModules`): 툴킷마다 모듈 하나, 모듈끼리 임포트하지 않음, 뷰의 비공개 속성(`view._...`)을 쓰지 않음, 모듈 맨 위에 `Checked:`(무엇으로 점검했는지)와 `Not checked:`(점검하지 못한 것)를 적음. **이 패키지는 실험적이며 점검은 가상 X 서버(xvfb)의 합성 이벤트로 했습니다.** 실제 입력기, Wayland 네이티브, Qt 외의 HiDPI는 어느 모듈도 확인하지 못했습니다.

## 이식 결과 (3단계)

여섯 예제를 모두 이 API 위로 옮겼습니다. 점검은 하나도 바꾸지 않고 통과해야 이식이 끝난 것입니다.

| 예제 | 위젯 파일(표와 전략과 기반 클래스까지 뺀 지금) | 점검 | 확인한 것 |
| --- | --- | --- | --- |
| `gtk3` | 663줄에서 485줄 | 33개 통과 | 아래 |
| `tk` | 464줄에서 266줄 | 24개 통과(2번 연속) | 어댑터 없이 `Session`을 `post`(큐와 파이프)와 `call_later`(`after`)만으로 구동. 클립보드 키와 페이지 안의 드래그를 뷰가 처리(Tk 코드에서 사라짐) |
| `sdl2` | 547줄에서 354줄 | 28개 통과 | 뷰이자 루프인 클래스가 `post`(큐와 `SDL_PushEvent`)와 `call_later`(시간 순 목록과 `SDL_WaitEventTimeout`)를 직접 구현. 드롭은 `drop()`으로 통일되어 `dragover`의 답을 기다림 |
| `kivy` | 530줄에서 282줄 | 27개 통과, 실제 앱의 창 닫기도 종료 코드 0 | `Clock.schedule_once`가 `post`와 `call_later`를 겸함(`ClockEvent`가 `cancel()`을 가짐). 드롭 이벤트가 위치를 주므로 `drop(x, y, ...)`에 그대로 대응 |
| `wx` | 547줄에서 294줄 | 28개 통과 | `drag_out` 능력과 `drop()`을 함께 시험. 위젯에는 wx 고유의 것만 남음: 마우스 핸들러 안에서만 드래그를 시작하는 규칙, `DropSource`가 데이터를 소유하지 않는 것, 자기 드래그와 외부 드롭을 가르는 `_dragging_out` |
| `qt` | 573줄에서 396줄 | 35개 통과: PyQt6와 PySide6 모두, 배율 1과 2 | 시그널이 `post`를, `QTimer`가 `call_later`를 맡음. 복사와 붙여넣기 모두 뷰가 Qt 클립보드로 처리(붙여넣기는 일반 텍스트만. 이식 전에는 CEF에 맡겼음) |

GTK 3 예제를 이 API 위로 옮기며([GTK 3 예제](gtk3-example.md)) 고친 것: 인터페이스에서 고친 것 셋: `BrowserView.commit_text()`(입력기가 확정한 글자는 ASCII 한 글자도 입력기 경로로. `text()`는 한 글자를 키로 만듦), `DragPayload`의 시작 위치 `x`, `y`, 새 드래그가 시작할 때 `drag_operation`을 복사로 되돌리기. 또 `Session`이 툴킷에 요구하는 것은 `post`와 `call_later`뿐이라 위젯(과 그 어댑터)이 생기기 전에 CEF를 만들 수 있습니다(`GlibLoop`).

## 소리 출력 (audio)

`BrowserView(adapter, audio=...)`: `"auto"`(기본 없음: `None`이면 소리를 받지 않음), 싱크 객체, 또는 `None`. 싱크는 `start(sample_rate, channels)`, `write(samples, frames)`(frames x channels개의 little-endian float32, 인터리브), `stop()`을 가집니다(CEF의 오디오 스레드에서 불리므로 막으면 안 됨). `"auto"`는 어댑터의 `audio_sink()`(SDL2 `SdlSink`, Qt `QtSink`), 없으면 `cefweaver.ui.audio.PygameSink`(`pip install cefweaver[pygame]`), 그것도 없으면 소리 없음입니다. 싱크가 예외를 내면 떼어내고 `on_audio_error`로 한 번 알립니다. `BrowserWidget.attach_view(adapter, audio=...)`가 그대로 넘깁니다. 확인한 내용은 [F74](verified-findings-media.md)입니다.

## 마이크와 카메라 (권한 정책)

`BrowserView(adapter, media_permissions=정책)`(또는 세션을 시작하기 전에 `view.media_permissions = 정책`). 페이지가 `getUserMedia`를 부르면 `정책(요청)`이 불리고, 요청은 `origin`, `permissions`(`types.MediaAccessPermissionTypes`), `is_main_frame`을 가지며 `allow(권한=None)`(요청한 것보다 많이는 주지 않음)이나 `deny()`로 답합니다. 지금 답해도 되고 나중에(사용자에게 물은 뒤) 답해도 되며, 한 번만 답할 수 있습니다. 정책이 예외를 내면 거부하고 `sys.excepthook`으로 보고합니다. 정책이 없으면(기본) CEF의 기본 처리(거부)입니다. 도우미 `ui.permissions.allow_origins("https://meet.example.org", ...)`는 그 출처에만 마이크와 카메라를 주고 화면 캡처는 주지 않습니다. 소리는 Chromium이 시스템 마이크에서 직접 받습니다([F77](verified-findings-media.md)).

## 컨텍스트 메뉴 (우클릭)

오프스크린에서는 CEF가 메뉴를 그려 주지 않아서 어댑터가 `show_menu(items, x, y, done)`을 가지면(선택) 뷰가 CEF의 메뉴 모델을 `ui.menu.MenuItem` 목록(`kind`: command, check, radio, separator, submenu. `label`은 단축키 표시 `&`를 뗀 것, `enabled`, `checked`, `children`)으로 바꿔 넘깁니다. 어댑터는 툴킷의 메뉴 위젯으로 `(x, y)`(뷰 좌표)에 보여 주고 고른 항목의 `command_id`로 `done(command_id)`를, 그냥 닫으면 `done(None)`을 부릅니다(한 번만 유효). 표준 명령(뒤로, 복사, 전체 선택 등)은 CEF가 실행합니다. `show_menu`가 없는 어댑터는 메뉴가 안 뜨는 지금까지와 같습니다. 앱은 `view.on_context_menu = 훅`으로 메뉴를 고칩니다: `훅(info, items)`가 보여 줄 목록을 돌려주고(`None`이면 메뉴 없음), `info`는 `x`, `y`, `link_url`, `source_url`, `page_url`, `selection_text`, `is_editable`을 가지며, `MenuItem("라벨", action=함수)`는 앱의 항목으로 골랐을 때 함수만 실행합니다(CEF에는 알리지 않음). 훅이나 `show_menu`가 예외를 내면 메뉴를 취소하고 `sys.excepthook`으로 보고합니다.

## 아직 하지 않은 것

- (여섯 예제를 모두 이식했습니다.) 남은 일은 툴킷별 어댑터를 패키지에 둘지 정하는 것과 같은 세션에 브라우저 여러 개를 다루는 것입니다.
- 한 세션에 브라우저 하나만 다룹니다.
- 툴킷별 공식 어댑터는 패키지에 넣지 않았습니다(`examples/`에 둘 예정).

## 관련 페이지

- [UI 어댑터 설계](../analyses/ui-adapter-design.md)와 [툴킷 예제](toolkit-examples.md)
- [메시지 펌프](verified-findings-handlers.md)(F62)
