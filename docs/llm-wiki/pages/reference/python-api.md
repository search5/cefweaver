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
| `add_command_line_switch(name, value="")` | Chromium 스위치. 예: `"disable-gpu"`, `("ozone-platform", "x11")` |
| `add_javascript_binding(name, callback)` | 페이지의 `window.<name>(...)`을 `callback(*args)`에 연결. `callback`이 호출 가능하지 않으면 `TypeError` |
| `initialize(start_url="about:blank")` | CEF를 시작하고 창을 만듭니다. 실패하면 `RuntimeError("CefInitialize() failed")` |
| `do_message_loop_work()` | 메시지 루프를 한 번 실행. 주기적으로 호출해야 합니다. |
| `shutdown()` | CEF 종료. 시작하지 않았거나 이미 종료했으면 아무것도 하지 않습니다. |
| `load_url(url) -> bool` | 브라우저가 없으면 `False` |
| `execute_javascript(code) -> bool` | 브라우저가 없거나 로딩 중이면 `False` |
| `add_resource(url, content, mime_type="text/html", headers=None, status=200)` | 메모리의 내용을 http(s) URL로 제공. 비 http(s) URL은 `ValueError` |
| `is_running` (속성) | 시작했고 종료 전이며 창이 닫히지 않았으면 `True` |
| `is_ready_to_execute_javascript` (속성) | 페이지 로딩이 끝났으면 `True` |

동작은 [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md), [JavaScript 바인딩](../concepts/javascript-bindings.md), [리소스 제공](../concepts/resource-serving.md)에 있습니다. 인자로 받는 경로는 `str`, `bytes`, `os.PathLike`입니다.

## 생성된 이름

| 종류 | 이름 |
| --- | --- |
| CEF가 구현하는 클래스(래퍼) | `Request`, `Response`, `Callback`, `ResourceReadCallback`, `ResourceSkipCallback`, `Browser`, `Frame` |
| 애플리케이션이 구현하는 클래스(상속해서 씀) | `ResourceHandler`, `SchemeHandlerFactory` |
| 전역 함수 | `register_scheme_handler_factory(scheme_name, domain_name, factory) -> bool`, `clear_scheme_handler_factories() -> bool`, `get_mime_type(extension) -> str` |

규칙은 다음과 같습니다([바인딩 생성기의 설계](../concepts/binding-generator.md), [핸들러 프록시 구조](../concepts/handler-proxies.md)).

- 이름은 PEP 8 형식입니다. `Cef` 접두사를 떼고, 메서드는 snake_case이며, 예약어는 밑줄을 붙입니다(`Callback.continue_()`).
- 라이브러리 클래스는 직접 만들 수 없습니다(`Request()`는 `TypeError`). 만드는 함수가 있는 클래스는 `Request.create()`처럼 씁니다. 객체는 CEF가 넘겨 주거나 `create()`로 얻습니다.
- 핸들러는 기반 클래스를 상속하고 필요한 메서드만 재정의합니다. 재정의하지 않은 메서드는 CEF의 기본 동작을 따릅니다. 출력 인자는 반환값으로 돌려줍니다(반환값이 먼저).
- `None`은 헤더가 `optional_param`으로 표시한 곳에만 허용됩니다. 그 밖에 `None`을 넘기면 `TypeError`입니다.
- 라이브러리 메서드가 CEF 객체를 반환하면 `X | None`(CEF가 객체를 주지 않을 수 있음)이고, `Create()` 정적 메서드만 항상 객체를 돌려줍니다.
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

## 관련 페이지

- [Cython 확장 모듈](../components/cython-extension.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
- [시험](../components/tests.md)
