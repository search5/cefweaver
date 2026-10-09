---
title: 관련 프로젝트와 그 위키
type: reference
sources:
  - CLAUDE.md
  - tools/gen/vendor/README.txt
  - tools/build_cef.py
updated: 2026-10-08
---

# 관련 프로젝트와 그 위키

cefweaver를 만들 때 참고하는 프로젝트들입니다. `CLAUDE.md`의 규칙에 따라 이 프로젝트들의 코드를 조사할 때는 해당 프로젝트의 `docs/llm-wiki/`를 먼저 읽고, 위키가 가리키는 원본으로 확인합니다. 위키와 원본이 다르면 원본을 따릅니다. 경로는 이 개발 환경의 것입니다.

| 프로젝트 | 무엇인가 | 소스와 위키 | cefweaver에서 참고한 것 |
| --- | --- | --- | --- |
| cefpython | CEF의 Python 바인딩(Cython, C++). 같은 목적의 앞선 프로젝트 | `/home/jiho/cef_framework/cefpython/`, 위키 `docs/llm-wiki/` | 단일 Cython 모듈 구조(`src/cefpython.pyx`가 `.pyx` 약 47개를 `include`), `libcef.so`를 `RTLD_GLOBAL`로 먼저 올리는 `__init__.py`, `automate.py --build-cef`, CEF 자체 패치(`patches/`), 하위 프로세스(`src/subprocess`) |
| java-cef (JCEF) | CEF의 Java 바인딩(JNI) | `/home/jiho/cef_framework/java-cef/`, 위키 `docs/llm-wiki/` | 모든 핸들러를 사용자 객체로 위임하는 구조(`ClientHandler::GetHandler<T>()`), `jcef_helper`, `DownloadCEF.cmake`와 `CEF_VERSION` 관리, `LD_PRELOAD=libcef.so`, JUnit 시험 구조(`TestSetupExtension`, `TestFrame`) |
| CEF (cef_origin) | CEF 자체의 소스(master 2026-09-29) | `/home/jiho/cef_framework/cef_origin/`, 위키 `docs/llm-wiki/` | `tools/cef_parser.py`(생성기가 복사해 사용), `automate-git.py`와 빌드 문서(`master_build_quick_start.md`, `automated_build_setup.md`), 헤더 주석과 `db/ko/*.json`의 한국어 설명 |

## 이 프로젝트와의 관계

- **cefweaver의 `native/`**의 시작은 다른 프로젝트에서 가져온 `cef-wrapper` 예제입니다([사용하지 않는 코드와 유산](../components/legacy-code.md)).
- 루트 `CMakeLists.txt`와 `cmake/DownloadCEF.cmake`는 CEF 프로젝트 템플릿(`cefsimple`)에서 왔고, java-cef도 같은 파일을 가집니다.
- 생성기의 입력(`build/native/cef/include`)은 실제로 쓰는 CEF 배포본의 헤더입니다. 파서는 CEF 소스의 것을 복사해서 씁니다(`tools/gen/vendor/README.txt`에 출처 커밋).

## 이 위키가 근거로 쓴 조사

이 세 프로젝트를 조사한 결과는 아래 분석 페이지에 정리되어 있습니다. 각 위키의 페이지에서 얻은 사실과, 위키가 가리키는 원본을 직접 읽어 확인한 사실을 구분해서 적었습니다.

- [java-cef 시험과의 비교](../analyses/java-cef-test-comparison.md)
- [API 중계 규모와 생성기 선택](../analyses/api-relay-scale.md)
- [cefpython의 CEF 패치와 cefweaver](../analyses/cefpython-patches.md)

## 참조 시의 주의

- 위키의 서술은 작성 시점의 원본 기준입니다. cefpython 위키는 2017년의 문서와 v66 기준 코드를 반영하고, java-cef 위키는 환경 제약(CEF 바이너리 없음)으로 시험을 실행하지 못했다고 밝힙니다.
- cef_origin은 master(2026-09-29)이고 cefweaver가 쓰는 배포본(154.0.34)보다 새롭습니다. 소스의 세부가 154와 다를 수 있으므로 배포본의 헤더로 확인합니다.

## 관련 페이지

- [llm-wiki 패턴 요약](../summaries/karpathy-llm-wiki.md)
- [설계 결정 기록](design-decisions.md)
