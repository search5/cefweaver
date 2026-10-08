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
| 핸들러의 **구조체 출력**이 Python에서 | **확인했습니다**(F38): 오프스크린의 `get_view_rect`가 돌려준 `Rect`로 CEF가 200x100, 320x240 프레임을 그렸습니다. `get_root_screen_rect`와 `get_screen_point`는 부르지 않아 따로 시험하지 않았습니다. | |
| 클라이언트 핸들러 변경의 **Windows** 컴파일 | 생성된 전달 클래스와 `CefWrapperClientHandler` 변경은 Linux에서만 컴파일했습니다. | Windows에서 빌드 |
| Chrome 스타일 변형 빌드에서 한 번 난 **세그멘테이션 오류** | `test_resource_handler_callbacks_run_on_threads_other_than_the_ui_thread`에서 종료 코드 -11이 한 번 났습니다(그 빌드는 Chrome 스타일 변형이었음). 정상(Alloy) 빌드에서 20번, 전체 시험 3번은 재현되지 않았습니다. | 같은 시험을 변형 빌드에서 반복 실행 |
| 네이티브 Wayland 크래시의 **원인**과 순수 Wayland 세션(`DISPLAY` 없음)의 방법 | 함수 이름을 보지 못했습니다(심볼 없음, 원본 `libcef`는 `gdb`가 못 읽음). `cefsimple`의 Alloy는 살아 있었으므로 래퍼의 실행 방식(외부 메시지 펌프 등)이 원인일 가능성이 있습니다. | 심볼이 있는 CEF 빌드 또는 래퍼를 `CefRunMessageLoop`으로 바꿔 비교 |
| F27이 **이전 CEF 버전**에서도 나는지 | 152의 `cefsimple`로 확인하려 했으나 원격 디버깅 포트가 열리지 않아 중단했습니다. | 152 표준 배포본으로 `cefsimple` 또는 cefweaver를 빌드해 `data:` + `srcdoc` 페이지 시험 |
| **Chrome 스타일 선택 옵션**을 열 때의 위험(옵션은 아직 없고 Alloy만 지원) | (1) 래퍼의 컨텍스트 메뉴 항목("Show DevTools" 등)은 Alloy에서만 시험했습니다(Chrome 스타일의 메뉴는 Chrome UI가 다룸). (2) Chrome 스타일과 외부 메시지 펌프와 부모 창 지정의 조합은 다룬 적이 없습니다. (3) Chrome 스타일은 오프스크린 렌더링을 지원하지 않아서, 오프스크린 옵션을 열 때 조합을 막는 검사가 필요합니다. 수정 범위는 작습니다: 옵션 전달 약 20줄, 스타일 분기 2곳(창 제목과 로드 오류 페이지를 지금은 쓰이지 않는 명령줄 스위치 `enable-chrome-runtime`으로 판단하므로 `GetRuntimeStyle()`로 바꿔야 함), 시험 몇 개. | 선택 옵션을 열 때 두 스타일에서 확인 |
| **구조체 참조가 입출력이라는 판단**의 일반성 | 헤더는 참조 인자의 방향(출력인지 입출력인지)을 표시하지 않습니다. 구조체는 입출력, 그 밖은 출력 전용으로 정한 근거는 `CefDisplay`와 `CefView`의 좌표 변환(입출력, 시험으로 확인)과 `CefMenuModel`, `CefImage`의 기본형 출력(출력 전용)입니다. 구조체를 순수 출력으로 쓰는 `CefTranslatorTest::GetPointByRef`는 범위 밖이라 확인하지 못했습니다(그런 메서드는 호출할 때 아무 구조체나 넘겨야 함). | 범위에 넣고 호출해 보기 |
| `shutdown()` 뒤에 해제되는 라이브러리 객체를 **버리는 방식**의 이식성 | 종료 뒤에 해제되는 라이브러리 객체는 `CefRefPtr`의 포인터를 `NULL`로 만들어 `Release()`를 건너뜁니다. `CefRefPtr`가 포인터 하나로 이루어져 있다는 가정에 기댑니다(CEF의 `scoped_refptr`는 그렇습니다). 객체는 새지만 프로세스가 끝나는 중입니다. 원인(`TaskManager`가 종료된 CEF에서 `Release()`되면 SIGTRAP)은 `libcef` 안이라 조사하지 못했습니다. | CEF 버전을 바꾸고 시험 |
| 헤더 주석의 한국어 번역 | `cef_origin` 위키에는 1,348개 메서드의 한국어 설명이 있으나 생성 스텁에는 헤더의 영어 주석을 그대로 씁니다. | 생성기가 위키의 `db/ko/*.json`을 읽도록 확장 |

## 2. 알려진 한계

- **요청 핸들러의 `on_certificate_error`, `on_render_process_terminated`, `on_open_url_from_tab`와 리소스 요청 핸들러의 `on_protocol_execution`은 실행해 보지 못했습니다**(TLS 서버, 렌더러 종료 등이 필요). `get_auth_credentials`, `on_resource_redirect`, `on_resource_response`는 로컬 HTTP 서버로 확인했습니다(F52). 쿠키 접근 필터(`CefCookieAccessFilter`)와 응답 필터는 생성되지 않습니다. `CefRequestContextHandler`는 `CefRequestContext`가 범위 밖이라 없습니다.

- **인쇄 핸들러의 `on_print_dialog`, `on_print_job`, `get_pdf_paper_size`는 실행해 보지 못했습니다**(프린터가 없는 환경, F42). 생성과 컴파일만 확인했습니다.

- **오프스크린 렌더링에는 `start_dragging`, GPU 가속 페인트, 팝업 그리기가 없습니다.** 시험하지 않은 것: 렌더 핸들러가 없을 때, `PaintElementType.POPUP`, 영문 한 글자 밖의 키 입력, 터치와 IME의 결과. 자세한 것은 [오프스크린 렌더링](offscreen-rendering.md).

- **`add_command_line_switch`의 스위치는 자식 프로세스에 전달되지 않습니다**(F36). 렌더러나 GPU 프로세스가 읽는 스위치(예: 렌더러 쪽 기능을 켜는 것)는 지금 줄 방법이 없습니다. 자식에게도 보내는 옵션은 만들지 않기로 했습니다(java-cef도 같은 한계, F36).
- **교차 사이트 iframe이 로드되지 않았습니다**(F37). 원인을 조사하지 않았고, 사이트 격리로 프로세스가 갈리는 프레임에서의 메시지 라우터는 확인하지 못했습니다.

- **CEF는 프로세스당 하나**이고 사용자 스레드가 UI 스레드입니다([프로세스 모델과 스레드](../concepts/process-model-and-threads.md)). `do_message_loop_work()`를 호출하지 않으면 아무것도 처리되지 않습니다.
- **Python은 브라우저 프로세스에만 있어서 렌더러 쪽 동작을 정할 수 없습니다.** 프로세스 메시지로 받을 수 있는 것은 렌더러의 C++ 코드가 보내는 메시지뿐이고, 지금은 진단용 `cefweaver-pong`(`cefweaver-ping`에 대한 답)이 전부입니다. JavaScript와의 통신은 `add_javascript_binding`(기본형 인자, 반환값 없음)과 java-cef와 같은 메시지 라우터(`window.cefQuery`, 문자열 또는 바이트 요청과 비동기 응답)입니다([메시지 라우터](message-router.md)). 페이지에 `cefQuery`가 생기려면 첫 질의 핸들러를 `initialize()` 전에 더해야 합니다. cefpython처럼 JavaScript 콜백과 Python 콜백을 인자로 주고받는 일은 하지 않습니다([분석](../analyses/js-python-messaging.md)).
- `BinaryValue.get_raw_data`(CEF 메모리를 가리키는 포인터)와 `ProcessMessage.get_shared_memory_region`(범위 밖 클래스)은 열지 않았습니다. `create`와 `get_data`는 `bytes`로 열렸습니다(`get_data`가 복사하므로 `get_raw_data`는 필요 없다고 보았음). 값 컨테이너는 CEF의 메서드를 그대로 중계하며 파이썬 객체(`dict`, `list`)와의 변환 함수는 없습니다. 열지 못한 항목의 사정과 방법은 [분석](../analyses/js-python-messaging.md)에 있습니다.
- **네이티브 Wayland에서 Alloy 스타일 브라우저가 죽습니다**(`ozone-platform=wayland`, 크래시 지점은 `libcef` 안, F31). 그래서 `DISPLAY`가 있으면 `x11`(XWayland)이 기본입니다. `DISPLAY`가 없는 순수 Wayland 세션은 해결책이 없고(Chromium이 Wayland를 고르면 죽음), `cefsimple`의 Alloy 스타일은 같은 `libcef`에서 살아 있어서 래퍼 쪽 원인일 수 있으나 찾지 못했습니다. GUI 툴킷에 끼워 넣는 일(`parent_window`)은 X11 핸들이라 Wayland에서 어차피 어렵습니다.
- **CEF 154.0.34의 문제: `data:`나 `about:blank` 페이지의 `<iframe srcdoc>`가 로드를 끝내지 못합니다**(F27). cefweaver의 문제가 아니며(`cefsimple`도 같음) 고칠 수 없습니다. `add_resource`로 페이지를 제공하거나 `src` iframe을 쓰는 우회가 있고, `expectedFailure` 시험이 CEF의 수정을 알려 줍니다.
- **준비되기 전의 입력은 버려집니다**(`send_mouse_*`, F18). 대기열에 쌓이지 않고 준비를 알리는 신호도 없습니다(첫 프레임 뒤에도 10번 중 1번은 버려졌음). 호출하는 쪽이 도착할 때까지 다시 보내야 합니다.
- **Python에 열린 핸들러는 일부**입니다. 로드, 수명 주기, 표시, 드래그, 컨텍스트 메뉴 핸들러와 프로세스 메시지는 `set_client()`로 받을 수 있습니다. 나머지 핸들러 13개는 생성 범위 밖입니다([생성 범위와 커버리지](generated-api-coverage.md)).
- `set_client()`의 전달 대상(`forward_..._handler_`)은 CEF가 `Get...Handler()`를 부를 때마다 잠금 없이 바뀝니다. 이벤트와 getter가 한 스레드(UI 스레드)에서 오는 동안에는 안전하지만, CEF 헤더가 스레드를 밝힌 것은 표시와 수명 주기 핸들러뿐이고 getter가 어느 스레드에서 불리는지는 확인하지 않았습니다.
- 사용자의 `get_load_handler()` 같은 getter는 **이벤트마다** Python에서 실행될 수 있습니다. 비용은 측정하지 않았습니다.
- **JS 값은 네 종류만**(정수, 불리언, 실수, 문자열) 전달되고 반환값은 없습니다. 인자 없는 C++ 바인딩 경로는 Python에 노출하지 않았습니다.
- `Browser` 전역 참조(`CefWrapperBrowserProcessHandler::Browser`)와 `g_IsRunning`은 동기화되어 있지 않습니다. 다른 Python 스레드에서 `load_url`/`execute_javascript`를 부를 수는 있지만(CEF 쪽 `CefFrame`은 어느 스레드든 가능) 이 전역을 보호하지는 않습니다.
- `CefWrapper::IsReadyToExecuteJavascript()`는 `CefWrapperClientHandler::GetInstance()`의 널을 확인하지 않습니다. Python 래퍼가 상태로 먼저 거릅니다.
- `resources_dir_path` 설정은 Linux에서 `icudtl.dat` 위치에 영향이 없습니다. 런타임 파일은 `libcef.so`와 같은 디렉터리여야 합니다([런타임 파일 배치](../concepts/runtime-layout.md)).
- 생성기는 라이브러리 메서드의 객체 참조 출력 인자(`CefRefPtr<T>&`), 요소가 평범하지 않은 구조체이거나 `CefRawPtr`인 벡터, 라이브러리 메서드에 주는 객체 목록, 라이브러리 메서드에 주는 벡터, 맵, 소유 포인터, 평범한 데이터가 아닌 구조체, 라이브러리 메서드의 출력 인자, 핸들러 메서드의 구조체 반환, 라이브러리 클래스의 상속을 지원하지 않습니다([생성 범위와 커버리지](generated-api-coverage.md)).
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
