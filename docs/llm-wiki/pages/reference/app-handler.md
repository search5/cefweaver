---
title: 앱 핸들러 (명령줄, 스킴, 시작 훅)
type: reference
sources:
  - native/cefwrapper/app_hooks.h
  - native/cefwrapper/app_hooks.cc
  - native/cefwrapper/cef_wrapper_app.cc
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/_cefweaver.pyx
  - tests/test_smoke.py
updated: 2026-10-08
---

# 앱 핸들러 (명령줄, 스킴, 시작 훅)

java-cef의 `CefAppHandler`에 해당합니다. CEF를 시작하는 순간의 훅을 Python 객체로 받습니다.

```python
class Hooks(cefweaver.AppHandler):
    def on_before_command_line_processing(self, process_type, command_line):
        command_line.append_switch("disable-gpu")              # CommandLine
    def on_register_custom_schemes(self, registrar):
        registrar.add_custom_scheme("myapp", types.SchemeOptions.STANDARD | types.SchemeOptions.SECURE)
    def on_context_initialized(self):
        ...                                                     # 첫 브라우저 직전
    def on_already_running_app_relaunch(self, command_line, current_directory):
        return True                                             # 처리함: 새 창을 열지 않음

app.set_app_handler(Hooks())                                    # initialize() 전에만
```

| 훅 | 동작 |
| --- | --- |
| `on_before_command_line_processing(process_type, command_line)` | 브라우저 프로세스에서만 불립니다(`process_type`은 `""`, java-cef와 같음). `add_command_line_switch`의 스위치보다 먼저 불려서 거기서 바꾼 것 위에 래퍼의 스위치가 붙습니다. `command_line`은 `CommandLine` 객체입니다. |
| `on_register_custom_schemes(registrar)` | `SchemeRegistrar.add_custom_scheme(name, options)`는 이 호출 안에서만 유효합니다(그 뒤에는 `RuntimeError`). 등록한 스킴은 기억해 두었다가 자식 프로세스(렌더러)의 명령줄에 `cefweaver-custom-schemes=이름:옵션;...`으로 붙이고(`OnBeforeChildProcessLaunch`), 렌더러의 `OnRegisterCustomSchemes`가 그것으로 같은 스킴을 등록합니다. java-cef는 임시 파일로 같은 일을 합니다. |
| `on_context_initialized()` | 첫 브라우저를 만들기 직전에 불립니다. |
| `on_already_running_app_relaunch(command_line, current_directory)` | 같은 사용자 데이터(`cache_path`)로 두 번째 프로세스를 시작하면 첫 프로세스에 두 번째의 명령줄이 옵니다. `True`면 처리한 것입니다. |

`CommandLine`(생성된 클래스)의 메서드는 `append_switch`, `append_switch_with_value`, `append_argument`, `get_switches`(`dict`), `get_arguments`, `get_program`/`set_program`, `has_switch`, `get_switch_value`, `has_switches`, `has_arguments`, `reset`입니다. `get_global_command_line()`으로 이 프로세스의 명령줄을 읽을 수 있습니다.

## java-cef와 다른 점, 하지 않은 것

- java-cef의 `onScheduleMessagePumpWork`(외부 메시지 펌프), `onBeforeTerminate`, `stateHasChanged`는 없습니다. 우리는 호출하는 쪽이 `do_message_loop_work()`를 부르는 구조이고(CEF의 `external_message_pump`를 켜지 않음) 종료 상태는 `shutdown()`이 다룹니다.
- 모든 훅은 `initialize()`를 부른 스레드에서 불립니다.

## 제약

- `CommandLine.init_from_string`은 Windows의 명령줄 문법을 읽는 메서드라 Linux에서는 아무것도 하지 못합니다(CEF의 동작). `init_from_argv`는 포인터 배열이라 열지 않았습니다(java-cef도 열지 않음). Linux에서는 `set_program`과 `append_*`로 만듭니다.
- 사용자 스킴을 쓰려면 `register_scheme_handler_factory(스킴, 도메인, 팩토리)`도 해야 페이지가 뜹니다(시험에서 확인).

## 관련 페이지

- [Python API 참조](python-api.md)
- [java-cef 동등성](java-cef-parity.md)
- [실험으로 확인한 사실 (F36부터)](verified-findings-more.md)
