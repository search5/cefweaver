---
title: 소스 트리 지도
type: reference
sources:
  - CMakeLists.txt
  - pyproject.toml
  - native/cefwrapper/CMakeLists.txt
  - tools/gen/generate.py
  - .gitignore
updated: 2026-10-08
---

# 소스 트리 지도

저장소 루트의 구성입니다. 파일 수와 줄 수는 2026-10-08 기준 대략값입니다(`tools/gen/vendor/`, `tools/buildtools/` 제외).

```
cefweaver/
  CMakeLists.txt              루트 CMake: CEF 확보, 하위 타깃          [root-cmake]
  cmake/DownloadCEF.cmake     prebuilt 내려받기                        [root-cmake]
  pyproject.toml              빌드 백엔드, 메타데이터, ext-modules     [packaging]
  MANIFEST.in                 sdist에서 런타임 제외                    [packaging]
  uv.lock, LICENSE, README.rst, CHANGELOG.rst (비어 있음)              [repo-metadata]
  CLAUDE.md                   LLM 작업 지침                            [summaries]
  native/
    cefwrapper/               C++ 래퍼(정적 라이브러리 libcefwrapper.a)
      library.h, library.cpp  CefWrapper 클래스                        [native-library-api]
      cef_wrapper_app.*       CefApp                                    [native-handlers]
      cef_wrapper_browser_process_handler.*
      cef_wrapper_client_handler.* (+ _linux.cc, _win.cc)
      cef_wrapper_render_process_handler.*
      javascript_binding.h, javascript_python_binding_handler.h, javascript_bindings_handler.h
      custom_protocol_scheme_handler.*, file_util.h  (사용하지 않음)   [legacy-code]
      global_vars.h
      generated/cefweaver_proxies.h   (생성)                           [generated-files]
      CMakeLists.txt
    cefsubprocess/            서브프로세스 실행 파일                   [native-cefsubprocess]
  cefweaver/                  Python 패키지
    __init__.py               libcef 선로드, 공개 이름                 [cython-extension]
    _cefweaver.pyx            확장 모듈 본체(손으로 씀)
    cefwrapper.pxd            CefWrapper 선언(손으로 씀)
    cef_api.pxd, cef_api.pxi, _cefweaver.pyi, py.typed   (생성)
    (스테이징된 런타임: libcef.so, *.pak, icudtl.dat, locales/, cefsubprocess ... 은 git 제외)
  tools/
    prepare.py                CEF 확보, 빌드, 스테이징                 [tool-prepare]
    build_cef.py              CEF 소스 빌드                            [tool-build-cef]
    gen/                      바인딩 생성기                            [generator-modules]
      vendor/                 CEF 파서 복사본
      handwritten.pyi         CefApp의 타입 스텁(손으로 씀)
    buildtools/               clang-format 내려받기(옵션)              [repo-metadata]
  tests/
    test_smoke.py, test_generator.py                                   [tests]
  docs/
    conf.py, index.rst, Makefile, make.bat   Sphinx 골격
    llm-wiki/                 이 위키
  third_party/cef/            CEF 배포본 내려받는 곳(README.txt만 커밋)
  build/                      빌드 산출물(git 제외)
    native/                   CMake 빌드, build/native/cef 링크, cef_index.json, prepare.json
    cef_src/                  --build-cef의 소스와 빌드
```

| 코드의 종류 | 위치 | 편집 |
| --- | --- | --- |
| 손으로 쓴 C++ | `native/cefwrapper/`(생성 폴더 제외), `native/cefsubprocess/` | 직접 |
| 손으로 쓴 Cython | `cefweaver/_cefweaver.pyx`, `cefwrapper.pxd` | 직접 |
| 생성된 파일 | `native/cefwrapper/generated/`, `cefweaver/cef_api.*`, `cefweaver/_cefweaver.pyi`, `docs/llm-wiki/pages/reference/coverage-report.md` | **생성기로만** |
| 생성기 | `tools/gen/*.py` | 직접 |
| 빌드와 도구 | `CMakeLists.txt`, `cmake/`, `tools/prepare.py`, `tools/build_cef.py`, `pyproject.toml` | 직접 |

대괄호는 이 위키의 해당 페이지 이름입니다. 파일을 고치면 그 페이지를 함께 고칩니다([SCHEMA.md](../../SCHEMA.md)의 ingest 절차).

## 관련 페이지

- [아키텍처 개요](../concepts/architecture-overview.md)
- [생성되는 파일](../components/generated-files.md)
- [패키징](../components/packaging.md)
- [용어집](glossary.md)
