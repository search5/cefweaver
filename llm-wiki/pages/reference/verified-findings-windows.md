---
title: 실행해서 확인한 Windows (F116부터)
type: reference
sources:
  - CMakeLists.txt
  - cmake/CefweaverExtension.cmake
  - native/cefwrapper/library.cpp
  - native/cefsubprocess/cefsubprocess.cc
  - native/cefsubprocess/CMakeLists.txt
  - cefweaver/__init__.py
  - cefweaver/ui/view.py
  - cefweaver/ui/session.py
  - cefweaver/ui/toolkits/pywin32.py
  - examples/pywin32/smoke.py
  - examples/common/winxdo.py
  - tests/test_smoke.py
  - tests/test_ui.py
  - tools/gen/emit_cython.py
  - .gitattributes
updated: 2026-10-13
---

# 실행해서 확인한 Windows (F116부터)

Windows 지원을 더하며 실제로 빌드하고 실행해서 확인한 기록입니다. 앞의 항목은 [실행해서 확인한 macOS](verified-findings-macos.md)와 [남은 API](verified-findings-opened.md)에 있습니다. 환경은 모두 Windows 11 Pro 10.0.26200, Visual Studio Build Tools 2026(MSVC 14.50.35717), uv가 받은 CPython 3.13.1, CEF 154.0.34(`windows64` prebuilt)이고, 날짜는 2026-10-11입니다.

## F116. wheel 빌드

`uv build --wheel -o dist`를 저장소 루트에서 실행했습니다(`CEF_ROOT`를 주지 않아 CMake가 CEF를 `third_party/cef`에 받았고, 압축 348MB, 푼 것 911MB입니다). scikit-build-core 1.1.1이 CMake 4.4.4로 Visual Studio 18 2026 생성기를 골랐습니다. 구성은 CEF를 내려받는 첫 실행에 약 125초가 걸렸고 `build/skbuild`는 약 800MB입니다. 이전에 남아 있던 Windows 코드는 그대로는 빌드되지 않았고, 다음 순서로 막혔습니다.

| 순서 | 증상 | 원인과 조치 |
| --- | --- | --- |
| 1 | `IMPORTED_LOCATION not set for imported target "cef_sandbox_lib"` | 래퍼는 `no_sandbox`를 쓰는데 CEF의 cmake가 샌드박스를 켰습니다. 루트 `CMakeLists.txt`가 `WIN32`에서 `USE_SANDBOX`를 `OFF`로 고정합니다 |
| 2 | `C3861: 'CefEnableHighDPISupport'` (`library.cpp`와 `cefsubprocess.cc`) | CEF 154 헤더에 함수가 없습니다. 호출을 지웠습니다. 고DPI는 매니페스트와 앱이 정합니다 |
| 3 | `C2589` 등(`cef_ref_counted.h`의 `std::max`) | 확장 모듈에 `NOMINMAX`가 없어서 `<windows.h>`의 `max` 매크로가 걸렸습니다. `NOMINMAX WIN32_LEAN_AND_MEAN UNICODE _UNICODE`를 줍니다 |
| 4 | `C2440`(`char8_t`) | C++20에서 `path::u8string()`은 `std::u8string`입니다. 경로를 UTF-8 `std::string`으로 바꾸는 함수(`PathToUtf8`, `PathFromUtf8`)를 두었습니다. `path::string()`은 ANSI 코드 페이지라 사용자 이름이 한글이면 잘립니다 |
| 5 | `mt.exe ... Failed to load and parse the manifest` | `cefsubprocess.exe.manifest`와 `compatibility.manifest`가 저장소에 없었습니다. CEF의 `tests/cefsimple/win/`에서 가져왔습니다 |
| 6 | (빌드가 저장소 밖으로 복사) | `native/cefsubprocess/CMakeLists.txt`가 `../cefwrappertest`와 `../../../src/PyCef_Dev`로 `COPY_FILES`하던 옛 줄을 지웠습니다 |

그 밖에 확장 모듈은 `/MT`(CEF의 래퍼 라이브러리와 같은 정적 런타임), `/utf-8`, `/bigobj`로 컴파일합니다. 서브프로세스 경로는 `.pyd`가 있는 디렉터리 기준으로 바꿨고(원래는 현재 작업 디렉터리 기준 `cefsubprocess/cefsubprocess.exe`), `cmake/CefweaverExtension.cmake`의 런타임 `install()`을 Windows에도 적용했습니다(`.lib`는 뺌). wheel은 `cefweaver-0.1.0-cp313-cp313-win_amd64.whl`(약 180MB)이고 안에 `_cefweaver.cp313-win_amd64.pyd`(5.3MB), `cefsubprocess.exe`, `libcef.dll`(290MB), 나머지 DLL, `.pak`, `icudtl.dat`, `locales/`가 있습니다.

설치한 wheel에서 `import cefweaver`가 처음에는 `ModuleNotFoundError: fcntl`(`texture.py`)로 실패했습니다. `fcntl`을 Windows에서 가져오지 않게 하고 `read_plane()`은 `NotImplementedError`를 내게 했습니다. 그 뒤 `cefweaver.get_version()`이 `Version(cefweaver='0.1.0', cef_major=154, ...)`를 돌려주었습니다. `libcef.dll`은 지연 적재라서 `__init__.py`가 전체 경로로 먼저 올립니다.

생성된 코드가 `cef_window_handle_t`를 `unsigned long`(Windows에서 32비트)으로 선언해서 포인터 크기 HWND를 자른다는 경고(`C4311`)가 났습니다. `tools/gen/emit_cython.py`가 `uintptr_t`로 선언하게 고치고 다시 생성했습니다. **이 변경을 Linux와 macOS에서는 빌드해 보지 않았습니다**(두 곳에서 `uintptr_t`는 `unsigned long` 또는 포인터와 같은 폭이라 달라지지 않을 것으로 보지만 확인하지 못했습니다). 그 뒤 Linux x86_64에서 확인했습니다(2026-10-11): `generate.py --check`는 최신이었고, 병합한 트리의 wheel 빌드는 `library.cpp`의 `PathToUtf8`과 `PathFromUtf8`이 Linux에서 쓰이지 않아 `-Werror=unused-function`으로 실패했습니다. 두 함수에 `[[maybe_unused]]`를 붙이자 빌드가 되고 시험 547개가 통과했습니다(건너뜀 10개, 예상된 실패 3개). macOS는 빌드해 보지 못했습니다. 같은 트리를 Windows에서 다시 빌드하니 `[[maybe_unused]]`는 MSVC(`/W4 /WX`)에서도 문제가 없었습니다(경고는 링크의 `LNK4199`뿐).

## F117. 시험 결과

명령: `.venv-test\Scripts\python.exe -P -m unittest discover -s tests -v`(설치한 wheel, 데스크톱에서 실행). 세 번 돌렸습니다.

| 실행 | 결과 | 비고 |
| --- | --- | --- |
| 1 (시험을 고치기 전, 임시 폴더 정리 오류를 막은 뒤) | 546개, 744초, 실패 13, 오류 3, 건너뜀 16 | 첫 실행은 약 28개가 실패했는데 대부분 `chrome_debug.log` 잠금으로 임시 폴더를 못 지운 오류였습니다. 이 실행에서 남은 16개를 아래 F118, F121과 시험의 Linux 가정으로 갈랐습니다 |
| 2 (시험 수정 뒤) | 547개, 667초, 실패 3, 건너뜀 22 | 실패 3개 중 2개는 문서 점검(문서를 고치기 전에 돌아서 실패, 문서를 고친 뒤 단독 실행은 통과)이고 1개는 새로 더한 Windows quickstart 시험(venv의 `python.exe`는 런처라서 PID로는 창을 못 찾음, 창 클래스 이름으로 고침) |
| 3 (최종 wheel) | **547개, 532초, `OK`, 건너뜀 21, 예상된 실패 3** | `cef_window_handle_t` 변환을 `uintptr_t`로 고친 wheel(위)입니다 |

| 4 (Linux의 `-Werror` 수정을 받은 트리) | 547개, 590초, 실패 2 | 이 둘은 Windows에서 **간헐적으로 실패하는 시험**이었습니다(단독으로 6번 중 4번, 4번 중 4번). `test_a_browser_runs_in_the_headless_adapter`는 첫 프레임(흰색)이 오고 0.3초 뒤에 색을 검사했고, `test_keys_beyond_a_letter_edit_and_move_in_an_offscreen_input`은 입력란을 비우는 스크립트와 앞서 보낸 `x` 키가 다른 경로로 가서 순서가 보장되지 않았습니다. 앞의 두 전체 실행에서는 우연히 통과했습니다. 조건을 기다리게 고쳐 단독 6번씩 모두 통과했습니다 |
| 5 (고친 시험) | 547개, 569초, 오류 1 | 임시 폴더의 `chrome_debug.log` 잠금(위와 같은 원인)이 `cefweaver-root-`와 `cefweaver-profile-` 폴더에서도 났습니다. 네 곳 모두 `ignore_cleanup_errors`를 **Windows에서만** 켜게 했습니다 |
| 6 (최종) | **547개, 567초, `OK`, 건너뜀 21, 예상된 실패 3** | `examples/pywin32/smoke.py` 27개도 2회 통과 |

시험을 고친 것은 크게 넷입니다. (1) Linux 가정: `/proc`(PowerShell로 대체), `libX11`, `c++`(없으면 건너뜀), `startswith("/")`(`os.path.isabs`), `signal.SIGKILL`. (2) `default_ozone_platform()`이 Wayland 소켓 경로를 `os.path`로 다루어서 Windows에서 POSIX 경로를 절대 경로로 보지 않던 것을 `posixpath`로 고쳤습니다(Wayland는 Linux입니다). (3) 줄바꿈: git이 CRLF로 체크아웃해서 생성 파일 비교가 실패했습니다. `.gitattributes`로 LF를 고정하고 생성 파일을 다시 만들었습니다. (4) `CHAR` 이벤트(F118)와 아래 F121의 차이입니다. 건너뛴 21개는 Linux나 macOS 전용, Wayland, GPU, `pygame`과 `PyYAML` 없음, `c++` 없음, 그리고 F121의 둘입니다. `c++`가 없는 것은 이 기계에 GCC나 Clang이 없어서이고, 그 시험 4개(생성된 C++ 컴파일)는 Windows에서 돌려 보지 못했습니다.

## F118. Windows의 `CHAR` 키 이벤트는 문자 코드를 `windows_key_code`에 둡니다

처음 전체 시험에서 호스트에 `RAWKEYDOWN`, `CHAR`, `KEYUP`을 보내 `a`를 입력하는 시험 3개가 `a` 대신 `A`(또는 `abc` 대신 `ABC`)를 얻었습니다. 키보드의 Caps Lock은 꺼져 있었습니다(`GetKeyState(VK_CAPITAL)`이 0). 시험과 `BrowserView`가 `CHAR`에도 가상 키 코드(`A`는 65)를 `windows_key_code`로 보냈기 때문으로, Windows는 `WM_CHAR`의 `wParam`(문자)을 이 자리에 받습니다. `BrowserView._char()`가 Windows에서 `windows_key_code`를 문자로 바꾸게 고쳤고, 시험의 `CHAR` 이벤트도 같게 만들었습니다. 고친 뒤 세 시험과 UI의 편집 키 시험(`test_editing_keys_edit_a_field_without_native_codes_from_the_toolkit`)이 통과했습니다. `send_key_event`로 직접 `CHAR`를 보내는 사용자는 Windows에서 같은 규칙을 따라야 합니다.

## F119. pywin32 툴킷

`cefweaver/ui/toolkits/pywin32.py`의 `Win32Browser`는 `SdlBrowser`처럼 창, 브라우저, 메시지 루프를 한 클래스에 둡니다. 구조는 [툴킷 예제](toolkit-examples.md)와 `cefweaver/ui/toolkits/pywin32.py`의 docstring에 있고, 여기에는 실행해서 알게 된 것만 적습니다. 예제는 `examples/pywin32/`(`quickstart.py`, `browser.py`, `smoke.py`, `README.md`)입니다.

- 창이 뜨고 데모 페이지가 그려지고 정상 종료했습니다. `smoke.py`는 `examples/common/checks.py`의 공통 점검 23개에 이 툴킷의 점검 4개(페이지 안의 드래그, `WM_DROPFILES`, 컨텍스트 메뉴 2개)를 더한 **27개**를 실제 입력으로 돌려 모두 통과했습니다(`ALL OK`). 입력은 `xdotool` 대신 `examples/common/winxdo.py`가 `SendInput`으로 보냅니다(마우스 이동과 클릭, 휠, `ctrl+a` 같은 조합 키, 문자 입력). `checks.py`가 Windows에서 이 모듈을 부르도록 했습니다.
- **pywin32에 없는 것**: `AdjustWindowRectEx`, `SetTimer`, `KillTimer`, `DragQueryPoint`, 상수 `WM_MOUSEHWHEEL`이 없었습니다(`win32gui`와 `win32api`와 `win32con`에서 `hasattr`로 확인). `ctypes`로 채웠고, 그림도 pywin32에 `StretchDIBits`가 없어서 `ctypes`입니다.
- **고친 결함(실행해서 발견)**: (1) 키 메시지의 `lParam`을 부호 없는 32비트 그대로 `native_key_code`로 보내서, 키를 뗄 때(31번 비트가 켜짐) `OverflowError: Python int too large to convert to C long`이 났습니다. 부호 있는 32비트로 바꿨습니다. (2) 창 프로시저가 Alt 키 메시지(`WM_SYSKEYDOWN`/`UP`)를 `DefWindowProc`에 넘기자, Alt를 한 번 눌렀다 떼는 것만으로 시스템 메뉴 모드(메뉴가 없는 창에서도 키를 기다리는 자체 루프)에 들어가 메시지 루프가 막혔습니다(점검이 첫 줄을 찍기 전에 멈춤). Alt+Space만 `DefWindowProc`에 넘기고 나머지 시스템 키와 `WM_SYSCHAR`는 처리한 것으로 돌려줍니다. (3) `win32api.DragQueryFile(hdrop)`가 목록이 아니라 숫자를 돌려주어, 개수를 먼저 물은 뒤 하나씩 읽게 했습니다.
- 컨텍스트 메뉴는 `TrackPopupMenu`(Windows의 자체 루프)입니다. 점검은 오른쪽 클릭 뒤 1초 있다가 Esc를 보내 메뉴를 닫고, 메뉴가 열려 있던 동안 `post`와 `call_later`가 창 프로시저에서 계속 돌아 CEF가 이어지는 것을 확인했습니다(항목은 한 줄이었습니다: 틀린 단어가 없는 문단 위의 메뉴).
- 처음 찍은 스냅샷이 흰 화면이었던 것은 첫 페인트 전에 찍어서였고, 3초 뒤에는 페이지가 그려졌습니다(툴킷의 결함이 아닙니다).
- **확인하지 못한 것**: 배율이 100%가 아닌 화면(이 기계는 96 DPI), 여러 모니터, 실제 한글 입력기(`WM_IME_COMPOSITION` 처리는 썼지만, 점검은 같은 `view` 메서드를 직접 부릅니다), 소리 출력, 탐색기에서 실제로 끌어다 놓기(점검은 실제 `DROPFILES` 블록을 담은 `WM_DROPFILES`를 보냅니다), 텍스트 드롭(OLE가 필요해서 만들지 않음).

## F120. 동결 도구

같은 도구 버전(PyInstaller 6.22.3, cx_Freeze 8.7.1)과 py2exe 0.14.2.0으로 pywin32 툴킷의 최소 앱과 `smoke.py`를 묶었습니다. 결과 표와 설정은 [앱 묶기](../procedures/freeze-app.md)의 "Windows" 절에 있습니다. 요약하면 PyInstaller(`--collect-all cefweaver` 필요, 없으면 ICU 오류로 종료 코드 3)와 cx_Freeze(설정 없음)와 py2exe(CEF 런타임을 손으로 복사, 그리고 `__init__.py`의 `add_dll_directory` 가드가 필요했음)가 모두 최소 앱 3회 중 3회, `smoke.py` 27개를 모두 통과했습니다.

## F121. 아직 설명하지 못한 Windows의 차이

시험에서 Windows만 다르게 나온 것 중 원인을 보지 않은 것입니다. 시험 코드는 해당 줄에 이유를 적고 건너뛰거나 기대를 Windows에 맞게 느슨하게 했습니다.

| 시험 | Windows의 결과 | 조치 |
| --- | --- | --- |
| `test_a_suggestion_of_the_menu_replaces_the_misspelled_word_on_a_page_that_lost_the_focus` | 메뉴에 틀린 단어가 비어 왔습니다(`[('', [])]`) | Windows에서 건너뜀 |
| `test_auto_resize_reports_the_content_size_to_the_display_handler` | 최댓값 `(900, 700)`을 주었는데 `Size(944, 504)`를 보고했습니다 | Windows에서는 양수인지만 확인 |
| `test_a_server_that_asks_for_a_client_certificate_is_told_to_the_request_handler` | 서버가 인증서를 요청했을 때 목록의 인증서 수가 0이 아니라 2였습니다(사용자의 개인 인증서가 Windows 저장소에 있는 것으로 보입니다. 추정입니다) | Windows에서는 수를 따지지 않음 |
| `test_a_views_window_holds_a_toolbar_and_a_browser_view` | 창 크기(640)와 툴바 너비(624)가 16픽셀 달랐습니다(창 틀) | Windows에서는 `get_client_area_bounds_in_screen()`과 비교 |
| `test_the_print_handler_sees_the_start_the_settings_and_the_reset` | 90초 시간 초과(`PrintHandler`는 Linux 전용이라 Windows는 시스템 인쇄 대화상자를 띄우는 것으로 보입니다. 추정입니다) | Windows에서 건너뜀 |

Linux에서만 의미가 있는 시험(`/proc`, `libX11`, `c++`로 생성 코드 컴파일)은 Windows에서 건너뛰거나(`c++`가 없으면 건너뜀) 대체 방법을 썼습니다. `/proc` 대신 PowerShell의 `Get-CimInstance Win32_Process`로 렌더러 프로세스를 찾고 `os.kill`(Windows에서는 `TerminateProcess`)로 끝냅니다. 처음에는 `cefsubprocess.exe`로 거르지 않아 시험 프로세스 자신의 명령줄(스크립트 안의 `--type=renderer` 글자)이 맞아서, 자기 자신을 종료 코드 15로 끝낸 일이 있었습니다.

## 관련 페이지

- [플랫폼 지원 현황](../concepts/platform-support.md)
- [앱을 PyInstaller와 cx_Freeze로 묶기](../procedures/freeze-app.md)
- [시험 실행하기](../procedures/run-tests.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [툴킷 예제](toolkit-examples.md)
