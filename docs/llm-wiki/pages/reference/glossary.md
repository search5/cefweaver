---
title: 용어집
type: reference
sources:
  - README.rst
  - CLAUDE.md
  - tools/gen/typesys.py
  - tools/prepare.py
updated: 2026-10-08
---

# 용어집

| 용어 | 뜻 |
| --- | --- |
| CEF | Chromium Embedded Framework. Chromium을 다른 응용에 넣는 프레임워크 |
| `libcef.so` | CEF 본체 공유 라이브러리. 이 프로젝트는 컴파일하지 않고 배포본의 것을 씁니다. |
| `libcef_dll_wrapper` | CEF C++ API를 C API(`libcef`)에 연결하는 래퍼 라이브러리. 배포본의 소스를 컴파일합니다. |
| CEF 배포본 (binary distribution) | `cef_binary_<버전>_<플랫폼>/`. `include/`, `Release/`, `Resources/`, `libcef_dll/`, `cmake/`를 가진 디렉터리 |
| `standard` 배포본 | CEF 빌드 서버가 제공하는 완전한 배포본. 이 프로젝트가 쓰는 종류입니다(`minimal`, `client`는 안 씀). |
| prebuilt | 미리 만들어진 배포본을 내려받아 쓰는 것 |
| 소스 빌드 | Chromium과 CEF를 직접 컴파일해서 배포본을 만드는 것(`--build-cef`) |
| `CEF_ROOT` | 사용할 CEF 배포본 디렉터리 |
| `binary_distrib` | 소스 빌드가 배포본을 놓는 곳(`chromium/src/cef/binary_distrib/`) |
| `automate-git.py` | CEF의 빌드 자동화 스크립트 |
| `GN_DEFINES` | Chromium 빌드 구성(GN) 인자를 담는 환경변수 |
| 브라우저 프로세스 | UI와 브라우저를 담당하는 프로세스. 이 프로젝트에서는 Python 프로세스 |
| 렌더러 프로세스 | 웹 페이지(JS)를 실행하는 하위 프로세스 |
| `cefsubprocess` | 렌더러, GPU, 유틸리티 프로세스를 맡는 실행 파일 |
| zygote | Chromium이 하위 프로세스를 포크해서 만들기 위한 프로세스 |
| UI 스레드 | CEF 브라우저 프로세스의 주 스레드. 이 프로젝트에서는 `initialize()`를 부른 Python 스레드 |
| 외부 메시지 펌프 | 사용자 코드가 `CefDoMessageLoopWork()`를 주기적으로 불러 CEF를 구동하는 방식 |
| GIL | Python의 전역 인터프리터 잠금. `with nogil`은 해제, `with gil`은 획득 |
| 트램펄린 | CEF가 부르는 C 함수로, GIL을 얻어 Python 메서드를 부르고 예외를 가두는 생성된 Cython 함수 |
| 프록시 (`Cw...Proxy`) | CEF 핸들러 클래스를 상속해 호출을 함수 포인터 표로 위임하는 생성된 C++ 클래스 |
| 라이브러리 쪽 (library-side) | CEF가 구현하고 애플리케이션이 부르는 클래스(`CefRequest` 등). 헤더의 `source=library` |
| 클라이언트 쪽 (client-side) | 애플리케이션이 구현하고 CEF가 부르는 클래스(핸들러). 헤더의 `source=client` |
| 종류 (kind) | 생성기가 C++ 타입을 분류한 결과(`Prim`, `Str`, `Enum`, `LibRef`, `ClientRef`, `Buffer`, `Void`) |
| 범위 (scope) | 지금 생성하는 클래스와 함수의 목록(`tools/gen/scope.py`) |
| 커버리지 보고서 | 생성하지 못한 메서드와 그 사유([커버리지 보고서](coverage-report.md)) |
| `optional_param` | 헤더가 인자를 `None`(널)을 허용한다고 표시한 것 |
| 순수 가상 함수 | `= 0`으로 선언된 가상 함수. 기반 클래스에 구현이 없어 호출할 수 없습니다. |
| 스테이징 | CEF 런타임과 `cefsubprocess`를 `cefweaver/` 아래에 복사하는 일(`prepare.py`) |
| `strip` | 실행 파일과 라이브러리에서 디버그 심볼을 제거하는 도구 |
| API 해시 | `cef_api_hash()`가 돌려주는 값. API 버전 설정과 `libcef`와 헤더의 일치 확인에 씁니다. |
| 스킴 핸들러 | 특정 URL 스킴(과 도메인)의 요청에 응답하는 CEF 확장 지점(`CefSchemeHandlerFactory`) |
| Xvfb | 화면 없이 동작하는 가상 X 서버. 시험에서 창이 실제 화면에 뜨지 않게 합니다. |
| Ozone | Chromium의 창 시스템 추상화. `--ozone-platform=x11`/`wayland`로 선택합니다. |
| XWayland | Wayland 세션에서 X11 응용을 실행하는 호환 계층 |
| 스택 보호값 (canary) | 스택 오버플로를 탐지하려고 함수 진입 때 넣어 두고 반환 때 확인하는 값 |
| llm-wiki | LLM이 작성하고 유지하는 마크다운 위키. 이 디렉터리입니다. |
| ingest, query, lint | 위키의 세 작업: 반영, 질문 답변, 점검([SCHEMA.md](../../SCHEMA.md)) |

## 관련 페이지

- [아키텍처 개요](../concepts/architecture-overview.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [llm-wiki 패턴 요약](../summaries/karpathy-llm-wiki.md)
