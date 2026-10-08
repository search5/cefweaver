---
title: 패키징
type: component
sources:
  - pyproject.toml
  - MANIFEST.in
  - .gitignore
  - tools/prepare.py
  - cefweaver/__init__.py
updated: 2026-10-08
---

# 패키징

빌드 백엔드는 setuptools이고(`requires = ["setuptools>=77", "Cython>=3.0", "cmake>=3.28.1"]`) 도구는 uv입니다. `setup.py`는 없습니다. Cython 확장을 `pyproject.toml`의 정적 선언 `[[tool.setuptools.ext-modules]]`로 적어서 필요가 없어졌습니다.

## ext-modules 설정

| 항목 | 값 | 이유 |
| --- | --- | --- |
| `name`, `sources` | `cefweaver._cefweaver`, `cefweaver/_cefweaver.pyx` | |
| `language` | `c++` | |
| `include-dirs` | `build/native/cef`, `native/cefwrapper` | CEF 헤더(`prepare.py`가 만든 링크)와 래퍼 헤더 |
| `library-dirs` | `build/native/native/cefwrapper`, `build/native/libcef_dll_wrapper`, `build/native/cef/Release` | 세 라이브러리가 흩어져 있습니다. |
| `libraries` | `cefwrapper`, `cef_dll_wrapper`, `cef`, `X11`(창 제목 설정), `dl`, `pthread` | 정적 라이브러리는 순서가 중요합니다(`cefwrapper`가 `cef_dll_wrapper`를 씀). |
| `define-macros` | `NDEBUG=1`, `_FILE_OFFSET_BITS=64` | 래퍼 라이브러리를 컴파일한 정의(`flags.make`)와 맞춰야 합니다. |
| `extra-compile-args` | `-std=c++20` | CEF 154가 C++20으로 컴파일됩니다. |
| `extra-link-args` | `-Wl,-rpath,$ORIGIN` | 같은 디렉터리의 `libcef.so`를 찾습니다. |
| `depends` | 생성 파일, 래퍼 헤더 두 개, 정적 라이브러리 두 개, `libcef.so` | 아래 참조 |

경로는 모두 저장소 루트 기준 상대 경로이며, **Linux 전용**입니다. 정적 설정 파일에는 플랫폼 조건을 쓸 수 없고 Windows의 라이브러리 이름과 디렉터리가 다르기 때문에, Windows를 지원하려면 설정 방식을 다시 정해야 합니다.

## depends가 필요한 이유

setuptools(distutils)는 `.pyx`와 `.cpp`의 수정 시각만 비교하고 **정적 라이브러리가 바뀐 것은 감지하지 못합니다.** 처음에는 `prepare.py`가 `libcefwrapper.a`를 새로 만들었는데도 이전에 링크한 확장 모듈을 재사용해서, 서브프로세스 경로가 옛 값으로 남은 wheel이 만들어졌습니다. `depends`에 라이브러리와 헤더를 적어 이를 막았습니다.

## package-data

`cefweaver = ["*.so", "*.so.*", "*.pyd", "*.dylib", "*.pak", "*.dat", "*.bin", "*.json", "locales/*", "cefsubprocess", "*.pyi", "py.typed"]`: `prepare.py`가 `cefweaver/`에 복사한 CEF 런타임과 타입 스텁을 wheel에 넣습니다. `.so` 패턴은 확장 모듈과 `libcef.so`에 모두 해당합니다.

## sdist와 `uv build`

- **인자 없는 `uv build`는 실패합니다.** sdist를 먼저 만들고 그 sdist에서 wheel을 만드는데, sdist에는 `build/native/cef`가 없어서 CEF 헤더를 찾지 못합니다(`include/cef_client.h` 없음). 그래서 `uv build --wheel`을 씁니다.
- `MANIFEST.in`은 sdist에서 스테이징된 런타임을 제외합니다. 제외하기 전의 sdist는 약 147MB였고 제외한 뒤 약 9KB입니다.
- sdist 단독으로는 wheel을 만들 수 없습니다.

## git에서 제외되는 파일

`.gitignore`가 `cefweaver/_cefweaver.cpp`(Cython 생성), 스테이징된 런타임(`cefweaver/*.so.*`, `*.pak`, `*.dat`, `*.bin`, `vk_swiftshader_icd.json`, `locales/`, `cefsubprocess`; `libcef.so` 등은 기존의 `*.so`로 제외)을 제외합니다. `cef_binary*`와 `build/`도 제외됩니다.

## wheel의 특성

- 태그는 `cp313-cp313-linux_x86_64`처럼 로컬 플랫폼 태그입니다. PyPI에 올리려면 manylinux 규격이 필요한데, `auditwheel show`는 이 wheel에 `linux_x86_64`만 허용했습니다(빌드 호스트의 glibc 2.43 심볼과, CEF가 요구하는 허용 목록 밖의 시스템 라이브러리 때문. F24).
- 크기: 약 148MB(스테이징 후 `libcef.so`를 strip한 값). 설치하면 약 363MB입니다.

## 메타데이터의 불일치

`pyproject.toml`에는 이 프로젝트의 현재 상태와 맞지 않는 항목이 있습니다. `dependencies = ["numpy>=1.26.2"]`는 코드 어디에서도 쓰이지 않습니다. classifier에는 macOS와 Windows가 있지만 지원하지 않거나 검증하지 못했습니다. `requires-python = ">=3.11"`과 달리 classifier는 3.11과 3.12만 적혀 있습니다(시험은 3.11~3.14에서 했습니다). [알려진 제약과 미검증 항목](../reference/known-constraints.md)에 모았습니다.

## 관련 페이지

- [런타임 파일 배치](../concepts/runtime-layout.md)
- [tools/prepare.py](tool-prepare.md)
- [빌드와 설치](../procedures/build-and-install.md)
