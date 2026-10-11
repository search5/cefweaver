---
title: 빌드와 설치
type: procedure
sources:
  - README.rst
  - CLAUDE.md
  - tools/prepare.py
  - pyproject.toml
  - cmake/CefweaverExtension.cmake
updated: 2026-10-11
---

# 빌드와 설치

Linux x86_64 기준입니다. 이 절차를 Python 3.11, 3.12, 3.13, 3.14에서 실행해서 확인했습니다.

## 준비물

- Linux x86_64, C++ 컴파일러(C++20 필요), CMake 3.19 이상, [uv](https://docs.astral.sh/uv/)
- Python 3.11 이상(`requires-python`)
- CEF를 내려받을 네트워크(prebuilt 사용 시)와 디스크 여유. 154 배포본은 압축본이 약 690MB(689,351,019바이트)이고 푼 디렉터리는 약 3.2GB입니다. `build/`는 약 3GB까지 커집니다.
- 시험하려면 `xvfb`(가상 X 서버)

## macOS (Apple Silicon)

같은 절차입니다(`python tools/prepare.py`, `CEF_ROOT=$PWD/build/native/cef uv build --wheel`). 준비물은 Xcode(또는 Command Line Tools)의 clang, CMake, uv입니다. Ninja는 필요 없습니다(Unix Makefiles). CEF는 `macosarm64` 배포본(압축 약 307 MB, 푼 것 약 791 MB)을 받습니다. 결과는 `macosx_12_0_arm64` wheel(약 147 MB, 안에 `cefsubprocess.app`)입니다. 앱 번들은 `prepare.py`가 아니라 wheel 빌드(CMake의 `install()`)가 넣습니다. `python.org`의 Python으로 `--list-versions`가 실패하면 [tools/prepare.py](../components/tool-prepare.md)를 보세요. 확인한 환경은 [F79](../reference/verified-findings-macos.md)에 있습니다.

## 절차

1. **사전 준비**(선택): CEF 확보와 네이티브 빌드

   ```sh
   python tools/prepare.py
   ```

   `build/native/`에 `libcef_dll_wrapper.a`, `libcefwrapper.a`, `cefsubprocess`가 만들어지고 `build/native/cef`가 CEF 배포본을 가리킵니다(macOS는 `cefweaver/cefsubprocess.app`도 조립합니다). Linux에서는 런타임을 복사하지 않습니다. 2단계의 wheel 빌드가 CMake로 모두 처리하므로 이 단계는 CEF를 미리 받거나 `--cef-root`로 지정할 때 씁니다. CEF를 직접 지정하거나 소스 빌드하는 방법은 [CEF 확보하기](obtain-cef.md)에 있습니다.

2. **wheel 빌드**

   ```sh
   CEF_ROOT=$PWD/build/native/cef uv build --wheel --python 3.13 -o dist
   ```

   `CEF_ROOT`를 주지 않으면 CMake가 CEF를 구합니다(`third_party/cef`). scikit-build-core가 CMake로 래퍼 라이브러리, `cefsubprocess`, 확장 모듈을 빌드하고 런타임을 wheel에 넣습니다([패키징](../components/packaging.md)). 인자 없는 `uv build`도 sdist와 wheel을 모두 만드는 것을 확인했습니다.

3. **설치**

   ```sh
   uv pip install dist/cefweaver-*.whl
   ```

4. **확인**

   ```python
   import cefweaver
   print(cefweaver.__all__)
   ```

## 다시 빌드할 때

- C++(`native/`)나 `.pyx`, 생성 파일을 고쳤으면 wheel만 다시 만듭니다. CMake의 의존성으로 바뀐 것만 다시 빌드됩니다. 단 빌드 격리(기본)에서는 격리 환경의 경로가 매번 달라 변경이 없어도 약 84초가 걸립니다. 증분 빌드를 하려면 `--no-build-isolation`을 씁니다([분석](../analyses/scikit-build-core-prototype.md): 변경 없음 14초, `.pxi` 하나 83초, 래퍼 헤더 하나 17초).
- CEF 헤더가 바뀌면(버전 변경) `python tools/gen/generate.py`가 먼저입니다([CEF 버전 올리기](update-cef-version.md)).
- `prepare.py`는 다시 실행해도 안전합니다. 이전 버전의 스크립트가 `cefweaver/`에 복사해 둔 항목(Linux의 런타임, macOS의 `cefsubprocess.app`)을 지웁니다.

## 자주 만난 문제

| 증상 | 원인과 해결 |
| --- | --- |
| `ImportError`: libcef.so를 못 찾음 | 런타임이 들어가지 않은 wheel입니다. 빌드 로그의 `Installing:` 줄에 `libcef.so`가 있는지 확인합니다(macOS는 `prepare.py`의 `cefweaver/cefsubprocess.app` 조립). |
| 소스 트리에서 import가 되지 않음(`_cefweaver` 없음) | 정상입니다. 확장은 wheel에만 있으니 설치한 뒤 `python -P`로 실행합니다. |
| 구성 단계에서 clang-format 오류 | `CEFWEAVER_FETCH_CLANG_FORMAT`가 켜져 있습니다. 기본값은 꺼짐입니다. |

## 관련 페이지

- [CEF 확보하기](obtain-cef.md)
- [시험 실행하기](run-tests.md)
- [tools/prepare.py](../components/tool-prepare.md)
- [패키징](../components/packaging.md)
