---
title: Python API 참조
type: reference
sources:
  - cefweaver/_cefweaver.pyx
  - cefweaver/_cefweaver.pyi
  - tools/gen/handwritten.pyi
  - cefweaver/__init__.py
updated: 2026-10-08
---

# Python API 참조

`import cefweaver`로 얻는 공개 이름은 `cefweaver.__all__`입니다. 손으로 쓴 `CefApp` 하나와 생성된 이름들입니다. 시그니처의 전체는 `cefweaver/_cefweaver.pyi`(`py.typed` 포함)에 있고 타입 검사기(mypy)로 사용 예를 확인했습니다.

## CefApp (손으로 쓴 진입점)

한 프로세스에서 한 번만 초기화할 수 있습니다. 설정 메서드는 `initialize()` 전에만, 동작 메서드는 `initialize()` 후와 `shutdown()` 전에만 부를 수 있고 아니면 `RuntimeError`입니다.

| 메서드 | 설명 |
| --- | --- |
| `CefApp()` | 객체 생성 (CEF는 아직 시작되지 않음) |
| `set_subprocess_path(path)` | `cefsubprocess` 실행 파일 경로. 기본: 모듈 디렉터리의 `cefsubprocess` |
| `set_cache_path(path)` | 캐시와 프로필 디렉터리. 기본: 현재 디렉터리의 `cache/` |
| `set_resources_path(path)` | `CefSettings.resources_dir_path`로 전달. Linux에서는 `icudtl.dat` 위치에 영향이 없습니다. |
| `add_command_line_switch(name, value="")` | Chromium 스위치. 예: `"disable-gpu"`, `("ozone-platform", "x11")`. Linux에서 `ozone-platform`을 주지 않고 `DISPLAY`가 있으면 `initialize()`가 `x11`을 씁니다(네이티브 Wayland는 Alloy 스타일에서 죽음, F31) |
| `set_client(client)` | 표시, 수명 주기, 로드 이벤트를 받을 `Client`(또는 `None`). `initialize()` 전에만. `Client`가 아니면 `TypeError` |
| `devtools_menu` (속성, 읽고 쓰기) | 컨텍스트 메뉴의 "Show DevTools", "Close DevTools", "Inspect Element" 항목. 기본 `False`. 언제든 바꿀 수 있고 이후에 만들어지는 메뉴에 적용됩니다. 켜고 꺼도 사용자 핸들러가 받는 이벤트와 메뉴는 같고 항목만 뒤에 붙습니다 |
| `add_javascript_binding(name, callback)` | 페이지의 `window.<name>(...)`을 `callback(*args)`에 연결. `callback`이 호출 가능하지 않으면 `TypeError` |
| `initialize(start_url="about:blank")` | CEF를 시작하고 창을 만듭니다. 실패하면 `RuntimeError("CefInitialize() failed")`. **프로세스당 한 번**: `shutdown()` 뒤에 다시 부르면 `RuntimeError` |
| `do_message_loop_work()` | 메시지 루프를 한 번 실행. 주기적으로 호출해야 합니다. |
| `shutdown()` | CEF 종료. 시작하지 않았거나 이미 종료했으면 아무것도 하지 않습니다. |
| `load_url(url) -> bool` | 브라우저가 없으면 `False` |
| `execute_javascript(code) -> bool` | 브라우저가 없거나 로딩 중이면 `False` |
| `add_resource(url, content, mime_type="text/html", headers=None, status=200)` | 메모리의 내용을 http(s) URL로 제공. 비 http(s) URL은 `ValueError` |
| `is_running` (속성) | 시작했고 종료 전이며 창이 닫히지 않았으면 `True` |
| `is_ready_to_execute_javascript` (속성) | 페이지 로딩이 끝났으면 `True` |

동작은 [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md), [JavaScript 바인딩](../concepts/javascript-bindings.md), [리소스 제공](../concepts/resource-serving.md)에 있습니다. 인자로 받는 경로는 `str`, `bytes`, `os.PathLike`입니다.

## 열거형과 값 타입

열거형(`MouseButtonType`, `ErrorCode`, `EventFlags` 등 100개)과 값 타입은 `cefweaver.types`에 있습니다([types 모듈](types-module.md)). CEF가 주는 열거형 값은 멤버로 오고(`error_code is types.ErrorCode.ABORTED`), 일반 정수도 그대로 넘길 수 있습니다.

## 생성된 이름

| 종류 | 이름 |
| --- | --- |
| CEF가 구현하는 클래스(래퍼) | `Request`, `Response`, `Callback`, `ResourceReadCallback`, `ResourceSkipCallback`, `Browser`, `BrowserHost`, `Frame` |
| 애플리케이션이 구현하는 클래스(상속해서 씀) | `ResourceHandler`, `SchemeHandlerFactory`, `Client`, `LoadHandler`, `LifeSpanHandler`, `DisplayHandler` |
| 값 타입(이름 있는 튜플) | `Point(x, y)`, `Rect(x, y, width, height)`, `Size(width, height)`, `Insets(top, left, bottom, right)`, `Range(from_, to)`, `MouseEvent(x, y, modifiers)` |
| 전역 함수 | `register_scheme_handler_factory(scheme_name, domain_name, factory) -> bool`, `clear_scheme_handler_factories() -> bool`, `get_mime_type(extension) -> str` |

규칙은 다음과 같습니다([바인딩 생성기의 설계](../concepts/binding-generator.md), [핸들러 프록시 구조](../concepts/handler-proxies.md)).

- 이름은 PEP 8 형식입니다. `Cef` 접두사를 떼고, 메서드는 snake_case이며, 예약어는 밑줄을 붙입니다(`Callback.continue_()`).
- 라이브러리 클래스는 직접 만들 수 없습니다(`Request()`는 `TypeError`). 만드는 함수가 있는 클래스는 `Request.create()`처럼 씁니다. 객체는 CEF가 넘겨 주거나 `create()`로 얻습니다.
- 핸들러는 기반 클래스를 상속하고 필요한 메서드만 재정의합니다. 재정의하지 않은 메서드는 CEF의 기본 동작을 따릅니다. 출력 인자는 반환값으로 돌려줍니다(반환값이 먼저).
- `None`은 헤더가 `optional_param`으로 표시한 곳에만 허용됩니다. 그 밖에 `None`을 넘기면 `TypeError`입니다.
- 라이브러리 메서드가 CEF 객체를 반환하면 `X | None`(CEF가 객체를 주지 않을 수 있음)이고, `Create()` 정적 메서드만 항상 객체를 돌려줍니다.
- 값 타입은 튜플이라서 풀어서 받을 수 있고(`x, y, w, h = rect`), CEF에 넘길 때는 같은 필드의 일반 튜플도 됩니다. 길이가 다르면 `TypeError`입니다.
- 예외는 `sys.excepthook`으로 보고되고 CEF로 전파되지 않습니다.

## 예

```python
import cefweaver

class Late(cefweaver.ResourceHandler):
    def open(self, request, callback):
        ...               # 나중에 callback.continue_()를 부른다
        return True, False
    def get_response_headers(self, response):
        response.set_status(200)
        return 0, ""
    def read(self, data_out, callback):
        return False, 0
```

## 브라우저 이벤트 받기

`Client`의 `get_load_handler()`, `get_life_span_handler()`, `get_display_handler()`가 핸들러를 돌려주면 `set_client()`로 넘긴 뒤 이벤트가 그 핸들러의 메서드로 옵니다. 콜백은 `initialize()`를 부른 스레드에서 `do_message_loop_work()` 안에 실행됩니다(시험에서 확인). 래퍼가 스스로 하는 일(`is_ready_to_execute_javascript`, 오류 페이지, JS 바인딩)은 그대로 동작합니다.

```python
class Load(cefweaver.LoadHandler):
    def on_load_end(self, browser, frame, http_status_code):
        print("loaded", frame.get_url())
    def on_load_error(self, browser, frame, error_code, error_text, failed_url):
        print("failed", failed_url, error_code)   # 예: -102 (ERR_CONNECTION_REFUSED)

class MyClient(cefweaver.Client):
    def __init__(self):
        self.load = Load()
    def get_load_handler(self):
        return self.load

app = cefweaver.CefApp()
app.set_client(MyClient())
app.initialize("https://example.com")
```

`do_close`는 닫기를 시작할 때 호출되고(`host.close_browser(False)` 등), `True`를 돌려주면 닫기가 취소됩니다. 다시 `close_browser`를 부르면(이번에 `False`를 돌려주면) `on_before_close`로 이어집니다. 래퍼의 브라우저는 Alloy 스타일이라서 가능한 동작입니다([실험으로 확인한 사실](verified-findings-api.md) F18).

`send_mouse_*` 같은 입력은 **브라우저가 입력을 받을 준비가 되기 전에 보내면 버려지고**, 준비를 알리는 신호는 없습니다. 첫 프레임이 지난 뒤에도 가끔(측정에서 10번 중 1번) 첫 입력이 버려졌으므로, 확실히 전해야 하면 도착할 때까지 다시 보내야 합니다([실험으로 확인한 사실](verified-findings-api.md) F18).

## 브라우저 호스트

`browser.get_host()`(콜백이 받은 `Browser`에서 얻음)가 `BrowserHost`를 돌려줍니다. 줌(`set_zoom_level`, `get_zoom_level`), 마우스 입력(`send_mouse_click_event`, `send_mouse_move_event`, `send_mouse_wheel_event`), 자동 크기 조정(`set_auto_resize_enabled`), 닫기(`close_browser`, `try_close_browser`), 찾기, 인쇄, 오디오 음소거 등 53개 메서드가 열려 있고, 열리지 않은 19개와 이유는 [생성 범위와 커버리지](generated-api-coverage.md)에 있습니다. 구조체 인자는 이름 있는 튜플 또는 같은 필드의 일반 튜플입니다.

```python
host = browser.get_host()
host.set_zoom_level(1.0)
host.send_mouse_click_event(cefweaver.MouseEvent(50, 60, 0), 0, False, 1)  # 0: 왼쪽 버튼
host.close_browser(False)
```

## 컨텍스트 메뉴

`Client.get_context_menu_handler()`가 `ContextMenuHandler`를 돌려주면 메뉴를 고칠 수 있습니다(`on_before_context_menu(browser, frame, params, model)`의 `model`은 `MenuModel`). 메뉴를 코드로 열고 항목을 고르려면 `run_context_menu`가 `True`를 돌려주어 CEF의 메뉴를 대신하고 콜백으로 고릅니다.

```python
class Menu(cefweaver.ContextMenuHandler):
    def on_before_context_menu(self, browser, frame, params, model):
        model.add_item(types.MenuId.USER_FIRST, "My item")        # ids from USER_FIRST on
    def run_context_menu(self, browser, frame, params, model, callback):
        callback.continue_(types.MenuId.USER_FIRST, 0)             # pick it, no window needed
        return True
    def on_context_menu_command(self, browser, frame, params, command_id, event_flags):
        print("chosen:", command_id)
        return True                                                # False: CEF runs a standard command

host.send_mouse_click_event(types.MouseEvent(30, 30, 0), types.MouseButtonType.RIGHT, False, 1)
host.send_mouse_click_event(types.MouseEvent(30, 30, 0), types.MouseButtonType.RIGHT, True, 1)
```

사용자의 명령 ID는 `types.MenuId.USER_FIRST`(26500)부터 쓰고, 래퍼는 맨 끝의 3개(28498~28500)를 DevTools 항목에 씁니다. 처리하지 않는 명령(`False`)은 CEF가 표준 명령(전체 선택, 복사 등)으로 실행합니다. 메뉴 항목의 기본 이름은 로케일을 따릅니다(한국어 환경에서 "뒤로", "앞으로").

## 출력 인자를 돌려주는 메서드

C++에서 값을 참조 인자로 돌려주는 라이브러리 메서드는 파이썬에서 **반환값**입니다. 반환값이 있으면 그것이 먼저이고 출력이 뒤따릅니다.

```python
ok, key_code, shift, ctrl, alt = menu.get_accelerator(command_id)   # MenuModel
ok, color = menu.get_color(command_id, types.MenuColorType.TEXT)

point = display.convert_point_to_pixels(types.Point(10, 20))        # Display: a point goes in and comes back
```

구조체 참조(`CefPoint&`)만 입출력으로 다룹니다(`CefDisplay`와 `CefView`의 좌표 변환이 값을 읽고 고치기 때문). 그 밖의 참조 인자는 출력 전용이며 헤더가 방향을 표시하지 않으므로 이 구분은 헤더가 아닌 추정에 근거합니다([알려진 제약과 미검증 항목](known-constraints.md)).

## 목록을 주고받는 메서드

목록의 요소는 문자열(`list[str]`), 숫자(`list[int]`), 값 타입(`list[Rect]`, `list[Range]`), 객체(`list[Display]`)입니다. 라이브러리 메서드에 주는 목록은 아무 시퀀스나 되고 그 안의 값 타입은 일반 튜플도 됩니다.

```python
settings = cefweaver.PrintSettings.create()
settings.set_page_ranges([types.Range(1, 3), (5, 5)])
settings.get_page_ranges()                      # [Range(from_=1, to=3), Range(from_=5, to=5)]
cefweaver.Display.get_all_displays()            # [Display, ...]
ok, ids = cefweaver.TaskManager.get_task_manager().get_task_ids_list()   # (True, [0, 1, ...])

class Drag(cefweaver.DragHandler):
    def on_draggable_regions_changed(self, browser, frame, regions):
        # CSS `-webkit-app-region: drag` gives [DraggableRegion(bounds=Rect(10, 20, 300, 40), draggable=1)]
        ...
```

`Client.get_drag_handler()`가 `DragHandler`를 돌려주면 드래그 영역 변화를 받습니다(`on_drag_enter`는 `DragData`가 아직 없어서 열리지 않았습니다). 프레임 식별자는 `"5-725574D5..."` 같은 문자열이고, 이름 목록의 순서는 호출마다 같다는 보장이 없습니다(`['inner', '']`와 `['', 'inner']`가 모두 나왔습니다). 시험에서 `srcdoc` iframe을 쓸 때는 `data:` 페이지가 아니라 `add_resource` 페이지에 넣어야 합니다(F27).

## 종료 뒤의 객체

`app.shutdown()` 뒤에 해제되는 라이브러리 객체(`Browser`, `TaskManager` 등)는 CEF의 `Release()`를 부르지 않고 버립니다. CEF가 이미 종료되었으므로 아무도 쓰지 않고, 종료된 CEF에 `Release()`를 부르면 프로세스가 죽는 객체(`TaskManager`)가 있기 때문입니다([실험으로 확인한 사실 2](verified-findings-api.md) F30).

## 관련 페이지

- [Cython 확장 모듈](../components/cython-extension.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
- [시험](../components/tests.md)
