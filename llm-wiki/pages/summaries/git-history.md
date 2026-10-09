---
title: git 이력 요약
type: summary
sources:
  - pyproject.toml
  - README.rst
  - CMakeLists.txt
  - tools/prepare.py
  - tools/gen/generate.py
updated: 2026-10-08
---

# git 이력 요약

`git log`로 확인한 커밋 흐름입니다. 2026-10-08에 작성했고 그때의 최신 커밋은 `f9e459c`입니다. 이후 커밋은 `git log`로 확인합니다. 커밋 메시지에 적힌 내용만 요약하며, 메시지에 없는 동작 여부는 추정하지 않습니다.

| 시기 | 커밋 | 내용 |
| --- | --- | --- |
| 2023-04 | `3db779c`~`7fa082d` | 저장소 시작, README, 초기 구현(커밋 메시지: initial skeleton code) |
| 2023-12-11~15 | `e7466c5`, `c7447f1`, `49716df` | Poetry 기반 빌드 도구와 CMake 시험 |
| 2023-12-18 | `03675db`~`8ef0382` | `libcef_dll_wrapper` 빌드 확인, native 개발 기반, clang-format.exe를 관리에서 제외, Sphinx 문서화 도구 추가, Poetry 빌드에서 CMake 제거 |
| 2024-01-02 | `8471fdb`, `fd85f7f` | `cef-wrapper`를 가져와 샘플 시험, 경로 찾는 부분을 제외하고 완전 컴파일에 가깝게 수정 |
| 2024-10-24 | `6423c2c` | README 갱신 |
| 2026-10-07 | `8f8291e`, `8bcbef1` | 프로젝트 이름을 cefweaver로 통일하고 메타데이터 정정, 빌드 시스템을 Poetry에서 setuptools 백엔드와 uv로 전환 |
| 2026-10-08 | `cab5e43` | Linux 지원과 Cython 확장 모듈, CEF 확보 도구(`prepare.py`, `build_cef.py`, 버전 조회와 캐시) 추가 |
| 2026-10-08 | `69a09a7` | 시험을 조건 기반 대기로 정리하고 `CLAUDE.md` 추가 |
| 2026-10-08 | `f9e459c` | CEF 헤더에서 Python 바인딩을 생성하는 도구와 리소스 핸들러 추가 |

## 읽을 수 있는 흐름

1. 2023년: Poetry와 CMake로 CEF 래퍼를 빌드하는 기반을 만들었습니다.
2. 2024년 초: 다른 프로젝트의 `cef-wrapper`를 가져와 샘플 시험을 하고 컴파일되도록 고쳤습니다(커밋 메시지 기준).
3. 2026-10: 빌드 시스템을 setuptools와 uv로 바꾸고, Linux에서 처음으로 끝까지 동작하게 만들었으며, CEF 확보 도구와 바인딩 생성기를 추가했습니다.

작성자 이름은 시기에 따라 `Jiho Persy Lee`, `Jiho Lee`, `이지호`, `Ji-ho Lee`로 다르게 나타납니다. 커밋 메시지는 2024년부터 한국어입니다.

## 관련 페이지

- [설계 결정 기록](../reference/design-decisions.md)
- [저장소 메타데이터](../components/repo-metadata.md)
- [README와 CLAUDE.md 요약](readme-and-claude-md.md)
