---
title: 저장소 메타데이터 (문서, 라이선스, third_party)
type: component
sources:
  - README.rst
  - CHANGELOG.rst
  - LICENSE
  - third_party/cef/README.txt
  - tools/buildtools/LICENSE
  - tools/gen/vendor/README.txt
  - .gitignore
  - docs/conf.py
  - docs/Makefile
  - uv.lock
updated: 2026-10-13
---

# 저장소 메타데이터 (문서, 라이선스, third_party)

코드가 아닌 파일들의 현재 상태입니다.

| 파일 | 상태 |
| --- | --- |
| `README.rst` | 프로젝트 소개, 지원 플랫폼, 빌드 방법, Python API 사용 예. 소개 문단은 cefpython의 README를 바탕으로 했습니다. 예제는 `examples/` 아래에 툴킷마다 있습니다(`cocoa`, `gtk3`, `kivy`, `print`, `qt`, `sdl2`, `swiftui`, `tk`, `views`, `wx`와 공용 `common`). |
| `CLAUDE.md` | LLM을 위한 작업 지침([README와 CLAUDE.md 요약](../summaries/readme-and-claude-md.md)) |
| `CHANGELOG.rst` | 비어 있습니다(0바이트). |
| `LICENSE` | BSD 3-Clause, 2023, Jiho Persy Lee. `pyproject.toml`은 `license = "BSD-3-Clause"`입니다. |
| `docs/` | (2026-10-13) Jekyll 사이트(GitHub Pages)를 지우고 **Sphinx 문서**로 바꿨습니다. 테마 `sphinx_rtd_theme`, 확장 `autodoc`, `napoleon`(Google 스타일만), `intersphinx`, `viewcode`, `nitpicky = True`. `index.rst`와 `api/{core,types,ui,toolkits}.rst`가 모듈을 나열하고 내용은 소스의 docstring입니다. 영어가 원문이고 한국어는 `locale/ko/LC_MESSAGES/**/*.po`(gettext, `sphinx-intl update`)입니다. `Makefile`의 `html`(`-W`), `html-all`(en, ko), `gettext`, `update-po`. 툴킷 모듈은 `autodoc_mock_imports`와 `conf.py`의 `ctypes.WinDLL` 대용으로 Linux에서 import합니다(Qt는 열거형 값으로 표를 만들어 PyQt6가 필요). `*.mo`와 `*.pot`, `_build/`는 커밋하지 않습니다. `CHANGELOG.rst`는 비어 있습니다. | 문서 호스팅(Read the Docs 또는 Actions)은 정하지 않았습니다 |
| `uv.lock` | uv의 잠금 파일(약 780줄) |
| `third_party/cef/` | `README.txt`(CEF 배포본이 CMake 구성 중에 이곳에 내려받아진다는 설명)만 커밋됩니다. 내려받은 `cef_binary_*` 디렉터리와 `.tar.bz2`는 `.gitignore`의 `cef_binary*`로 제외됩니다. |
| `tools/buildtools/` | CEF 템플릿에서 가져온 clang-format 내려받기 도구(`download_from_google_storage.py`, `gsutil.py`, `subprocess2.py`, 플랫폼별 `clang-format.sha1`). 옵션 `CEFWEAVER_FETCH_CLANG_FORMAT`를 켰을 때만 쓰입니다. `external_bin/`과 `clang-format` 실행 파일은 무시됩니다. |
| `tools/gen/vendor/` | CEF 파서 복사본과 라이선스([생성기 모듈](generator-modules.md)) |
| `tools/__init__.py`, `tools/gen/__init__.py` | 빈 파일 |
| `.gitignore` | 기본 Python 항목에 CEF(`cef_binary*`, `external_bin`, `clang-format`), 생성 파일(`cefweaver/_cefweaver.cpp`), `cefweaver/cefsubprocess.app/`이 추가되어 있습니다(이제 소스 트리에 스테이징되지 않지만, 남아 있어도 wheel에서 빠집니다. 런타임은 wheel 빌드가 `install()`로 넣습니다). |

## 이력

커밋 이력과 시기별 변화는 [git 이력 요약](../summaries/git-history.md)에 있습니다.

## 관련 페이지

- [패키징](packaging.md)
- [루트 CMake와 CEF 다운로드](root-cmake.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
