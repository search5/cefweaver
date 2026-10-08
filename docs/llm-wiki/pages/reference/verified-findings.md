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

## F15. 클라이언트 핸들러의 이벤트와 래퍼의 동작

- **방법**: `Client`, `LoadHandler`, `LifeSpanHandler`, `DisplayHandler`를 상속한 객체를 `set_client()`로 넘기고 `data:` 페이지와 닫힌 로컬 포트의 URL을 로드했습니다(`tests/test_smoke.py`의 시험 4개).
- **결과**: 한 번의 로드에서 `on_after_created`, `on_load_start`(주 프레임), `on_loading_state_change`(`True`와 `False`), `on_title_change`, `on_load_end` 순으로 이벤트가 왔고 생성이 시작보다 앞, 시작이 종료보다 앞이었습니다. 모든 콜백은 `initialize()`를 부른 스레드(`MainThread`)에서 실행되었습니다. 닫힌 포트의 오류는 `error_code == -102`(`ERR_CONNECTION_REFUSED`)와 요청한 URL로 왔고, 래퍼는 이어서 `data:` 오류 페이지를 로드했습니다. 사용자의 `on_load_end`와 클라이언트의 getter가 예외를 일으켜도 `sys.excepthook`으로 보고될 뿐 래퍼의 준비 플래그와 JS 바인딩은 정상이었고, 종료할 때 `on_before_close`가 전달되었습니다.
- **변이 시험**: 전달 호출 두 곳(`OnLoadEnd`, `OnBeforeClose`)을 일부러 지우자 새 시험 3개가 실패했고 실패 메시지가 기다린 사건을 가리켰습니다. 복구하자 모두 통과했습니다.
- **영향**: 위임 구조가 의도대로 동작합니다. 확인하지 못한 것은 [알려진 제약과 미검증 항목](known-constraints.md)에 적었습니다.

## F16. 값 타입 구조체

- **방법**: 헤더에서 읽은 구조체로 생성한 `cefweaver_proxies.h`를 `c++`로 컴파일해 프록시를 직접 호출하는 프로그램을 만들고 실행했습니다(`tests/test_generator.py`). `libcef.so`를 링크했습니다(`CefString`이 필요).
- **결과**: 입력 구조체는 표에 `const CefRect*`로 전달되었고(`5,6,7,8`), 표가 채운 출력 구조체는 CEF 메서드의 참조 인자에 복사되었습니다(`10,20,30,40`). wheel은 C 컴파일러 경고 없이 빌드되었습니다(내보내기와 변환 함수를 `inline`으로 선언해 미사용 함수 경고를 없앴습니다). 전체 시험 48개가 통과했습니다.
- **영향**: 구조체 입력과 출력의 C++ 쪽은 확인했습니다. Python 핸들러까지의 경로는 [알려진 제약과 미검증 항목](known-constraints.md)에 적었습니다.

## F17. 브라우저 호스트

- **방법**: `browser.get_host()`로 얻은 `BrowserHost`로 줌, 마우스, 자동 크기 조정, 닫기를 실행했습니다(`tests/test_smoke.py`, 가상 X 서버).
- **결과**:
  - 줌: `set_zoom_level(1.0)` 뒤 `get_zoom_level()`이 `1.0`을 돌려줍니다(초기값 `0.0`).
  - 마우스: `send_mouse_click_event`로 보낸 클릭이 페이지의 `mousedown`으로 도착하고 좌표와 버튼이 그대로입니다(Alloy 스타일, F18). `MouseEvent`와 일반 튜플 모두 받고, 길이가 다르거나 튜플이 아니면 `TypeError`입니다.
  - 자동 크기 조정: `set_auto_resize_enabled(True, Size(100, 100), (900, 700))` 뒤 `on_auto_resize`가 `Size`(예: 360 x 240)와 함께 호출됩니다. 핸들러의 구조체 입력이 Python까지 오는 것을 이것으로 확인했습니다.
  - 닫기: `close_browser(False)`가 `on_before_close`를 부르고 `is_running`을 거짓으로 만듭니다.

## F18. Chrome 스타일과 Alloy 스타일

- **방법**: 같은 시험을 Chrome 스타일(기본값)과 `window_info.runtime_style = CEF_RUNTIME_STYLE_ALLOY`로 만든 브라우저에서 실행하고, 차이를 스파이크로 따로 조사했습니다.
- **Chrome 스타일**: `get_runtime_style()`이 `1`. `do_close`가 **호출되지 않았습니다**(헤더가 `DoClose`를 Alloy 스타일에만 부른다고 밝힘). 마우스 좌표에 창 장식의 오프셋이 있었습니다((50, 60)이 (41, 50)). 창 제목은 CEF가 `<title> - Chromium`으로 자동 설정했습니다.
- **Alloy 스타일**: `get_runtime_style()`이 `2`.
  - `do_close`가 호출되고 `True`를 돌려주면 닫기가 취소됩니다(`running`이 계속 참). 이후 `False`를 돌려주면 `on_before_close`로 이어지고 종료됩니다.
  - 마우스 좌표는 정확합니다((50, 60)이 (50, 60)).
  - **첫 프레임이 렌더링되기 전에 보낸 입력은 버려집니다.** 로드 직후의 클릭은 (3번 모두) 도착하지 않았고, 이어서 페이지의 `requestAnimationFrame` 콜백이 불린 뒤의 클릭은 도착했습니다. 처음에는 포커스 문제로 짐작했으나 `document.hasFocus()`가 처음부터 참이었고 `set_focus` 없이도 시간이 지난 뒤에는 도착해서 아니었습니다.
  - CEF가 만든 800x600 최상위 창이 **제목 없이** 뜹니다. 래퍼가 X11로 설정하게 했고, 루트의 자식 창에 `_NET_WM_NAME`이 있는 것을 `xwininfo`로 확인했습니다.
- **영향**: 래퍼는 Alloy 스타일만 만듭니다([설계 결정 기록](design-decisions.md)). 시험이 스타일(`== 2`), `do_close`의 거부, 창 제목, 마우스를 지킵니다. Alloy 스타일에서의 네이티브 Wayland는 확인하지 못했습니다([알려진 제약과 미검증 항목](known-constraints.md)).

## F19. 리소스 핸들러 콜백의 스레드

- **방법**: `create`, `open`, `get_response_headers`, `read` 안에서 `threading.get_ident()`를 기록했습니다.
- **결과**: 네 곳 모두 메인 스레드와 다른 스레드에서 실행되었습니다. 스레드 이름은 `Dummy-1`~`5`로(Python이 만든 스레드가 아님) 호출마다 다를 수 있었습니다. 헤더가 말하는 IO 스레드인지는 이름으로 구별하지 못했습니다.

## F20. shutdown() 뒤 initialize()

- **방법**: 같은 프로세스에서 `shutdown()` 뒤 새 `CefApp().initialize()`를 호출했습니다.
- **결과**: 세그멘테이션 오류(종료 코드 139)였습니다. 지금은 `RuntimeError`로 막습니다(`test_initialize_after_shutdown_raises_instead_of_crashing`).

## F21. shutdown() 없이 프로세스가 끝나는 경우

- **방법**: 핸들러(클라이언트, 스킴 팩토리)가 살아 있고 요청이 진행 중인 채로 `shutdown()` 없이 스크립트를 끝냈습니다(5번 반복, 그리고 시험).
- **결과**: 모두 종료 코드 0으로 정상 종료했습니다.

## F22. 팩토리가 거절한 경로

- **방법**: 등록한 호스트에서 한 경로는 핸들러를, 다른 경로는 `None`을 돌려주었습니다.
- **결과**: 핸들러를 준 경로는 200으로 로드되었습니다. `None`을 준 경로는 CEF 기본 처리(네트워크)로 넘어가 `ERR_NAME_NOT_RESOLVED`(-105)로 실패했고 `on_load_error`가 불렸습니다. 시험은 오류 코드는 확인하지 않고 팩토리가 물었는지와 오류의 URL만 확인합니다(네트워크 환경에 따라 코드가 다를 수 있기 때문).

## F23. 다른 CEF 버전의 헤더로 생성

- **방법**: 147.0.14와 152.0.12의 `minimal` 배포본에서 `include/`만 받아 현재 범위로 생성기를 실행하고, 생성한 프록시 헤더, Cython 확장(`cython` 후 `c++ -fsyntax-only`), 래퍼의 손으로 쓴 소스 5개를 해당 버전의 헤더로 컴파일했습니다.
- **결과**: 154, 152, 147 모두 생성되고 전부 컴파일되었습니다. 생성 결과는 첫 줄의 버전 표기만 달랐습니다(현재 범위의 API는 147에서 154까지 같음). 해당 버전의 `libcef`로 실제 실행하지는 않았습니다.

## F24. manylinux

- **방법**: `auditwheel show dist/cefweaver-*.whl`.
- **결과**: 허용되는 태그가 `linux_x86_64`뿐입니다. wheel이 빌드 호스트(Ubuntu, glibc 2.43)의 `GLIBC_2.43` 등을 참조하고, `libcef`가 manylinux 허용 목록 밖의 `libnss3`, `libdbus-1`, `libasound`, `libudev`, `libsystemd`, `libgnutls` 등을 요구합니다.

## F25. GIL을 놓지 않으면 교착한다

- **방법**: `shutdown()`의 `with nogil`을 지운 변형 빌드와 정상 빌드에서 같은 시나리오를 실행했습니다. 끝나지 않는 응답(`read`가 계속 데이터를 돌려줌)을 IO 쪽 스레드가 읽는 중에 `shutdown()`을 호출하고, `faulthandler.dump_traceback_later(25)`로 감시했습니다.
- **결과**: 정상 빌드는 0.03초에 끝났고 그 사이에도 Python 콜백이 계속 불렸습니다(읽기 165회에서 338회). 변형 빌드는 3번 모두 `shutdown()`에서 반환하지 않아 25초에 감시 타이머가 프로세스를 끝냈습니다. 규칙(CEF를 부르는 호출은 GIL을 놓는다)이 필요하다는 근거입니다.

## F26. 문자열 벡터와 프레임

- **방법**: `browser.get_frame_names()`, `get_frame_identifiers()`(라이브러리의 출력 인자)와 `on_favicon_url_change`(핸들러의 입력)를 실행했습니다.
- **결과**: 둘 다 `list[str]`로 오고 내용이 맞습니다(프레임 이름 `inner`, 아이콘 URL `http://fav.test/icon.png`). 이름 목록의 순서는 일정하지 않았습니다. 식별자는 `5-<16진수>` 꼴의 문자열입니다.
- **부수 발견**: `<iframe srcdoc=...>`가 들어 있는 `data:` 페이지는 시작 URL이든 `load_url`이든 **로드가 끝나지 않습니다**(`on_load_end`가 오지 않고 로딩 상태가 계속 참). 같은 iframe이 `http://` 페이지(`add_resource`)나 `src='about:blank'`이면 정상입니다. 원인은 조사하지 않았고, 시험은 `about:blank` iframe을 씁니다.
- **부수 수정**: 핸들러가 받는 문자열, 구조체, 목록은 `optional_param` 표시와 상관없이 `None`이 아니라 값(빈 값 포함)으로 옵니다. 스텁이 `title: str | None`처럼 잘못 적었던 5곳을 고쳤습니다. 라이브러리 메서드의 입력만 `None`을 허용합니다.

## 관련 페이지

- [알려진 제약과 미검증 항목](known-constraints.md)
- [설계 결정 기록](design-decisions.md)
- [충돌 조사 방법](../procedures/debug-crashes.md)
