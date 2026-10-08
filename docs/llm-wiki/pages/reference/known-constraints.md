---
title: 알려진 제약과 미검증 항목
type: reference
sources:
  - README.rst
  - pyproject.toml
  - native/cefwrapper/library.cpp
  - native/cefwrapper/CMakeLists.txt
  - tools/build_cef.py
  - CLAUDE.md
updated: 2026-10-08
---

# 알려진 제약과 미검증 항목

원본을 끝까지 추적해도 근거를 얻을 수 없거나, 이 개발 환경에서 확인할 수 없었던 항목을 모읍니다. 항목마다 이유와 확인 방법을 적습니다. 해결되면 이 페이지에서 지우고 log.md에 기록합니다.

## 1. 확인하지 못한 것

| 항목 | 이유 | 확인 방법 |
| --- | --- | --- |
| **Windows**에서의 빌드와 동작 | 개발 환경이 Linux입니다. `OS_WIN` 분기, `cef_wrapper_client_handler_win.cc`, Windows용 CMake, `os.add_dll_directory`, `custom_protocol_scheme_handler.cc`의 수정이 양쪽에 영향을 줍니다. `pyproject.toml`의 `ext-modules`는 Linux 전용입니다. | Windows에서 `python tools/prepare.py`와 `uv build --wheel` 후 시험 실행. 설정 방식(정적 `ext-modules`로 충분한지)도 그때 정합니다. |
| `--build-cef`의 **실제 소스 빌드** | 이 환경의 디스크 여유가 약 69GB이고 요구량은 약 120GB입니다. `--dry-run`, 옵션 존재, 브랜치와 커밋 검증, 안전장치, 기존 배포본 재사용(가짜 디렉터리)까지만 확인했습니다. | 디스크 150GB 이상의 환경에서 `python tools/prepare.py --build-cef`. 결과 경로 탐색(`find_distribution`)과 `GN_DEFINES`를 그때 보정합니다. |
| **다른 CEF 버전의 헤더로 생성기 실행** | 154 배포본의 헤더에서만 실행했습니다. 파서는 CEF master(2026-09-29)의 복사본입니다. | 다른 버전 배포본으로 `python tools/gen/generate.py --cef-root <경로>` 실행 후 `tests/test_generator.py` |
| `GN_DEFINES`의 **`use_allocator=none`** 필요 여부 | cefpython이 같은 설정을 썼다는 근거만 있고 CEF 154에서 필요한지는 확인하지 않았습니다. | 소스 빌드 후 설정을 빼고 Python에서 CEF를 로드해 문제가 없는지 비교 |
| GIL을 놓지 않았을 때 **실제로 교착하는지** | 재현하지 않았습니다. 규칙의 적용 여부만 생성된 C++ 코드로 확인했고, `shutdown()`이 별도 스레드가 GIL을 쓰는 중에도 0.05초에 끝나는 것은 확인했습니다. | `with nogil` 없이 만든 변형 빌드로 콜백이 있는 상태에서 `shutdown()` 호출 |
| IO 스레드에서의 핸들러 호출 | CEF 헤더가 IO 스레드라고 밝히지만, 시험에서 스레드 이름을 찍어 확인한 것은 UI 스레드 콜백뿐입니다. | 핸들러 콜백 안에서 `threading.current_thread().name`을 찍어 확인 |
| `shutdown()` 뒤 **재초기화** | CEF가 프로세스당 한 번만 초기화할 수 있다고 알려져 있어서 시도하지 않았습니다. | 같은 프로세스에서 두 번째 `CefApp().initialize()` |
| `initialize()` 없이 프로세스가 끝날 때의 프록시 해제 | 인터프리터 종료 뒤에 CEF 스레드가 Python 객체를 해제할 수 있는지 시험하지 않았습니다. | `shutdown()` 없이 종료하는 스크립트 |
| 등록하지 않은 URL의 동작 | `create()`가 `None`이면 CEF 기본 처리로 넘어간다고 헤더가 설명하지만 실제 네트워크 동작은 시험하지 않았습니다. | 등록한 호스트의 다른 경로를 열어 보기 |
| **manylinux** wheel | wheel 태그가 `linux_x86_64`입니다. PyPI 배포에는 `auditwheel`이 필요합니다. | `auditwheel show`/`repair` |
| macOS | 지원하지 않기로 했고 구성 단계에서 중단합니다. 필요한 작업은 [플랫폼 지원 현황](../concepts/platform-support.md)에 있습니다. | |
| 서브프로세스 종료 오류의 **원인 메커니즘** | `main`에 `no_stack_protector`를 붙이면 사라지고 순정 `main`에는 검사 자체가 없다는 것만 확인했습니다. "zygote 자식이 스택 보호값이 다른 채 이 프레임으로 돌아온다"는 코드 주석의 설명은 추정입니다. | Chromium의 `ForkWithFlags`/zygote 코드와 TLS의 스택 보호값 처리를 확인 |
| 핸들러의 **구조체 출력**(`get_root_window_screen_rect`)이 Python에서 | 구조체 입력은 `on_auto_resize`로 Python까지 확인했습니다. 출력은 C++ 프록시를 실행해 확인했고 Cython은 컴파일되지만, CEF가 이 메서드를 오프스크린 렌더링에서만 불러서 Python 핸들러까지의 경로를 실행하지 못했습니다. | 오프스크린 렌더링(`CefWindowInfo`의 windowless 설정)으로 브라우저를 만들어 확인 |
| `BrowserHost`의 마우스 좌표가 보낸 값과 **같지 않은 이유** | `send_mouse_click_event`로 (50, 60)을 보내면 페이지에는 (41, 50)으로 도착했습니다(오프셋 -9, -10). 두 클릭 사이의 거리는 정확히 보존되어 시험은 그것만 확인합니다. 오프셋의 원인(창 장식, 뷰의 위치 등)은 조사하지 않았습니다. | 창 정보를 바꿔 가며 오프셋 비교 |
| 클라이언트 핸들러 변경의 **Windows** 컴파일 | 생성된 전달 클래스와 `CefWrapperClientHandler` 변경은 Linux에서만 컴파일했습니다. | Windows에서 빌드 |
| 헤더 주석의 한국어 번역 | `cef_origin` 위키에는 1,348개 메서드의 한국어 설명이 있으나 생성 스텁에는 헤더의 영어 주석을 그대로 씁니다. | 생성기가 위키의 `db/ko/*.json`을 읽도록 확장 |

## 2. 알려진 한계

- **CEF는 프로세스당 하나**이고 사용자 스레드가 UI 스레드입니다([프로세스 모델과 스레드](../concepts/process-model-and-threads.md)). `do_message_loop_work()`를 호출하지 않으면 아무것도 처리되지 않습니다.
- **`do_close`는 호출되지 않습니다.** 래퍼의 브라우저는 Chrome 스타일이라 CEF가 `DoClose`를 부르지 않습니다(F17). 닫기를 막는 용도로 쓸 수 없고, 래퍼의 `DoClose` 코드(`is_closing_`)도 실행되지 않습니다. Alloy 스타일로 바꾸면 달라집니다.
- **Python에 열린 핸들러는 일부**입니다. 표시, 수명 주기, 로드 핸들러는 `set_client()`로 받을 수 있지만, 컨텍스트 메뉴 핸들러와 JavaScript 바인딩 메시지(`OnProcessMessageReceived`)는 `CefWrapperClientHandler`가 고정해서 처리하고 위임하지 않습니다. 나머지 핸들러 15개는 생성 범위 밖입니다([생성 범위와 커버리지](generated-api-coverage.md)).
- `set_client()`의 전달 대상(`forward_..._handler_`)은 CEF가 `Get...Handler()`를 부를 때마다 잠금 없이 바뀝니다. 이벤트와 getter가 한 스레드(UI 스레드)에서 오는 동안에는 안전하지만, CEF 헤더가 스레드를 밝힌 것은 표시와 수명 주기 핸들러뿐이고 getter가 어느 스레드에서 불리는지는 확인하지 않았습니다.
- 사용자의 `get_load_handler()` 같은 getter는 **이벤트마다** Python에서 실행될 수 있습니다. 비용은 측정하지 않았습니다.
- **리눅스에서 창 제목을 설정하지 않습니다**(`PlatformTitleChange`가 비어 있음).
- **JS 값은 네 종류만**(정수, 불리언, 실수, 문자열) 전달되고 반환값은 없습니다. 인자 없는 C++ 바인딩 경로는 Python에 노출하지 않았습니다.
- `Browser` 전역 참조(`CefWrapperBrowserProcessHandler::Browser`)와 `g_IsRunning`은 동기화되어 있지 않습니다. 다른 Python 스레드에서 `load_url`/`execute_javascript`를 부를 수는 있지만(CEF 쪽 `CefFrame`은 어느 스레드든 가능) 이 전역을 보호하지는 않습니다.
- `CefWrapper::IsReadyToExecuteJavascript()`는 `CefWrapperClientHandler::GetInstance()`의 널을 확인하지 않습니다. Python 래퍼가 상태로 먼저 거릅니다.
- `resources_dir_path` 설정은 Linux에서 `icudtl.dat` 위치에 영향이 없습니다. 런타임 파일은 `libcef.so`와 같은 디렉터리여야 합니다([런타임 파일 배치](../concepts/runtime-layout.md)).
- 생성기는 벡터, 맵, 소유 포인터, 평범한 데이터가 아닌 구조체, 라이브러리 메서드의 출력 인자, 핸들러 메서드의 구조체 반환, 라이브러리 클래스의 상속을 지원하지 않습니다([생성 범위와 커버리지](generated-api-coverage.md)).
- `ext-modules` 설정이 Linux 전용이고 정적이라서 플랫폼별로 나눌 수 없습니다.
- `tools/prepare.py`의 스테이징은 Linux만 구현했습니다.
- 소스 빌드(`build_cef.py`)는 Linux x86_64만 지원하고 cefpython처럼 CEF에 자체 패치를 적용하지 않습니다.
- sdist만으로는 wheel을 만들 수 없고, 인자 없는 `uv build`는 실패합니다.

## 3. 문서와 메타데이터의 불일치

| 위치 | 불일치 | 상태 |
| --- | --- | --- |
| `README.rst` 소개 문단 | 여러 GUI 툴킷(wxPython, PyQt, PySide, Kivy 등)의 예제가 있다고 쓰지만 저장소에 예제가 없습니다. cefpython의 README 문장을 바탕으로 한 것으로 보입니다. | 그대로 둠. 사람의 결정이 필요합니다. |
| `pyproject.toml` | `numpy>=1.26.2`가 의존성에 있으나 코드에서 쓰지 않습니다. classifier에 macOS와 Windows가 있으나 지원하지 않거나 검증하지 못했습니다. classifier는 Python 3.11과 3.12만 적고 시험은 3.11~3.14에서 했습니다. | 그대로 둠 |
| `docs/` | Sphinx 골격만 있고 본문이 없습니다. `CHANGELOG.rst`는 비어 있습니다. | 그대로 둠 |
| `README.rst`의 `cefsubprocess/` 디렉터리 | 서브프로세스를 패키지 디렉터리 바로 아래 실행 파일로 옮긴 뒤에도 "디렉터리"라고 적혀 있었습니다. | 2026-10-08에 고침 |
| `_cefweaver.pyx`의 `load_url` docstring | "브라우저는 첫 `do_message_loop_work()` 호출들에서 만들어진다"고 했으나 `initialize()` 직후에 이미 `True`였습니다. | 2026-10-08에 고침 |
| `CLAUDE.md`와 `tests/test_smoke.py`의 시험 명령 | `-P` 없이 저장소 루트에서 실행하면 CEF 시험(당시 11개)이 조용히 건너뛰어졌습니다. | 2026-10-08에 고침 |
| `native/` 주석 | 원래 개발자의 경로(`C:\Dev\cef-binaries\...`), `ZenDraft` 경로가 남아 있습니다. | [사용하지 않는 코드와 유산](../components/legacy-code.md) |

## 4. 환경 제약

- 개발 PC는 Linux 6.17, Wayland 세션(`WAYLAND_DISPLAY=wayland-0`)에 XWayland(`DISPLAY=:0`)가 함께 있습니다. 시험은 Wayland를 끄고 Xvfb에서만 실행합니다.
- 디스크 여유가 부족하고(약 69GB) gdb가 멀티 프로세스 추적 중 스스로 종료합니다([충돌 조사 방법](../procedures/debug-crashes.md)).
- 헤드리스 Wayland 컴파지터(weston, cage, sway)가 없어서 네이티브 Wayland를 실제 화면을 건드리지 않고는 시험할 수 없습니다([Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)).

## 관련 페이지

- [실험으로 확인한 사실](verified-findings.md)
- [설계 결정 기록](design-decisions.md)
- [README와 CLAUDE.md 요약](../summaries/readme-and-claude-md.md)
