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
  - cmake/CefweaverExtension.cmake
  - native/cefwrapper/mac_runtime.mm
  - examples/cocoa/quickstart.py
  - cefweaver/ui/keys.py
  - cefweaver/ui/toolkits/pywin32.py
  - cefweaver/__init__.py
  - native/cefwrapper/library.cpp
  - native/cefsubprocess/cefsubprocess.cc
  - .gitattributes
updated: 2026-10-11
---

# 플랫폼 지원 현황

| 플랫폼 | 상태 | 근거 |
| --- | --- | --- |
| Linux x86_64 | 빌드, 구동, 시험을 마쳤습니다. | Python 3.11, 3.12, 3.13, 3.14에서 통합과 생성기 시험 통과(위키 점검 시험은 3.13에서만 실행). 시험 개수가 늘어난 지금 네 버전을 모두 다시 돌렸는지는 확인하지 못함 |
| Windows 11 x86_64 | 빌드, 구동, 시험, 동결을 마쳤습니다. 창 모드의 일부와 공유 텍스처 등은 확인하지 못했습니다. | [F116~F121](../reference/verified-findings-windows.md): wheel 빌드, 시험, `CHAR` 이벤트, pywin32 툴킷, 동결 |
| macOS arm64 (Apple Silicon) | 빌드, 구동, 시험의 대부분을 마쳤습니다. 공유 텍스처와 일부 동작은 다릅니다. | [F79~F83](../reference/verified-findings-macos.md): wheel 빌드, 오프스크린과 창 모드, Tk에서의 구동, 시험 |
| macOS x86_64 | Rosetta에서 빌드하고 구동했습니다(종료 감시 문제 있음). **실제 Intel Mac은 아닙니다.** | [F90](../reference/verified-findings-macos.md) |
| Linux ARM, 32비트 | 대상이 아닙니다. | `build_cef.py`는 x86_64 호스트만 허용합니다. |

## Linux

확장 모듈의 설정(`-Wl,-rpath,$ORIGIN`, `-std=c++20`, 프레임워크)은 `cmake/CefweaverExtension.cmake`에 있고 라이브러리 목록은 `cefwrapper` 타깃의 의존성이 정합니다([패키징](../components/packaging.md)). 2026-10-11에 `setup.py`에서 옮겼고 Linux와 macOS arm64에서 빌드하고 시험했습니다(macOS는 [F93](../reference/verified-findings-macos.md): 옮긴 뒤 wheel에 앱이 빠지고 태그가 틀린 것을 고침). Windows는 같은 CMake가 `OS_WINDOWS`에서 정합니다(아래).

화면 환경은 [Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)에 있습니다. 요약하면 네이티브 Wayland와 XWayland(X11)에서 모두 Chromium이 동작했습니다. 시험은 실제 화면에 창이 뜨지 않도록 환경변수 `WAYLAND_DISPLAY`를 제거하고 `ozone-platform=x11`을 지정해서 가상 X 서버(Xvfb)에서만 실행합니다.

## Windows

2026-10-11에 Windows 11(10.0.26200), Visual Studio Build Tools 2026(MSVC 14.50), CMake 4.4.4, Python 3.13.1, CEF 154.0.34(`windows64` prebuilt)에서 `uv build --wheel`로 wheel을 만들고(`cefweaver-0.1.0-cp313-cp313-win_amd64.whl`, 약 180MB) 시험했습니다([F116, F117](../reference/verified-findings-windows.md)). 이전에 남아 있던 Windows 코드는 그대로는 빌드되지 않았고 다음을 고쳤습니다.

- **샌드박스**: 래퍼가 `no_sandbox`를 쓰므로 루트 `CMakeLists.txt`가 Windows에서 `USE_SANDBOX`를 끕니다(`cef_sandbox.lib`는 링크하지 않음).
- **고DPI**: CEF 154 헤더에 `CefEnableHighDPISupport()`가 없어서 `library.cpp`와 `cefsubprocess.cc`에서 지웠습니다.
- **서브프로세스 경로**: 현재 작업 디렉터리 기준이던 것을 확장 모듈(`.pyd`)이 있는 디렉터리 기준(`ModuleDir()`, `GetModuleHandleExW`)으로 바꿨습니다. 경로는 UTF-8로 CEF에 넘깁니다(사용자 이름이 한글이어도 맞도록 `path::string()`을 쓰지 않음).
- **확장 모듈**: `NOMINMAX`와 `WIN32_LEAN_AND_MEAN`, 정적 런타임 `/MT`(CEF의 래퍼 라이브러리와 같음), `/utf-8`, `/bigobj`를 `cmake/CefweaverExtension.cmake`가 줍니다.
- **서브프로세스 실행 파일**: 매니페스트 두 개(`cefsubprocess.exe.manifest`, `compatibility.manifest`)를 CEF 예제에서 가져왔고, 저장소 밖으로 복사하던 옛 `COPY_FILES` 줄을 지웠습니다.
- **wheel 내용**: Linux와 같은 `install()`이 `cefsubprocess.exe`, `libcef.dll`과 DLL들, 리소스를 확장 모듈 옆에 넣습니다(`.lib`는 뺌).
- **DLL 적재**: `__init__.py`가 `libcef.dll`을 전체 경로로 미리 올립니다(`add_dll_directory`만으로는 지연 적재가 찾지 못합니다). py2exe처럼 패키지 디렉터리가 실제 디렉터리가 아닐 때는 건너뜁니다.
- **창 핸들 형**: 생성된 Cython 선언에서 `cef_window_handle_t`를 `unsigned long`(Windows에서 32비트)에서 `uintptr_t`로 바꿨습니다.

Windows의 `CHAR` 키 이벤트는 `windows_key_code`에 문자 코드를 요구합니다([F118](../reference/verified-findings-windows.md)). GUI는 `cefweaver.ui.toolkits.pywin32`(Win32 창, [F119](../reference/verified-findings-windows.md))가 있습니다. 확인하지 못한 것: 다른 프로그램의 창에 붙이는 창 모드(`SetAsChild`, `parent_view`는 macOS 전용), 공유 텍스처, 배율 100%가 아닌 화면, Python 3.13 외의 버전, Arm64, 실제 한글 입력기, GitHub Actions의 Windows 실행입니다([알려진 제약](../reference/known-constraints.md)).

## macOS

macOS는 `libcef`를 링크하지 않고 `Chromium Embedded Framework.framework`를 실행 중에 올립니다(`cef_load_library`). 서브프로세스는 단일 실행 파일이 아니라 도우미 앱 5개이고, 브라우저 프로세스는 Cocoa의 `NSApplication`이 `CefAppProtocol`을 구현해야 합니다. 구현은 다음과 같습니다.

- **프레임워크 로드**: `native/cefwrapper/mac_runtime.mm`의 `CefWeaverLoadRuntime()`이 확장 모듈을 가져올 때(`_cefweaver.pyx`의 맨 앞, 생성 코드의 첫 CEF 호출보다 앞) 프레임워크를 올립니다. 경로는 확장 모듈 옆의 `cefsubprocess.app`입니다.
- **가짜 메인 번들**: Python 프로세스에는 앱 번들이 없어서, `cefsubprocess.app`(Info.plist, `Contents/Frameworks/`의 프레임워크와 도우미 앱 5개)이 그 자리를 맡습니다. `CefSettings.main_bundle_path`와 `framework_dir_path`가 여기를 가리킵니다. 배치는 [런타임 파일 배치](runtime-layout.md)에 있습니다.
- **`NSApplication`**: `CefWeaverPrepareApplication()`이 `CefInitialize()` 전에 `NSApp`을 만들고(툴킷이 이미 만들었으면 그 클래스를 씀), 그 클래스에 `isHandlingSendEvent`, `setHandlingSendEvent:`와 `sendEvent:` 감싸기를 런타임에 더하고 프로토콜 세 개를 붙입니다. 서브클래스를 만들면 Qt나 Tk의 자체 클래스를 쓸 수 없기 때문입니다. Tk(자체 서브클래스), Qt, wx에서 동작하는 것을 확인했습니다. GTK는 시스템에 없어 시험하지 못했습니다.
- **메시지 루프**: 외부 메시지 펌프(`do_message_loop_work()`를 폴링)로 오프스크린과 창 모드가 동작했습니다. Cocoa 이벤트 루프와의 상호작용은 Tk에서만 확인했습니다.
- **같은 점**: 샌드박스를 쓰지 않습니다(`no_sandbox`).

- **네이티브 `NSView`에 붙이기**: `CefApp.parent_view`(NSView의 주소)를 주면 브라우저가 그 뷰의 자식 뷰(`SetAsChild`)로 만들어져 뷰를 채우고 크기를 따라갑니다. Cocoa나 SwiftUI의 `NSViewRepresentable`에 붙이는 쓰임을 위한 것이고, PyObjC의 Cocoa 창(`examples/cocoa/`), Swift 앱에 임베드한 Python(`examples/swiftui/`), Qt와 wx에서 확인했습니다([F84, F86, F89](../reference/verified-findings-macos.md)). Tk의 `winfo_id()`는 `NSView`가 아니어서 쓸 수 없습니다. 오프스크린 어댑터(`cefweaver.ui`)와 별개의 경로이고 입력, 메뉴, IME는 CEF가 네이티브로 처리합니다.
- **닫기**: `DoClose()`가 `false`를 돌려주면 CEF가 호스트 창에 `performClose:`를 보내 앱의 창 전체를 닫고, CEF가 만든 창에서는 `on_before_close`가 오지 않았습니다. 래퍼는 창이 있는 브라우저(`parent_view`나 CEF의 창)에서 `DoClose`를 `true`로 돌려 뷰를 직접 떼고 `CloseBrowser(true)`로 닫기를 끝냅니다. `shutdown()`은 이제 0.06초입니다([F87, F88](../reference/verified-findings-macos.md)).
- **폴링 루프**: `external_message_pump`를 쓰지 않으면 `do_message_loop_work()`가 `NSApp`의 이벤트도 처리합니다. 앱이 자기 런 루프를 가졌다면 `MessagePump`를 쓰세요.
- **오프스크린의 키**: macOS는 편집 키에 `native_key_code`를, KEYUP에 문자를 요구합니다. `cefweaver.ui`가 채웁니다([F85](../reference/verified-findings-macos.md)).

macOS에서 다른 점은 [F82](../reference/verified-findings-macos.md)에 있습니다. 공유 텍스처가 없는 것이 오프스크린 쪽에서 가장 크게 영향을 줍니다. 종료에서 Rosetta와 Swift 임베딩 때 Chromium의 teardown 감시가 프로세스를 죽이는 문제는 원인을 찾지 못했습니다([F89, F90](../reference/verified-findings-macos.md)).

## 문서와 메타데이터의 불일치

`README.rst`의 소개 문단은 여러 GUI 툴킷의 예제가 있다고 쓰며, 저장소의 `examples/`에는 `cocoa`, `gtk3`, `kivy`, `print`, `pywin32`, `qt`, `sdl2`, `swiftui`, `tk`, `views`, `wx`가 있습니다. 소개 문단이 든 툴킷 모두에 예제가 있는지는 확인하지 못했습니다(PyWin32는 이번에 더했습니다). 실제 상태는 이 페이지를 따릅니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)
- [런타임 파일 배치](runtime-layout.md)
- [실행해서 확인한 macOS](../reference/verified-findings-macos.md)
- [C++ 핸들러](../components/native-handlers.md)
- [scikit-build-core로 setup.py 없이 빌드하기 (프로토타입, Windows 준비)](../analyses/scikit-build-core-prototype.md)
- [실행해서 확인한 Windows](../reference/verified-findings-windows.md)
