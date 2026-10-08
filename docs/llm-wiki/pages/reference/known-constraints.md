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
| 다른 CEF 버전의 **실행** | 생성기와 컴파일은 147, 152, 154 헤더에서 확인했습니다(F23). 147과 152의 `libcef`로 실제 실행해 시험을 돌리지는 않았습니다. | 해당 버전의 배포본으로 `prepare.py`, `uv build --wheel`, 시험 |
| `GN_DEFINES`의 **`use_allocator=none`** 필요 여부 | cefpython이 같은 설정을 썼다는 근거만 있고 CEF 154에서 필요한지는 확인하지 않았습니다. | 소스 빌드 후 설정을 빼고 Python에서 CEF를 로드해 문제가 없는지 비교 |
| **manylinux** wheel | `auditwheel show`가 `linux_x86_64`만 허용했습니다(F24). manylinux 이미지에서 빌드하고 CEF가 요구하는 시스템 라이브러리(NSS, D-Bus, ALSA, udev 등)를 어떻게 다룰지 정해야 합니다. | manylinux 컨테이너에서 빌드 후 `auditwheel show`/`repair` |
| macOS | 지원하지 않기로 했고 구성 단계에서 중단합니다. 필요한 작업은 [플랫폼 지원 현황](../concepts/platform-support.md)에 있습니다. | |
| 서브프로세스 종료 오류의 **원인 메커니즘** | `main`에 `no_stack_protector`를 붙이면 사라지고 순정 `main`에는 검사 자체가 없다는 것만 확인했습니다. "zygote 자식이 스택 보호값이 다른 채 이 프레임으로 돌아온다"는 코드 주석의 설명은 추정입니다. | Chromium의 `ForkWithFlags`/zygote 코드와 TLS의 스택 보호값 처리를 확인 |
| 핸들러의 **구조체 출력**(`get_root_window_screen_rect`)이 Python에서 | 구조체 입력은 `on_auto_resize`로 Python까지 확인했습니다. 출력은 C++ 프록시를 실행해 확인했고 Cython은 컴파일되지만, CEF가 이 메서드를 오프스크린 렌더링에서만 불러서 Python 핸들러까지의 경로를 실행하지 못했습니다. | 오프스크린 렌더링(`CefWindowInfo`의 windowless 설정)으로 브라우저를 만들어 확인 |
| 클라이언트 핸들러 변경의 **Windows** 컴파일 | 생성된 전달 클래스와 `CefWrapperClientHandler` 변경은 Linux에서만 컴파일했습니다. | Windows에서 빌드 |
| Alloy 스타일에서 **네이티브 Wayland** | 시험은 X11(`ozone-platform=x11`)로만 실행했고, Wayland 조사([Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md))는 Chrome 스타일 기준입니다. 실제 화면에 창을 여는 일이라 사용자의 허락 없이 실행하지 않았습니다. | Wayland 세션에서 `ozone-platform` 없이 실행해 창이 뜨는지 확인 |
| **Chrome 스타일 선택 옵션**을 열 때의 위험(옵션은 아직 없고 Alloy만 지원) | (1) 래퍼의 컨텍스트 메뉴 항목("Show DevTools" 등)이 Chrome 스타일에서 동작하는지 시험한 적이 없고, Python에서 메뉴를 열고 항목을 고르는 수단도 없습니다. (2) Chrome 스타일과 외부 메시지 펌프와 부모 창 지정의 조합은 다룬 적이 없습니다. (3) Chrome 스타일은 오프스크린 렌더링을 지원하지 않아서, 오프스크린 옵션을 열 때 조합을 막는 검사가 필요합니다. 수정 범위는 작습니다: 옵션 전달 약 20줄, 스타일 분기 2곳(창 제목과 로드 오류 페이지를 지금은 쓰이지 않는 명령줄 스위치 `enable-chrome-runtime`으로 판단하므로 `GetRuntimeStyle()`로 바꿔야 함), 시험 몇 개. | 선택 옵션을 열 때 두 스타일에서 확인 |
| 헤더 주석의 한국어 번역 | `cef_origin` 위키에는 1,348개 메서드의 한국어 설명이 있으나 생성 스텁에는 헤더의 영어 주석을 그대로 씁니다. | 생성기가 위키의 `db/ko/*.json`을 읽도록 확장 |

## 2. 알려진 한계

- **CEF는 프로세스당 하나**이고 사용자 스레드가 UI 스레드입니다([프로세스 모델과 스레드](../concepts/process-model-and-threads.md)). `do_message_loop_work()`를 호출하지 않으면 아무것도 처리되지 않습니다.
- **첫 프레임 전의 입력은 버려집니다**(`send_mouse_*`, F18). 대기열에 쌓이지 않으므로 호출하는 쪽이 첫 프레임 이후에 보내야 합니다.
- **Python에 열린 핸들러는 일부**입니다. 표시, 수명 주기, 로드 핸들러는 `set_client()`로 받을 수 있지만, 컨텍스트 메뉴 핸들러와 JavaScript 바인딩 메시지(`OnProcessMessageReceived`)는 `CefWrapperClientHandler`가 고정해서 처리하고 위임하지 않습니다. 나머지 핸들러 15개는 생성 범위 밖입니다([생성 범위와 커버리지](generated-api-coverage.md)).
- `set_client()`의 전달 대상(`forward_..._handler_`)은 CEF가 `Get...Handler()`를 부를 때마다 잠금 없이 바뀝니다. 이벤트와 getter가 한 스레드(UI 스레드)에서 오는 동안에는 안전하지만, CEF 헤더가 스레드를 밝힌 것은 표시와 수명 주기 핸들러뿐이고 getter가 어느 스레드에서 불리는지는 확인하지 않았습니다.
- 사용자의 `get_load_handler()` 같은 getter는 **이벤트마다** Python에서 실행될 수 있습니다. 비용은 측정하지 않았습니다.
- **JS 값은 네 종류만**(정수, 불리언, 실수, 문자열) 전달되고 반환값은 없습니다. 인자 없는 C++ 바인딩 경로는 Python에 노출하지 않았습니다.
- `Browser` 전역 참조(`CefWrapperBrowserProcessHandler::Browser`)와 `g_IsRunning`은 동기화되어 있지 않습니다. 다른 Python 스레드에서 `load_url`/`execute_javascript`를 부를 수는 있지만(CEF 쪽 `CefFrame`은 어느 스레드든 가능) 이 전역을 보호하지는 않습니다.
- `CefWrapper::IsReadyToExecuteJavascript()`는 `CefWrapperClientHandler::GetInstance()`의 널을 확인하지 않습니다. Python 래퍼가 상태로 먼저 거릅니다.
- `resources_dir_path` 설정은 Linux에서 `icudtl.dat` 위치에 영향이 없습니다. 런타임 파일은 `libcef.so`와 같은 디렉터리여야 합니다([런타임 파일 배치](../concepts/runtime-layout.md)).
- 생성기는 문자열이 아닌 요소의 벡터, 라이브러리 메서드에 주는 벡터, 맵, 소유 포인터, 평범한 데이터가 아닌 구조체, 라이브러리 메서드의 출력 인자, 핸들러 메서드의 구조체 반환, 라이브러리 클래스의 상속을 지원하지 않습니다([생성 범위와 커버리지](generated-api-coverage.md)).
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
