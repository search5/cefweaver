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

- 2026-10-13에 코드와 실행 결과를 근거로 두 라운드의 이중 검증(독립 검증자 2명씩)을 거쳐 서술을 고쳐 썼습니다. 위키는 증거로 쓰지 않았고(낡은 서술이 있었음), 검증 기록은 `log.md`에 있습니다. README의 서술을 바꿀 때도 코드로 확인합니다.
- 목차: 소개, 기능, 문서, 지원 플랫폼, 설치, GUI 툴킷에 페이지 보이기, 예제, 소스에서 빌드, Python API, 프로덕션 준비 상태, 시험, 관련 프로젝트, 라이선스.
- 상태: 2026-10-13에 "프로덕션에 쓸 수 없다"는 한 줄 경고를 "사전 배포(0.1.0)"라는 상태 문단으로 바꿨습니다. 신뢰하는 콘텐츠에 대해 Linux에서 안정성을 시험했다는 사실(549개 시험, 180회 기동, 20분 soak)과, 샌드박스가 없어 신뢰할 수 없는 콘텐츠를 열면 안 된다는 것, 며칠 단위 실행은 시험하지 않았다는 것을 함께 적습니다. 근거는 [프로덕션 배포 가능성](../reference/production-readiness.md)입니다.
- 자동 시험은 세 플랫폼 모두에서 돌렸다고 적고(Windows와 macOS는 개발 컴퓨터 기준, Windows CI 러너는 데스크톱이 없어 일부 실패), 기동 반복과 soak 같은 안정성 시험은 Linux에서만 했다고 구분합니다.
- 기능 절(브라우저, Python과 JavaScript, GUI 툴킷, 미디어와 장치, 패키징)과 "프로덕션 준비 상태" 절(시험 결과 표와 알아 둘 점)을 더했습니다. 수치(클래스 129개, 메서드 1,182개, 시험 549개 등)는 커버리지 보고서와 안정성 시험 기록의 값이므로, 바뀌면 README도 고칩니다.
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
