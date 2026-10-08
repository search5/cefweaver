---
title: 프로세스 모델과 스레드
type: concept
sources:
  - native/cefwrapper/library.cpp
  - native/cefsubprocess/cefsubprocess.cc
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - cefweaver/_cefweaver.pyx
  - tools/gen/emit_cython.py
updated: 2026-10-08
---

# 프로세스 모델과 스레드

## 프로세스

Chromium은 여러 프로세스로 동작하며, cefweaver에서는 다음과 같이 나뉩니다.

| 프로세스 | 실체 | 하는 일 |
| --- | --- | --- |
| 브라우저 프로세스 | **Python 프로세스 자신** | `CefInitialize`를 호출하고 창과 브라우저를 만들며 UI 스레드 콜백을 실행합니다. |
| 렌더러, GPU, 유틸리티 프로세스 | `cefsubprocess` 실행 파일 | `main`이 `CefExecuteProcess`를 호출해 CEF가 정한 역할을 수행합니다. |

`CefWrapper::InitCefSimple()`(`native/cefwrapper/library.cpp`)가 `CefSettings.browser_subprocess_path`를 서브프로세스 실행 파일로 지정합니다. 기본값은 Linux에서 확장 모듈과 같은 디렉터리의 `cefsubprocess`이고, Windows에서는 현재 작업 디렉터리의 `cefsubprocess/cefsubprocess.exe`입니다. `CefApp.set_subprocess_path()`로 바꿀 수 있습니다.

서브프로세스는 Python 없이 C++만 실행합니다. 그래서 JavaScript 호출 처리 중 렌더러에서 실행되는 코드(`cef_wrapper_render_process_handler.cc`)는 Python 객체에 접근하지 못하고, 이름만 가지고 브라우저 프로세스로 메시지를 보냅니다([JavaScript 바인딩](javascript-bindings.md)).

샌드박스는 쓰지 않습니다(`settings.no_sandbox = true`). 그래서 CEF 배포본의 `chrome-sandbox`는 스테이징에서 제외합니다([런타임 파일 배치](runtime-layout.md)).

## UI 스레드는 Python 스레드

`library.cpp`에서 `settings.multi_threaded_message_loop = true`는 주석 처리되어 있습니다. 즉 **외부 메시지 펌프** 방식이고, `CefInitialize()`를 호출한 스레드가 CEF의 UI 스레드가 됩니다. 사용자는 그 스레드에서 `CefApp.do_message_loop_work()`를 반복 호출해야 하고, UI 스레드에서 실행되는 모든 콜백(JavaScript 바인딩, 클라이언트 핸들러)은 이 호출 안에서 실행됩니다. 시험에서 바인딩 콜백과, 표시, 수명 주기, 로드 핸들러 콜백이 모두 `initialize()`를 부른 스레드에서 실행되는 것을 확인했습니다(바인딩 콜백은 스레드 이름이 `MainThread`로 찍혔습니다. [실험으로 확인한 사실](../reference/verified-findings.md)).

## 다른 스레드의 콜백

CEF에는 UI 스레드 말고도 IO 스레드 등이 있습니다. 예를 들어 CEF 헤더(`cef_scheme.h`)는 `CefSchemeHandlerFactory`의 메서드가 항상 IO 스레드에서 호출된다고 적고, `CefResourceHandler`도 따로 명시하지 않으면 IO 스레드라고 적습니다. 따라서 생성된 핸들러 콜백은 UI 스레드가 아닌 스레드에서 Python을 실행할 수 있습니다. 시험에서 실제 스레드 이름을 찍어 확인한 것은 UI 스레드 콜백뿐이고, IO 스레드 호출은 헤더 문서에 근거한 서술입니다.

## GIL 규칙

| 방향 | 규칙 | 구현 |
| --- | --- | --- |
| Python에서 CEF를 호출 | GIL을 놓고 호출합니다. | 손으로 쓴 `initialize`, `do_message_loop_work`, `shutdown`, `load_url`, `execute_javascript`와 모든 생성 래퍼 메서드가 `with nogil:`을 씁니다. |
| CEF가 Python을 호출 | 콜백은 GIL을 다시 얻습니다. | 콜백 함수는 `noexcept with gil`로 선언되고 예외를 `sys.excepthook`으로 보고하며 C++로 전파하지 않습니다. |

GIL을 쥔 채 CEF 안에서 기다리면 다른 CEF 스레드가 콜백을 위해 GIL을 기다리다 교착할 수 있기 때문에 앞의 규칙이 필요합니다. 규칙이 코드에 적용되어 있는지는 확인했습니다. Cython이 만든 C++ 코드에서 `PyEval_SaveThread`가 호출 위치마다 있고, 콜백에는 `PyGILState_Ensure`가 있습니다. 반대로 GIL을 놓지 않았을 때 실제로 교착하는지는 재현하지 못했습니다. 별도 Python 스레드가 GIL을 계속 쓰는 상태에서 `shutdown()`이 0.05초에 끝나는 것은 확인했지만, 이 시험은 GIL 해제 누락을 구별할 만큼 엄밀하지 않습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

`CefFrame`의 메서드는 브라우저 프로세스에서 어느 스레드에서든 호출할 수 있다고 CEF 헤더(`cef_frame.h`)가 밝히므로, 다른 Python 스레드에서 `load_url`을 불러도 UI 스레드 규칙을 어기지 않습니다. 다만 래퍼가 내부에서 쓰는 `Browser` 전역 참조 자체는 동기화되어 있지 않습니다.

## 관련 페이지

- [수명 주기와 메시지 루프](lifecycle-and-message-loop.md)
- [핸들러 프록시 구조](handler-proxies.md)
- [C++ 핸들러](../components/native-handlers.md)
- [cefsubprocess 실행 파일](../components/native-cefsubprocess.md)
