# 위키 목차

모든 페이지의 한 줄 요약 목록입니다. 질문에 답할 때 가장 먼저 읽습니다. 규칙은 [SCHEMA.md](SCHEMA.md), 기록은 [log.md](log.md), 안내는 [README.md](README.md)에 있습니다.

## 개념 (concepts)

- [아키텍처 개요](pages/concepts/architecture-overview.md): 계층 구조, 두 갈래의 Python 인터페이스, 빌드 흐름의 전체 그림
- [바인딩 생성기의 설계](pages/concepts/binding-generator.md): CEF 헤더에서 바인딩을 생성하는 파이프라인, 타입 종류, 규칙, 범위
- [CEF 확보 방식](pages/concepts/cef-acquisition.md): prebuilt, 기존 배포본, 소스 빌드의 세 가지 확보 방식
- [핸들러 프록시 구조](pages/concepts/handler-proxies.md): 핸들러를 Python 객체로 위임하는 함수 포인터 표와 프록시, 래퍼의 핸들러가 이벤트를 넘기는 전달 클래스, 값 전달 규칙
- [JavaScript 바인딩](pages/concepts/javascript-bindings.md): JS에서 Python 콜백까지의 여섯 단계, 값 변환, 이름만 보내는 이유
- [수명 주기와 메시지 루프](pages/concepts/lifecycle-and-message-loop.md): initialize, 외부 메시지 펌프, 창 닫기, shutdown의 순서와 상태
- [플랫폼 지원 현황](pages/concepts/platform-support.md): Linux, Windows, macOS, ARM의 지원 상태와 근거
- [프로세스 모델과 스레드](pages/concepts/process-model-and-threads.md): 브라우저 프로세스는 Python 프로세스, 서브프로세스, UI 스레드와 GIL 규칙
- [리소스 제공 (스킴 핸들러와 add_resource)](pages/concepts/resource-serving.md): 스킴 핸들러와 add_resource로 네트워크 없이 페이지 제공
- [런타임 파일 배치](pages/concepts/runtime-layout.md): libcef.so와 리소스를 같은 디렉터리에 두는 이유와 배치

## 구성요소 (components)

- [Cython 확장 모듈 (_cefweaver)](pages/components/cython-extension.md): _cefweaver.pyx, cefwrapper.pxd, __init__.py의 구성과 CefApp 내부
- [생성되는 파일](pages/components/generated-files.md): 생성기가 만드는 다섯 파일과 새로 고치고 확인하는 방법
- [생성기 모듈 (tools/gen)](pages/components/generator-modules.md): tools/gen의 모듈별 역할과 의존 방향
- [사용하지 않는 코드와 유산](pages/components/legacy-code.md): 호출되지 않는 코드와 원래 환경에 고정된 부분
- [cefsubprocess 실행 파일](pages/components/native-cefsubprocess.md): 서브프로세스 실행 파일, 플랫폼별 main, no_stack_protector
- [C++ 핸들러](pages/components/native-handlers.md): CefWrapperApp, 브라우저 프로세스, 클라이언트(사용자 Client로 이벤트 위임과 순서), 렌더러 핸들러
- [CefWrapper 클래스](pages/components/native-library-api.md): CefWrapper 클래스의 메서드, 경로 함수, 전역 상태, 약점
- [패키징](pages/components/packaging.md): ext-modules 설정, depends, package-data, sdist와 uv build
- [저장소 메타데이터 (문서, 라이선스, third_party)](pages/components/repo-metadata.md): README, LICENSE, docs/, third_party, tools/buildtools 등의 상태
- [루트 CMake와 CEF 다운로드](pages/components/root-cmake.md): 루트 CMakeLists.txt, DownloadCEF.cmake, 네이티브 타깃의 CMake
- [시험 (tests/)](pages/components/tests.md): tests/의 시험 304개(통합, 생성기, 위키 점검)와 설계 원칙
- [tools/build_cef.py](pages/components/tool-build-cef.md): tools/build_cef.py의 소스 빌드 흐름, 명령, GN_DEFINES, 한계
- [tools/prepare.py](pages/components/tool-prepare.md): tools/prepare.py의 흐름, 옵션, 버전 조회, 스테이징

## 절차 (procedures)

- [새 클래스를 생성 범위에 추가하기](pages/procedures/add-class-to-generator.md): scope.py에 클래스를 추가하고 확인하는 절차와 한계
- [새 타입 지원 추가하기](pages/procedures/add-type-to-generator.md): 새 타입 종류를 지원하려고 고칠 곳과 설계 질문
- [빌드와 설치](pages/procedures/build-and-install.md): prepare.py, uv build --wheel, 설치와 자주 만난 문제
- [CEF의 한계를 CEF 예제로 검증하기](pages/procedures/verify-cef-limits.md): "CEF의 한계"라고 적기 전에 `cefsimple`과 CEF 소스로 가르는 방법과 지금까지의 검증 결과
- [충돌 조사 방법](pages/procedures/debug-crashes.md): 서브프로세스 충돌을 조사할 때 효과가 있었던 방법과 쓸 수 없었던 방법
- [CEF 확보하기](pages/procedures/obtain-cef.md): 버전 조회, prebuilt, 기존 배포본, 소스 빌드 명령
- [시험 실행하기](pages/procedures/run-tests.md): -P가 필수인 시험 실행 명령, 일부 실행, 여러 Python 버전
- [CEF 버전 올리기](pages/procedures/update-cef-version.md): 기본 버전 변경, 재생성, 시험, 120에서 154로 올릴 때의 관찰

## 참조 (reference)

- [설계 결정 기록](pages/reference/design-decisions.md): 빌드, 바인딩, 런타임, 시험, 저장소 운영의 결정과 이유
- [생성 범위와 커버리지](pages/reference/generated-api-coverage.md): 지금 생성되는 402+3개와 제외 52개, 전체 89% 중 남은 장애물, 생성기의 한계와 다음 단계
- [커버리지 보고서 (생성됨)](pages/reference/coverage-report.md): 생성기가 쓰는 보고서 전문(제외된 메서드의 사유, 클래스별 지원 비율)
- [용어집](pages/reference/glossary.md): CEF, 프로세스, 생성기, 위키 용어 정의
- [알려진 제약과 미검증 항목](pages/reference/known-constraints.md): 미검증 항목, 한계, 문서와 메타데이터의 불일치, 환경 제약
- [types 모듈 (열거형과 값 타입)](pages/reference/types-module.md): 헤더에서 만든 IntEnum, IntFlag, NamedTuple, 이름과 값을 읽는 규칙, 정수와 튜플과의 호환
- [Python API 참조](pages/reference/python-api.md): CefApp의 메서드 표(set_client 포함)와 생성된 이름, 규칙, 브라우저 이벤트 받기 예
- [관련 프로젝트와 그 위키](pages/reference/related-projects.md): cefpython, java-cef, CEF와 그 위키, 참고한 것
- [소스 트리 지도](pages/reference/source-tree-map.md): 저장소 트리와 파일 종류별 편집 방법
- [실험으로 확인한 사실](pages/reference/verified-findings.md): 실행해서 확인한 14가지 사실(방법, 결과, 영향)
- [실험으로 확인한 사실 2 (핸들러, 호스트, 스타일, 생성기)](pages/reference/verified-findings-api.md): F15~F33. 클라이언트 위임, 구조체, 호스트, Alloy와 Chrome, 스레드, 재초기화, GIL 교착, srcdoc 문제, types 모듈
- [실행해서 확인한 핸들러 (F55부터)](pages/reference/verified-findings-handlers.md): 렌더러 종료, 새 탭과 외부 프로토콜, 인증서 오류, 요청 컨텍스트 핸들러, 설정(F58), 버전(F59), 브라우저 여러 개(F60), 메시지 펌프(F62), 스레드 작업(F63), 브라우저 설정(F64), JavascriptBridge(F65), 공유 텍스처(F66), GTK 3 예제(F67), 오프스크린 키와 터치와 IME와 팝업, 한글 조합(F56), 교차 사이트 iframe과 그 수정(F57), 툴킷 예제(F69)
- [실험으로 확인한 사실 (F36부터)](pages/reference/verified-findings-more.md): 오프스크린, 구조체, 바이트열, 핸들러, 스트림, 시간, 인자 무시 등
- [GTK 3 예제 (오프스크린 위젯)](pages/reference/gtk3-example.md): `examples/gtk3/`의 위젯과 uv 환경, 실제로 돌려 확인한 것(27개 점검: 입력, 한글, 복사와 붙여넣기, 드래그 앤 드롭, HiDPI), 발견한 결함과 우회
- [툴킷 예제 (Qt, Tkinter, SDL2, wxPython, Kivy)](pages/reference/toolkit-examples.md): `examples/`의 다섯 예제(PyQt6와 PySide6 포함)의 공통 구조(`common/demo.py`, `common/checks.py`), 툴킷별 차이, 모두 통과한 점검, 툴킷이 드러낸 것(클립보드, 드래그 시작, 드롭의 경합)과 확인하지 못한 것
- [공유 텍스처 (GPU 가속 페인트)](pages/reference/shared-textures.md): `shared_texture`, `on_accelerated_paint`, `AcceleratedPaintInfo`, `read_plane`, 규칙과 GPU 환경, 픽셀 내용을 확인하지 못한 것
- [JavascriptBridge](pages/reference/javascript-bridge.md): JSON으로 Python 함수를 페이지에 노출(`Promise`, 콜백, `execute_function`, `evaluate`, `origins`), 렌더러에 Python 없이 메시지 라우터 위에서 동작
- [메시지 라우터 (window.cefQuery)](pages/reference/message-router.md): `QueryHandler`와 `QueryCallback`, 렌더러와 브라우저 쪽 연결, 제약
- [오프스크린 렌더링](pages/reference/offscreen-rendering.md): `offscreen`, `RenderHandler.on_paint`의 읽기 전용 버퍼, 제약
- [스트림과 ZIP 읽기](pages/reference/streams.md): `fread`/`fwrite` 규약(`ptr, size, n`)을 `read(n, size=1)`, `write(data, size=1)`로 연 규칙과 핸들러
- [바이트열과 시간](pages/reference/bytes-and-times.md): `void*` 표(복사, 크기가 앞, 의도적 제외)와 `CefBaseTime` → `datetime`
- [java-cef 동등성 (바닥과 그 위)](pages/reference/java-cef-parity.md): java-cef가 여는 것이 바닥, 격차와 바닥 위 목록
- [앱 핸들러 (명령줄, 스킴, 시작 훅)](pages/reference/app-handler.md): `AppHandler`와 `SchemeRegistrar`, `CommandLine`, 사용자 스킴의 렌더러 전파

## 요약 (summaries)

- [git 이력 요약](pages/summaries/git-history.md): 커밋 이력의 시기별 흐름
- [llm-wiki 패턴 요약 (카파시)](pages/summaries/karpathy-llm-wiki.md): 카파시의 llm-wiki 패턴 요약과 이 위키의 대응
- [README와 CLAUDE.md 요약](pages/summaries/readme-and-claude-md.md): README.rst와 CLAUDE.md의 내용 요약

## 분석 (analyses)

- [API 중계 규모와 생성기 선택](pages/analyses/api-relay-scale.md): CEF, java-cef, cefpython의 규모와 생성기를 고른 근거
- [cefpython과 cefweaver의 API 차이](pages/analyses/cefpython-comparison.md): cefpython의 API 459개와 대조한 결과(창 임베딩, JS 바인딩, 렌더러의 Python 등 없는 것, 이름만 다른 것, cefweaver에만 있는 것)
- [cefpython의 CEF 패치와 cefweaver](pages/analyses/cefpython-patches.md): cefpython의 CEF 패치가 현재 CEF에 적용되는지, 가져오지 않은 이유
- [래퍼와 사용자가 핸들러를 나눠 쓰는 방법](pages/analyses/sharing-handlers-with-the-wrapper.md): 핸들러를 분리할 수 없는 이유, 컨텍스트 메뉴의 결정과 구현(순서, ID, 기본 끔), 프로세스 메시지(이름으로 나눔, 진단용 ping/pong)
- [JavaScript와 호스트 사이의 통신 (java-cef, cefpython과 비교)](pages/analyses/js-python-messaging.md): 세 프로젝트의 중계 방식 비교, 메시지 라우터 도입 선택지, 열지 못한 BinaryValue와 공유 메모리
- [Chromium의 Wayland와 X11 동작](pages/analyses/chromium-on-wayland.md): 네이티브 Wayland와 XWayland에서 Chromium 동작 실험
- [java-cef 시험과의 비교](pages/analyses/java-cef-test-comparison.md): java-cef 시험 구조 조사, cefweaver와의 비교, 채택한 것
