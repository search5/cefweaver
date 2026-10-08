---
title: 실험으로 확인한 사실
type: reference
sources:
  - native/cefwrapper/library.cpp
  - native/cefsubprocess/cefsubprocess.cc
  - cefweaver/__init__.py
  - cefweaver/cef_api.pxi
  - tools/prepare.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 실험으로 확인한 사실

F15 이후(클라이언트 핸들러, 브라우저 호스트, Chrome과 Alloy 스타일, 생성기, `types` 모듈)는 [실험으로 확인한 사실 2](verified-findings-api.md)에 있습니다.

코드를 읽는 것만으로는 알 수 없어서 직접 실행해서 확인한 사실입니다. 날짜는 2026-10-07과 2026-10-08이고, 환경은 Linux x86_64(6.17), GCC 15, CEF 154.0.34, 가상 X 서버(Xvfb)입니다(달리 적은 경우 제외). 각 항목은 방법, 결과, 영향을 적습니다. 추정이 섞인 부분은 그렇게 밝힙니다.

## F1. icudtl.dat는 libcef.so가 있는 디렉터리에서 찾는다

- **방법**: `libcef.so`와 리소스(`icudtl.dat`, `*.pak`)를 서로 다른 디렉터리에 두고(`libcef.so`는 `LD_LIBRARY_PATH`로 찾게 함) 초기화합니다. `resources_dir_path`를 (가) 확장 모듈 디렉터리(리소스가 있는 곳)로 지정, (나) 존재하지 않는 경로, (다) 설정 안 함의 세 경우를 시험합니다. 정상 배치(같은 디렉터리)에서도 같은 세 경우를 시험합니다.
- **결과**: 분리 배치에서는 세 경우 모두 `Invalid file descriptor to ICU data received`로 실패했습니다. 정상 배치에서는 세 경우 모두 성공했습니다(존재하지 않는 경로도).
- **영향**: Linux의 CEF 154에서 `resources_dir_path`는 `icudtl.dat` 위치를 바꾸지 못합니다. 런타임 파일을 `libcef.so`와 같은 디렉터리에 둡니다. 처음에는 `resources_dir_path`를 기본으로 설정해서 이 문제를 막는다고 생각했으나 틀렸고, 자동 설정을 제거했습니다([런타임 파일 배치](../concepts/runtime-layout.md), [cefpython의 CEF 패치와 cefweaver](../analyses/cefpython-patches.md)).

## F2. API 버전을 설정하기 전에 라이브러리 객체를 쓰면 프로세스가 죽는다

- **방법**: 초기화 없이 `Request.create()`를 호출합니다.
- **결과**: `FATAL:cef/libcef_dll/cpptoc/request_cpptoc.cc:429] CefRequest_0_CppToC called with invalid version -1`로 프로세스가 중단(`Trace/breakpoint trap`)되었습니다.
- **원인**: CEF 소스(`libcef_dll/libcef_dll2.cc`)에서 `cef_api_hash(version, entry)`가 첫 성공 호출 때 전역 버전을 설정하고, 래퍼는 `CefInitialize`와 `CefExecuteProcess` 쪽에서 이 함수를 부릅니다.
- **영향**: 생성된 모듈이 불러올 때 `cef_api_hash(CEF_API_VERSION, 0)`를 호출합니다. 이후 `Request.create()` 같은 호출이 초기화 전에도 안전합니다.

## F3. 서브프로세스 종료 때의 stack smashing

- **방법**: 서브프로세스가 종료할 때 `*** stack smashing detected ***`가 두 번(프로세스 두 개) 나왔습니다. `__stack_chk_fail`을 가로채는 `LD_PRELOAD` 라이브러리로 주소를 출력하고 `nm`/`objdump`로 대조했습니다([충돌 조사 방법](../procedures/debug-crashes.md)).
- **결과**: 실패 위치는 `cefsubprocess`의 `main` 끝(`sub %fs:0x28` 뒤의 `jne __stack_chk_fail`)이고 프로세스는 `--type=utility --utility-sub-type=unzip.mojom.Unzipper`였습니다. 순정 `cefsimple`(같은 배포본에서 빌드)의 `main`에는 `%fs:0x28` 검사가 0개였고 시험 3회에서 오류가 0건이었습니다. 우리 `main`에는 검사가 있었고 같은 조건의 시험 3회에서 매번 2건이 나왔습니다. `main`에 `__attribute__((no_stack_protector))`를 붙이자 3회 모두 0건이 되었습니다.
- **해석(추정)**: 순정에서 오류가 안 나는 이유는 그 `main`에 검사가 없어서이고, 검사가 있으면 실패하는 근본 원인은 Chromium의 zygote가 자식 프로세스를 이 프레임으로 돌려보낼 때 스택 보호값이 달라지기 때문일 가능성이 높습니다. 이 메커니즘 자체는 확인하지 못했습니다.

## F4. 바인딩 객체를 렌더러로 원시 메모리 복사하면 JS 콜백이 동작하지 않는다

- **방법**: 초기 구현 그대로 JS에서 `window.hello(...)`를 호출하고 40초 동안 메시지 루프를 돌렸습니다.
- **결과**: 콜백이 한 번도 호출되지 않았고 `shutdown()`에서 세그멘테이션 오류가 났습니다.
- **원인**: `JavascriptPythonBinding`이 `std::string`을 품고 있는데 이 객체 배열을 `CefBinaryValue`로 렌더러 프로세스에 그대로 복사했습니다. 다른 프로세스에서는 문자열 내부 포인터가 유효하지 않습니다.
- **수정 후**: 이름 목록(`CefListValue`)만 전달하게 바꾸자 콜백이 호출되었습니다. 세그멘테이션 오류의 직접 원인은 브라우저를 닫지 않고 `CefShutdown()`을 호출한 것이었고 닫기와 `Browser` 참조 해제를 추가했습니다([JavaScript 바인딩](../concepts/javascript-bindings.md), [수명 주기와 메시지 루프](../concepts/lifecycle-and-message-loop.md)).

## F5. 캐시된 CEF_ROOT가 요청한 버전을 덮어쓴다

- **방법**: 120 배포본으로 만든 `build/native`에서 `--cef-version`으로 154를 요청했습니다.
- **결과**: 154를 요청했는데 `Using existing CEF distribution: ...120...`가 출력되었고 120이 쓰였습니다(조용히).
- **영향**: `CEF_ROOT`를 캐시하지 않고 `CEFWEAVER_CEF_ROOT`로 기록하며, `--cef-root`가 없으면 `-UCEF_ROOT`를 넘깁니다. "120 캐시에서 154 요청", "`--cef-root`로 120 지정", "이후 지정 없이 154 요청"의 세 경우를 실행해 모두 요청한 버전이 쓰이는 것을 확인했습니다([CEF 확보 방식](../concepts/cef-acquisition.md)).

## F6. setuptools는 정적 라이브러리의 변경을 감지하지 못한다

- **방법**: `library.cpp`를 고쳐 `libcefwrapper.a`를 다시 만든 뒤 `uv build --wheel`.
- **결과**: 확장이 다시 링크되지 않아 서브프로세스 경로가 옛 값(`cefsubprocess/cefsubprocess`)인 wheel이 만들어져, 시험이 서브프로세스 실행 오류로 실패했습니다.
- **영향**: `ext-modules`에 `depends`를 추가했습니다([패키징](../components/packaging.md)).

## F7. 인자 없는 uv build는 실패하고, -P 없는 시험 실행은 조용히 건너뛴다

- **방법**: `uv build`(인자 없음)와 저장소 루트에서 `python -m unittest discover -s tests`를 실행했습니다.
- **결과**: 앞의 것은 sdist에서 wheel을 만들 때 `include/cef_client.h`를 못 찾아 실패했습니다. 뒤의 것은 `Ran 24 tests ... OK (skipped=11)`(당시 시험은 24개)로 끝났습니다. 소스 트리의 `cefweaver/`가 설치된 wheel을 가렸기 때문입니다. `-P`를 붙이면 24개가 모두 실행됩니다.
- **영향**: 문서의 명령을 `uv build --wheel`과 `python -P -m unittest ...`로 고쳤습니다.

## F8. 네이티브 Wayland와 XWayland 모두 Chromium이 동작한다

[Chromium의 Wayland와 X11 동작](../analyses/chromium-on-wayland.md)에 방법과 수치를 적었습니다. 요약: 두 경우 모두 페이지의 JS가 Python으로 보고했고, WebGL 렌더러가 NVIDIA GPU(ANGLE)로 잡혔으며, 1.5초에 `requestAnimationFrame`이 91번(Wayland)과 93번(XWayland) 호출되었습니다. 이 시험은 실제 화면에 창을 잠깐 열었습니다. 사람이 눈으로 화면을 확인한 것은 아닙니다.

## F9. 창 닫기는 is_running을 거짓으로 만든다

- **방법**: 창 관리자가 없는 Xvfb에서 `python-xlib`로 CEF 창(매핑된 1050x1004 창)에 `WM_DELETE_WINDOW`를 보냅니다. 처음에는 숨겨진 10x10 임시 창에 보내서 실패했습니다.
- **결과**: 요청 약 4.0초 뒤 `is_running`이 `False`가 되어 루프가 끝났고 `shutdown()`도 정상이었습니다.

## F10. 브라우저는 initialize() 안에서 이미 만들어져 있다

- **방법**: `initialize("about:blank")` 직후 메시지 루프를 돌리지 않고 `load_url()`과 `execute_javascript()`를 부릅니다.
- **결과**: `load_url`은 `True`, `execute_javascript`는 `False`(로딩 중)였습니다. 크래시는 없었습니다. CEF의 보장은 아니고 관찰입니다.

## F11. data: URL에 charset이 없으면 한국어 로케일에서 EUC-KR로 해석된다

- **방법**: `<script>`가 `report('text-é')`를 호출하는 페이지를 `data:text/html;base64,...`로 열었습니다(`<meta charset>` 없음).
- **결과**: Python이 `'text-챕'`을 받았습니다. `<meta charset="utf-8">`를 넣으면 `'é한글'`이 정확히 전달되었습니다. 바인딩 쪽 오류가 아니라 페이지의 인코딩 추정 때문입니다(`--lang=ko` 환경에서 관찰).

## F12. strip과 크기

- `libcef.so`(154 Release): 1,455,021,248바이트. `strip --strip-debug` 후 465,160,736바이트, `strip --strip-unneeded` 후 272,219,288바이트. strip한 복사본으로 모든 시험이 통과했습니다.
- 스테이징 총량 약 359MB, wheel 약 148MB, 설치 후 약 363MB.

## F13. 파서와 헤더

- CEF master의 `cef_parser.py`로 154 배포본 헤더를 읽어 클래스 185개, 가상 메서드 1,439개(master 소스에서는 1,441개). 전역 함수 53개.
- 파서의 `get_result_ptr_type_root()`는 C API 이름(`cef_request_t`)을 돌려주고, `is_result_struct_enum()`은 "참조나 포인터가 아님"이라는 어림짐작입니다. `CefSchemeHandlerFactory`처럼 클라이언트 쪽 클래스는 `class CEF_EXPORT`가 아니라 `class Name :`로 선언되어, 처음의 순수 가상 감지가 실패했습니다([바인딩 생성기의 설계](../concepts/binding-generator.md)).

## F14. Python 버전

Python 3.11, 3.12, 3.13, 3.14에서 wheel을 빌드하고 통합과 생성기 시험 24개를 모두 통과했습니다(생성된 Cython 코드 포함). 3.15는 시험하지 않았습니다.

## F36. 명령줄 스위치는 자식 프로세스에 전달되지 않는다

- **방법**: `add_command_line_switch`로 `cefweaver-custom-switch=abc`, `disable-gpu`, `site-per-process`를 주고 실행 중인 프로세스들의 명령줄(`ps -eww`)을 비교했습니다.
- **결과**: 세 스위치 모두 `--type=renderer`, `gpu-process`, `utility`, `zygote` 프로세스의 명령줄에 **없었습니다.** 반면 `--ozone-platform=x11`은 자식에게 있었는데, Chromium이 스스로 전달하는 스위치이기 때문으로 보입니다(이유는 확인하지 않음). 그래서 `add_command_line_switch`의 스위치는 브라우저 프로세스에서만 읽힌다고 봐야 합니다. 자식 프로세스에 필요한 스위치는 `OnBeforeChildProcessLaunch`로 붙여야 합니다(메시지 라우터가 이렇게 합니다, F34).
- **영향**: 이전의 "자식 프로세스가 물려받습니다"라는 서술(`native-library-api.md`, `native-handlers.md`, `cef_wrapper_app.cc`의 주석)이 틀려서 고쳤습니다. 스위치를 자식에게도 보내는 옵션은 **만들지 않기로 했습니다**: java-cef도 같은 한계이고 사용자가 "java-cef만큼만" 가기로 했습니다(아래 비교와 [설계 결정 기록](design-decisions.md)).
- **java-cef와의 비교**(소스 확인, 실행하지는 않음): 스위치를 주는 길은 `CefApp.getInstance(args, settings)`의 `args`와 `CefAppHandler.onBeforeCommandLineProcessing`뿐이고, 그 훅은 `process_type`이 비었을 때(브라우저 프로세스)만 Java로 전달됩니다(`client_app.cpp:34`). `OnBeforeChildProcessLaunch`는 `native/`에 없습니다. 자식에게 값을 보낼 때는 스위치 대신 `extra_info`(라우터 설정), 프로세스 메시지(`AddMessageRouter`), 부모 PID 이름의 임시 파일(커스텀 스킴)을 씁니다.

## F37. 교차 사이트 iframe이 로드되지 않는다

- **방법**: `add_resource`로 `http://a.test/main.html`(iframe 포함)과 자식 페이지를 두 호스트에 제공하고 `LoadHandler`로 관찰했습니다.
- **결과**: 같은 사이트(`a.test`)의 iframe은 로드되고(`load-end` 200, `iframe-onload`), 다른 사이트(`b.test`)의 iframe은 오류도 로드 완료도 없이 멈춥니다. `site-per-process` 유무와 질의 핸들러 유무와 관계없이 같았고, `b.test`를 메인 프레임으로 여는 것은 정상이었습니다.
- **미확인**: 원인(두 번째 호스트의 스킴 핸들러, 프로세스 전환, CEF 문제 등)과 cefsimple에서도 같은지는 조사하지 않았습니다. 그래서 사이트 격리로 프로세스가 갈리는 프레임에서 메시지 라우터가 동작하는지는 **확인하지 못했습니다.**

## F38. 오프스크린 렌더링

- **방법**: `offscreen = True`와 `RenderHandler`로 빨간 페이지를 그리고, 크기 변경, 마우스 클릭, 팝업을 시험했습니다.
- **결과**:
  - `on_paint`가 `PaintElementType.VIEW`, 200x100, 길이 80000(`200*100*4`)의 **읽기 전용** `memoryview`를 받고 첫 픽셀이 BGRA의 빨강(`00 00 ff ff`)입니다. `dirty_rects`는 `Rect`의 목록이고 화면 안입니다. 호출이 끝난 뒤 뷰를 쓰면 `ValueError`입니다. `get_host().is_window_rendering_disabled()`는 `True`.
  - `get_view_rect`가 돌려준 `Rect`(핸들러의 **구조체 출력**)가 CEF에 전달됩니다. 크기를 바꾸고 `was_resized()`를 부르면 `320x240` 프레임이 옵니다. 이로써 구조체 출력 경로를 Python 핸들러까지 확인했습니다([알려진 제약과 미검증 항목](known-constraints.md)).
  - `send_mouse_click_event`가 오프스크린 페이지의 `onclick`에 닿습니다(입력은 준비 전에 버려지므로 다시 보냄, 기존 규칙).
  - `window.open`은 `null`(막힘)이고 브라우저는 하나뿐입니다.
- **발견(결함, 수정)**: `shutdown()`이 `SIGSEGV`로 죽었습니다. 창이 없는 브라우저는 `CloseBrowser(true)` 안에서 `OnBeforeClose`가 바로 실행되어 `browser_list_`에서 항목이 지워지는데, `CloseAllBrowsers`가 같은 목록을 순회하고 있어 반복자가 무효가 되었습니다. 복사본을 순회하도록 고쳤습니다(창 있는 브라우저는 닫기가 비동기라 드러나지 않았음).
- **영향**: 오프스크린 렌더링이 열렸습니다([오프스크린 렌더링](offscreen-rendering.md)).

## F39. 구조체 종류의 확대 (키보드, 화면 정보)

- **방법**: `size` 머리와 열거형, `char16_t` 필드가 있는 구조체를 열고 오프스크린 브라우저로 시험했습니다.
- **결과**:
  - `KeyEvent`(`RAWKEYDOWN`, `CHAR`, `KEYUP`)를 `send_key_event`로 보내자 입력란에 `a`가 들어가고 페이지의 `keydown`이 `key == "a"`를 받았습니다. 잘못된 인자(`"a"`)는 `TypeError`입니다.
  - `get_screen_info`가 `(True, ScreenInfo(2.0, ...))`를 돌려주면 페이지의 `window.devicePixelRatio`가 2가 되고 `on_paint`의 크기가 400x200, 길이 `400*200*4`입니다(핸들러의 구조체 출력, 중첩 구조체 `rect`).
  - `send_touch_event`(구조체에 열거형 둘)와 `ime_set_composition`(`CompositionUnderline`의 벡터, 중첩 `Range`, 열거형 `style`)은 호출이 받아들여지고 정상 종료합니다. 결과는 시험하지 않았습니다.
- **발견**: `char16_t`는 Cython이 알지 못하는 타입이라 `cdef extern from *: ctypedef unsigned short char16_t`로 알려 주었습니다.
- **영향**: 구조체 15개가 공개되고 보고서의 타입 지원이 89%에서 90%로 늘었습니다([오프스크린 렌더링](offscreen-rendering.md)).

## F40. 바이트열 입출력 (BinaryValue)

- **방법**: `BinaryValue.create(bytes)`와 `get_data(size, offset)`를 CEF 없이, 그리고 프로세스 메시지로 렌더러를 거쳐 시험했습니다.
- **결과**:
  - `bytes`, `bytearray`, `memoryview`를 받아 복사하고, `get_data`는 오프셋과 남은 길이를 지켜 `bytes`를 돌려줍니다(요청이 더 크면 남은 만큼, 끝이면 `b""`). `str`, `int`, `list`, `None`은 `TypeError`, 음수 크기는 `OverflowError`.
  - 0부터 255까지 모든 바이트가 렌더러를 거쳐 그대로 돌아옵니다.
  - `create(b"")`는 `None`입니다. CEF의 `CefBinaryValue::Create`가 빈 데이터에 `nullptr`을 돌려줍니다(`cef_origin/libcef/common/values_impl.cc:488-494`). 리스트에 `set_binary`로 넣은 값은 리스트가 소유하므로 원래 객체는 무효가 됩니다(`copy()`가 `None`, CEF의 문서대로).
- **발견**: `nogil` 안에서는 Python 객체를 `char*`로 바꿀 수 없어 포인터를 `nogil` 앞에서 꺼냅니다.
- **영향**: 열지 못했던 `BinaryValue.create`와 `get_data`가 열렸습니다. `get_raw_data`는 일부러 열지 않았습니다([알려진 제약과 미검증 항목](known-constraints.md)).

## F41. 포커스, JS 대화상자, 파일 대화상자, 다운로드 핸들러

- **방법**: 오프스크린 브라우저에서 핸들러를 달고 각 이벤트를 일으켜 보았습니다.
- **결과**:
  - `set_focus(True)`가 `on_set_focus(browser, source)`(`FocusSource` 멤버)와 `on_got_focus`로 갑니다.
  - `alert`, `confirm`, `prompt`가 `on_js_dialog(browser, origin_url, dialog_type, message_text, default_prompt_text, callback)`로 오고 `(handled, suppress_message)`를 돌려줍니다. `callback.continue_(success, user_input)`의 답이 페이지에 가서 `confirm`은 참/거짓, `prompt`는 `"typed"`가 됩니다.
  - 파일 입력을 마우스로 누르면 `on_file_dialog(browser, mode, title, default_file_path, accept_filters, accept_extensions, accept_descriptions, callback)`(`FileDialogMode.OPEN`)이 오고, `callback.continue_([path])`의 파일이 `input.files`에 들어갑니다.
  - `Content-Disposition: attachment`인 응답이 `on_before_download(browser, download_item, suggested_name, callback)`(`suggested_name == "named.txt"`)으로 오고, `callback.continue_(path, False)`의 경로에 10바이트가 저장되며 `on_download_updated`가 `is_complete()`와 `get_received_bytes()`를 알립니다.
- **영향**: java-cef의 13개 핸들러 가운데 4개를 더해 10개가 되었습니다(키보드, 인쇄, 요청이 남음, [생성 범위와 커버리지](generated-api-coverage.md)).

## F42. 키보드와 인쇄 핸들러

- **방법**: 오프스크린 브라우저에서 키 이벤트를 보내고 `host.print()`를 불렀습니다.
- **결과**:
  - `send_key_event`로 보낸 `RAWKEYDOWN`이 `on_pre_key_event(browser, event)`로 페이지보다 먼저 오고(`KeyEvent`, `type == RAWKEYDOWN`, `windows_key_code == 65`) `(handled, is_keyboard_shortcut)`를 돌려줍니다. 오프스크린에서도 호출됩니다.
  - `host.print()`는 `on_print_start`, `on_print_settings(browser, settings, get_defaults)`(`settings`는 `PrintSettings`), `on_print_reset` 순서로 옵니다.
- **확인하지 못함**: 프린터가 없는 환경이라 Chromium이 오류를 내고(`print_error_dialog`) `on_print_dialog`, `on_print_job`은 오지 않았습니다. `get_pdf_paper_size`(구조체 반환)는 컴파일과 생성만 확인했고 CEF가 부르는 경우를 만들지 못했습니다. `on_key_event`(페이지가 처리하지 않은 키)도 단정하지 않았습니다.
- **영향**: java-cef의 13개 핸들러 가운데 12개가 되었습니다(요청이 남음).

## F43. 요청 핸들러와 리소스 요청 핸들러

- **방법**: 사용자의 `RequestHandler`를 달고 탐색과 하위 리소스를 일으켰습니다. 메시지 라우터와 함께도 시험했습니다.
- **결과**:
  - `on_before_browse(browser, frame, request, user_gesture, is_redirect)`가 `True`를 돌려주면 그 페이지는 로드되지 않습니다(시작 페이지의 `data:` URL 탐색도 이 핸들러로 옵니다).
  - `get_resource_request_handler(...)`가 `(ResourceRequestHandler, disable_default_handling)`을 돌려주면 그 핸들러의 `on_before_resource_load`가 `ReturnValue.CANCEL`로 하위 리소스(이미지)를 취소하고 페이지의 `onerror`가 불립니다. `on_resource_load_complete`가 `URLRequestStatus.SUCCESS`와 수신 바이트 수를 줍니다.
  - 라우터와 사용자의 요청 핸들러가 함께 있을 때, 사용자가 탐색을 취소(`True`)하면 열린 질의가 취소되지 않고 허용된 탐색에서만 취소됩니다.
- **확인하지 못함**: `get_auth_credentials`(`AuthCallback`)와 `on_certificate_error`는 서버가 필요해 실행하지 않았습니다. `on_render_process_terminated`, `on_open_url_from_tab`, `on_resource_redirect`, `on_resource_response`, `on_protocol_execution`도 실행하지 않았습니다. `get_cookie_access_filter`는 쿠키 구조체 때문에 생성되지 않습니다.
- **영향**: java-cef의 핸들러 13개를 모두 갖추었습니다.

## F44. 스트림과 ZIP 읽기

- **방법**: CEF를 시작하지 않고 파일, 메모리, Python 핸들러, `zipfile`로 만든 ZIP으로 시험했습니다.
- **결과**:
  - `write(b"hello")`는 5, `write(b"abcdef", 2)`는 3(항목 수)이고, 항목의 배수가 아닌 길이는 `ValueError`입니다. `read(5)`, `read(2, 2)`는 바이트열을 돌려주고 끝에서는 짧거나 `b""`입니다. `seek`, `tell`, `eof`가 맞습니다.
  - `ReadHandler`와 `WriteHandler`를 Python으로 구현해 `create_for_handler`에 주면 `read(4)`, `read(3, 2)`가 핸들러의 `read(buffer, size)`로 가고 항목 수 반환이 바이트열로 바뀌어 돌아옵니다. `write(b"1234", 2)`는 핸들러가 `(b"1234", 2)`를 받고 2를 돌려줍니다.
  - ZIP의 첫 파일을 열어 100바이트씩 읽으면 앞부분과 나머지가 맞고 끝에서 `b""`입니다. 열린 파일이 없는데 읽으면 CEF가 -1을 돌려주어 `RuntimeError`입니다.
- **영향**: 앞서 제외한 `CefStreamWriter::Write` 같은 "크기 인자가 둘인" 경우가 표로 열렸습니다([스트림과 ZIP 읽기](streams.md)).

## F45. 시간(`datetime`)과 `void*` 표

- **방법**: 시간을 돌려주는 CEF 메서드와 PostData를 시험하고, 범위 밖 핸들러까지 포함한 넓은 범위로 프록시를 컴파일했습니다.
- **결과**:
  - `ZipReader.get_file_last_modified()`가 시간대가 있는 `datetime`을 돌려주고 ZIP에 적은 2020-01-02 12:00과 하루 이내로 맞습니다. 다운로드의 `get_start_time()`은 현재 시각과 2분 안이고 `get_end_time() >= get_start_time()`입니다.
  - `PostDataElement.set_to_bytes`/`get_bytes`, `PostData`, `Request.set_post_data`/`get_post_data`가 `\x00\xff`를 포함한 바이트열을 왕복합니다.
- **발견(잠재 결함, 수정)**: 범위 밖 핸들러의 `const void*`(`DevToolsMessageObserver.on_dev_tools_message`, `ServerHandler.on_web_socket_message`, `URLRequestClient.on_download_data`, `MediaObserver`)가 const 없는 `void*`로 선언되어 있어서 범위에 넣으면 헤더와 맞지 않아 컴파일이 깨질 계획이었습니다. const를 지키고 읽기 전용 `memoryview`로 바꿨고, 범위 밖 핸들러 다섯을 넣은 넓은 범위의 프록시를 컴파일하는 시험을 더했습니다.
- **java-cef와의 비교**(소스 확인): 날짜는 `java.util.Date`로 바꾸는 한 방향이고 밀리초로 줄입니다. 스트림은 드래그 데이터의 `GetFileContents`용 `WriteHandler` 하나뿐입니다.
- **영향**: 열린 메서드가 늘었고(타입 지원 92%) `void*` 때문에 막힌 것은 일부러 제외한 9개로 줄었습니다([바이트열과 시간](bytes-and-times.md)).

## F46. java-cef가 넘기지 않는 인자의 무시 (팝업, 커서, 인증서 오류)

- **방법**: java-cef가 Java로 넘기는 인자만 Python으로 넘기고 나머지는 무시(`IGNORED_PARAMS`)하도록 하고, 창 있는 브라우저에서 `window.open`과 오프스크린에서 커서 변경을 시험했습니다.
- **결과**:
  - `on_before_popup(browser, frame, target_url, target_frame_name)`가 `True`를 돌려주면 팝업이 취소되고 `window.open`이 `null`이며, `False`면 팝업이 열립니다. 오프스크린 브라우저는 사용자 핸들러를 부르지 않고 막습니다(java-cef와 같음).
  - `on_cursor_change(browser, type)`이 `CursorType` 멤버로 옵니다(`cursor:pointer` 위에서 `HAND`).
  - `on_certificate_error(browser, cert_error, request_url, callback)`는 `ssl_info` 없이 생성됩니다(실행은 TLS 서버가 필요해 확인하지 않음).
- **발견**: 무시하는 인자도 C++ 쪽에서는 헤더와 똑같이 선언해야 해서(`CefWindowInfo&`, `bool*`, `const CefCursorInfo&`) `Ignored`가 참조, 포인터, const를 보존합니다.
- **영향**: 바닥의 격차 3개가 메워졌습니다([java-cef 동등성](java-cef-parity.md)).

## 관련 페이지

- [실험으로 확인한 사실 2: 핸들러, 호스트, 스타일, 생성기](verified-findings-api.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [설계 결정 기록](design-decisions.md)
- [충돌 조사 방법](../procedures/debug-crashes.md)
