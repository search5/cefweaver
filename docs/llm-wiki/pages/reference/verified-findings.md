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

## 관련 페이지

- [알려진 제약과 미검증 항목](known-constraints.md)
- [설계 결정 기록](design-decisions.md)
- [충돌 조사 방법](../procedures/debug-crashes.md)
