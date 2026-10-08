# 작업 기록

시간순으로 덧붙이는 기록입니다. 형식은 [SCHEMA.md](SCHEMA.md)를 따릅니다. 기존 항목은 고치지 않습니다.

## [2026-10-08] ingest | 초기 위키 작성

- 카파시의 gist "LLM Wiki"(2026-04-04) 원문을 내려받아 전문을 읽고, 그 패턴(원본, 위키, 스키마의 세 층과 ingest, query, lint 작업, index.md와 log.md)을 이 저장소에 맞게 구성했습니다. 구체적인 구조와 형식은 이미 있는 cefpython과 java-cef의 위키 관례를 따랐습니다.
- 저장소 전체를 조사하여 페이지를 처음 작성했습니다. 조사한 원본: `CMakeLists.txt`, `cmake/`, `native/`, `cefweaver/`, `tools/`(`prepare.py`, `build_cef.py`, `gen/`), `tests/`, `pyproject.toml`, `MANIFEST.in`, `README.rst`, `CLAUDE.md`, `tools/gen/STATUS.md`, `docs/`, git 이력.
- 조사하면서 원본에서 고친 오류: `README.rst`의 `cefsubprocess/` 디렉터리 설명(실행 파일), `_cefweaver.pyx`의 `load_url` docstring(브라우저는 `initialize()` 안에서 만들어짐), `CLAUDE.md`와 `tests/test_smoke.py`의 시험 명령에 `-P` 누락(저장소 루트에서 CEF 시험 11개가 조용히 건너뛰어짐).
- 만든 페이지: concepts 10, components 13, procedures 7, reference 8, summaries 3, analyses 4(총 45개). 목록은 [index.md](index.md)에 있습니다.
- 대화에서 조사한 내용을 `analyses/`로 환원했습니다: java-cef 시험 비교, API 중계 규모, cefpython 패치, Chromium의 Wayland와 X11 동작.
- 실행으로 확인한 사실은 [verified-findings](pages/reference/verified-findings.md)에, 확인하지 못한 항목과 문서의 불일치는 [known-constraints](pages/reference/known-constraints.md)에 모았습니다.
- 확인된 특이사항: `pyproject.toml`의 `numpy` 의존성은 코드에서 쓰이지 않고, `README.rst`는 저장소에 없는 GUI 툴킷 예제를 언급하며, `native/`에 호출되지 않는 코드(`zen://` 핸들러 등)가 남아 있습니다.
- 점검 도구 `lint.py`를 추가했습니다.

## [2026-10-08] ingest | tools/gen의 문서 파일을 위키로 병합

- `tools/gen/STATUS.md`(생성기의 한계와 다음 단계)의 내용을 [생성 범위와 커버리지](pages/reference/generated-api-coverage.md)의 "생성기의 한계와 다음 단계" 절로 옮기고 파일을 삭제했습니다. 내용은 이미 [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [바인딩 생성기의 설계](pages/concepts/binding-generator.md), [설계 결정 기록](pages/reference/design-decisions.md)에 나뉘어 들어 있어서 겹치는 서술을 확인하고 한 곳으로 모았습니다.
- `tools/gen/COVERAGE.txt`(생성기가 만드는 보고서)를 위키 페이지 [커버리지 보고서](pages/reference/coverage-report.md)로 옮겼습니다. `tools/gen/generate.py`가 이 페이지를 직접 쓰며, 내용이 같으면 `updated`를 유지해서 `--check`와 시험(`test_generated_files_are_up_to_date`)이 날짜 때문에 흔들리지 않습니다.
- 요약 페이지 `summaries/readme-claude-status.md`를 `readme-and-claude-md.md`로 바꾸고(STATUS.md 절 삭제) 이 페이지를 가리키던 링크와 색인을 모두 고쳤습니다.
- `tools/gen/vendor/README.txt`와 `vendor/LICENSE.txt`는 옮기지 않았습니다. 복사해 온 CEF 파서의 BSD 라이선스와 출처 표시이므로 코드와 함께 있어야 합니다. 내용의 요약은 [생성기 모듈](pages/components/generator-modules.md)과 [관련 프로젝트](pages/reference/related-projects.md)에 있습니다.
- 변경한 파일: 위키 페이지 19개의 `sources`와 본문, `index.md`, `README.rst`, `CLAUDE.md`, `tools/gen/generate.py`, `docs/llm-wiki/lint.py`.

## [2026-10-08] schema | 생성 페이지를 위한 frontmatter 필드 generated

- 도구가 만드는 페이지를 위해 frontmatter에 선택 필드 `generated: true`를 추가했습니다. 이 페이지는 직접 고치지 않고 200줄 길이 제한에서 제외됩니다([SCHEMA.md](SCHEMA.md)). `lint.py`가 이 필드를 읽습니다.

## [2026-10-08] ingest | CefClient 위임 구조와 로드, 수명 주기, 표시 핸들러

- 사용자가 선택한 다음 단계(1번, TDD)를 구현했습니다. 시험을 먼저 쓰고 실패를 확인한 뒤(생성기 4개, 통합 6개) 구현했고, 변이 시험으로 시험이 구현의 파손을 잡는지 확인했습니다.
- 생성기: `scope.py`에 `CefClient`, `CefLoadHandler`, `CefLifeSpanHandler`, `CefDisplayHandler` 추가, `emit_cpp.py`에 전달 클래스(`Cw<이름>Forward`) 방출. 래퍼: `CefWrapperClientHandler`가 전달 클래스를 상속해 이벤트를 사용자 핸들러로 넘기고, `CefWrapper::SetClient`와 `CefApp.set_client()` 추가.
- 갱신한 페이지: [C++ 핸들러](pages/components/native-handlers.md), [핸들러 프록시 구조](pages/concepts/handler-proxies.md), [생성 범위와 커버리지](pages/reference/generated-api-coverage.md), [Python API 참조](pages/reference/python-api.md), [설계 결정 기록](pages/reference/design-decisions.md), [알려진 제약과 미검증 항목](pages/reference/known-constraints.md), [실험으로 확인한 사실](pages/reference/verified-findings.md)(F15), [시험](pages/components/tests.md), [새 클래스를 생성 범위에 추가하기](pages/procedures/add-class-to-generator.md) 외 개수와 줄 수를 맞춘 페이지.
- 시험은 37개(통합 17, 생성기 19, 위키 1)이고 모두 통과했습니다.
