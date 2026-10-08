---
title: 플랫폼 지원 현황
type: concept
sources:
  - README.rst
  - CMakeLists.txt
  - pyproject.toml
  - tools/prepare.py
  - native/cefwrapper/CMakeLists.txt
  - native/cefsubprocess/CMakeLists.txt
  - tests/test_smoke.py
updated: 2026-10-08
---

# 플랫폼 지원 현황

| 플랫폼 | 상태 | 근거 |
| --- | --- | --- |
| Linux x86_64 | 빌드, 구동, 시험을 마쳤습니다. | Python 3.11, 3.12, 3.13, 3.14에서 통합과 생성기 시험 24개 통과(위키 점검 시험은 3.13에서만 실행) |
| Windows | 코드 경로와 CMake 타깃이 있으나 **검증하지 못했습니다.** | 이 저장소의 개발 환경이 Linux입니다. |
| macOS | **지원하지 않습니다.** | `CMakeLists.txt`가 구성 단계에서 `FATAL_ERROR`로 중단합니다. |
| ARM, 32비트 | 대상이 아닙니다. | `build_cef.py`는 x86_64 호스트만 허용하고, `pyproject.toml`의 확장 설정이 Linux x86_64 기준입니다. |

## Linux

`pyproject.toml`의 `ext-modules` 설정(라이브러리 이름, 디렉터리, `-Wl,-rpath,$ORIGIN`, `-std=c++20`)은 Linux 전용입니다. 정적 설정 파일이라 플랫폼별로 나눌 수 없어서 Windows 지원을 시작하면 설정 방식을 다시 정해야 합니다([설계 결정 기록](../reference/design-decisions.md)).

화면 환경은 [Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)에 있습니다. 요약하면 네이티브 Wayland와 XWayland(X11)에서 모두 Chromium이 동작했습니다. 시험은 실제 화면에 창이 뜨지 않도록 환경변수 `WAYLAND_DISPLAY`를 제거하고 `ozone-platform=x11`을 지정해서 가상 X 서버(Xvfb)에서만 실행합니다.

## Windows

Windows용 코드는 이전 작업에서 남아 있습니다. `OS_WIN` 분기(`SetAsPopup`, `CefEnableHighDPISupport`, `GetCommandLineW`), `cef_wrapper_client_handler_win.cc`(`SetWindowText`로 창 제목 변경), `native/cefwrapper/CMakeLists.txt`와 `native/cefsubprocess/CMakeLists.txt`의 `OS_WINDOWS` 분기, `wWinMain` 서브프로세스입니다. 이 코드는 이번에 Linux 지원을 추가하면서 `#if`로 감싸는 정도만 고쳤고 Windows에서 빌드해 보지 않았습니다. `custom_protocol_scheme_handler.cc`의 수정(`int64`를 `int64_t`로, `starts_with`를 `rfind`로)은 양쪽에 영향을 주므로 Windows에서도 확인이 필요합니다. `cefweaver/__init__.py`의 `os.add_dll_directory` 분기도 시험하지 못했습니다.

## macOS

macOS는 `libcef`를 링크하지 않고 `Chromium Embedded Framework.framework`를 실행 중에 로드해야 하고, 서브프로세스가 단일 실행 파일이 아니라 여러 helper 앱 번들이어야 하며, 브라우저 프로세스가 `NSApplication`과 `CefAppProtocol`을 구현해야 합니다. Python 프로세스가 호스트인 이 구조에서 `CefDoMessageLoopWork()`와 Cocoa 이벤트 루프를 결합하는 설계가 가장 어렵습니다. 이 항목은 java-cef와 CEF의 문서를 바탕으로 한 분석이며 구현하거나 시험해 본 것이 아닙니다. 기존 CMake의 `OS_MAC` 분기는 상위에서 중단되어 도달하지 않습니다.

## 문서와 메타데이터의 불일치

`pyproject.toml`의 classifier는 macOS와 Windows를 포함하고, `README.rst`는 여러 GUI 툴킷(wxPython, PyQt 등)의 예제가 있다고 쓰지만 저장소에는 예제가 없습니다. 실제 상태는 이 페이지를 따릅니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)
- [런타임 파일 배치](runtime-layout.md)
- [C++ 핸들러](../components/native-handlers.md)
