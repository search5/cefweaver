---
title: README와 CLAUDE.md 요약
type: summary
sources:
  - README.rst
  - CLAUDE.md
updated: 2026-10-13
---

# README와 CLAUDE.md 요약

## README.rst

프로젝트 소개와 사용법입니다. 2026-10-13에 cefpython의 README 구성(목차, 소개, 설치, 예제, 문서)을 참고해 다시 썼습니다.

- 목차: 소개, 문서, 지원 플랫폼, 설치, GUI 툴킷에 페이지 보이기, 예제, 소스에서 빌드, Python API, 관련 프로젝트, 라이선스.
- 상태: 개발 중이며 프로덕션용이 아니라고 밝힙니다.
- **문서 사이트(GitHub Pages)**: 영어 https://search5.github.io/cefweaver/en/index.html, 한국어 https://search5.github.io/cefweaver/ko/index.html. 자매 프로젝트 cefloom의 사이트는 https://search5.github.io/cefloom/ 입니다(관련 프로젝트에 링크).
- 지원 플랫폼 표: Linux x86_64, macOS arm64, Windows 11 x86_64(모두 개발 중). Python 3.11 이상.
- 설치: PyPI에 없고(프로젝트 페이지가 404) GitHub 릴리스도 없어서 소스에서 wheel을 빌드해 설치한다고 씁니다. 툴킷은 선택 의존성(`cefweaver[qt]` 등).
- 예제: `examples/` 폴더별 표(툴킷 11개, Views, 인쇄, Cocoa, SwiftUI, common).
- 빌드: `python tools/prepare.py`(prebuilt, `--cef-root`, `--build-cef`), 다음에 `uv build --wheel`. `--list-versions`와 `--cef-version`, 소스 빌드의 요구 자원과 `--dry-run`.
- Python API 예: `CefApp`, `add_javascript_binding`, `add_resource`, 생성된 PEP 8 래퍼, 메시지 펌프 설명, 런타임 파일 배치.
- 라이선스: BSD 3-Clause(`LICENSE`).
- `tests/test_ui.py`가 README의 Tk 빠른 시작 코드가 `examples/tk/quickstart.py`와 같은지 확인하므로, 그 코드를 고칠 때는 둘을 함께 고칩니다.

## CLAUDE.md

저장소에서 일하는 Claude Code를 위한 지침입니다([SCHEMA.md](../../SCHEMA.md)와 함께 위키의 스키마 층입니다).

1. **다른 프로젝트의 코드는 그 프로젝트의 llm-wiki를 우선 참조**합니다(cefpython, java-cef, cef_origin 위치 표). 위키가 가리키는 원본으로 검증하고, 다르면 원본을 따르며 차이를 알립니다([관련 프로젝트](../reference/related-projects.md)).
2. **빌드와 시험 명령**: `prepare.py`, `uv build --wheel`, `env -u WAYLAND_DISPLAY xvfb-run -a python -P -m unittest discover -s tests -v`. `-P`가 필수인 이유, 가상 X 서버가 필요한 이유, 지원 플랫폼.
3. **바인딩 생성기**: 명령 세 가지, 생성 파일 목록(직접 고치지 않음), 범위, 타입, 이름 규칙, 시그니처 규칙, 핸들러, GIL, 초기화 전 호출 안전성([바인딩 생성기의 설계](../concepts/binding-generator.md)).
4. **시험 작성 원칙**: 조건 기다리기, CEF 시험은 프로세스 분리, 외부 네트워크 금지(`add_resource`), 정상 종료까지 확인.
5. **이 저장소의 위키**: `llm-wiki/`를 유지하는 규칙(질문 전에 `index.md`, 코드를 바꾸면 같은 작업에서 위키 갱신, 가치 있는 답변은 `analyses/`에 저장, `lint.py` 점검). 상세는 SCHEMA.md에 있습니다.

## 관련 페이지

- [llm-wiki 패턴 요약](karpathy-llm-wiki.md)
- [git 이력 요약](git-history.md)
- [생성기의 한계와 다음 단계](../reference/generated-api-coverage.md)
