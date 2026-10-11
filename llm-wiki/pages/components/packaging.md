---
title: 패키징
type: component
sources:
  - pyproject.toml
  - .gitignore
  - tools/prepare.py
  - cefweaver/__init__.py
  - cmake/CefweaverExtension.cmake
  - CMakeLists.txt
updated: 2026-10-11
---

# 패키징

빌드 백엔드는 scikit-build-core이고(`requires = ["scikit-build-core>=0.10", "Cython>=3.0", "cmake>=3.28.1"]`) 도구는 uv입니다. 2026-10-11에 setuptools와 `setup.py`에서 옮겼습니다. 확장 모듈과 wheel에 들어가는 파일을 모두 CMake가 만듭니다. 옮긴 이유와 확인 범위는 [분석](../analyses/scikit-build-core-prototype.md)에 있습니다(Linux에서 확인, macOS와 Windows는 확인하지 못함).

## 흐름

1. `uv build --wheel`이 scikit-build-core를 부르고, 이것이 최상위 `CMakeLists.txt`를 구성합니다. `SKBUILD`가 켜져 있으면 `cmake/CefweaverExtension.cmake`가 포함됩니다. 그렇지 않은 구성(`tools/prepare.py`의 사전 빌드)에서는 포함되지 않습니다.
2. 같은 CMake 안에서 `libcef_dll_wrapper`, `cefwrapper`, `cefsubprocess`가 빌드됩니다. CEF는 `-DCEF_ROOT`, 환경 변수 `CEF_ROOT`, 없으면 내려받기 순서로 정해집니다([CEF 확보 방식](../concepts/cef-acquisition.md)). `tools/prepare.py`가 만든 `build/native/cef`를 `CEF_ROOT`로 주면 같은 배포본을 씁니다.
3. `cefweaver/_cefweaver.pyx`는 `add_custom_command`로 Cython을 실행해 C++로 바꾸고(`.pxi`, `.pxd`가 바뀌면 다시 실행), `Python_add_library(_cefweaver MODULE WITH_SOABI ...)`로 확장 모듈을 만듭니다. `cefwrapper`에 링크하면 `libcef_dll_wrapper`, `libcef`, 시스템 라이브러리가 CMake의 의존성으로 따라옵니다. 정의는 `NDEBUG=1`(Linux는 `_FILE_OFFSET_BITS=64`도), 표준은 C++20, Linux의 rpath는 `$ORIGIN`입니다.
4. `install()`이 확장 모듈, Linux의 `cefsubprocess`, `Release/*`와 `Resources/*`(`chrome-sandbox` 제외)를 `cefweaver/`에 넣습니다. `libcef.so`는 일반 파일이라 `install.strip`이 듣지 않으므로 `install(CODE ...)`가 `strip --strip-unneeded`를 실행합니다(1.4GB에서 약 272MB).
5. 순수 Python 파일, 타입 스텁, `py.typed`는 `wheel.packages = ["cefweaver"]`로 들어갑니다. `wheel.exclude`가 `.pyx`, `.pxd`, `.pxi`, `CMakeLists.txt`, `__pycache__`, 생성된 `_cefweaver.cpp`를 뺍니다.

빌드 디렉터리는 `build/skbuild/{wheel_tag}`입니다. 정적 라이브러리가 바뀌면 CMake가 의존성으로 알아서 다시 링크하므로, setuptools 때 필요했던 `depends` 목록은 없습니다.

## macOS

`OS_MAC` 분기가 `-framework Cocoa`, `-framework AppKit`, `-framework IOSurface`, `-Wl,-ObjC`를 더합니다(`setup.py`가 주던 값). `libcef`는 링크하지 않습니다. **이 분기는 macOS에서 빌드하거나 돌려 보지 못했습니다.** `cefsubprocess.app`은 아직 `tools/prepare.py`의 `stage_macos()`가 `cefweaver/` 아래에 조립하고, `wheel.packages`가 그것을 파일로 가져갑니다. Linux는 스테이징을 하지 않습니다(`prepare.py`가 이전 스테이징 결과를 지우기만 합니다. 같은 파일이 두 번 들어가지 않게 하기 위해서입니다).

## sdist와 `uv build`

- 인자 없는 `uv build`가 sdist와 wheel을 모두 만들었습니다(`CEF_ROOT` 지정, 약 1분 39초, sdist 1,062,753바이트, wheel 156,076,196바이트). 따로 실행한 `uv build --sdist`는 약 1MB의 sdist를 만들었고, 그 sdist 하나로 `uv build --wheel`이 wheel을 만들었습니다(2026-10-11, `CEF_ROOT` 없이 실행했으므로 CMake가 CEF를 구했습니다. 어디에서 구했는지는 확인하지 않았습니다).
- 이 이유로 `MANIFEST.in`을 지웠습니다(scikit-build-core는 쓰지 않고, sdist에는 git이 추적하는 파일이 들어갑니다). sdist에는 `docs/`, `examples/`, `llm-wiki/`, `tests/`, `tools/`도 들어 있습니다(361개 항목). 줄일지는 정하지 않았습니다.

## git에서 제외되는 파일

`.gitignore`가 `cefweaver/_cefweaver.cpp`(옛 setuptools 빌드의 Cython 생성물), `cef_binary*`, `build/`를 제외합니다. 이제 Linux에서는 런타임이 소스 트리에 복사되지 않습니다.

## wheel의 특성

- 태그는 `cp313-cp313-linux_x86_64`처럼 로컬 플랫폼 태그입니다. PyPI에 올리려면 manylinux 규격이 필요한데, `auditwheel show`는 이 wheel에 `linux_x86_64`만 허용했습니다(빌드 호스트의 glibc 2.43 심볼과, CEF가 요구하는 허용 목록 밖의 시스템 라이브러리 때문. F24).
- 크기: 약 156,076,117바이트(2026-10-11, scikit-build-core로 만든 것). 설치하면 약 363MB입니다(이전 값, 다시 재지 않음).
- 빌드 시간: `uv build --wheel`은 한 번에 약 1분 37초였습니다(2026-10-11). 빌드 격리를 끄면(`--no-build-isolation`) 증분 빌드가 되는 것은 프로토타입에서 확인했습니다.

## 메타데이터의 불일치

`pyproject.toml`에는 이 프로젝트의 현재 상태와 맞지 않는 항목이 있습니다. `dependencies = ["numpy>=1.26.2"]`는 코드 어디에서도 쓰이지 않습니다. classifier에는 macOS와 Windows가 있지만 지원하지 않거나 검증하지 못했습니다. `requires-python = ">=3.11"`과 달리 classifier는 3.11과 3.12만 적혀 있습니다(시험은 3.11~3.14에서 했습니다). [알려진 제약과 미검증 항목](../reference/known-constraints.md)에 모았습니다.

## 관련 페이지

- [런타임 파일 배치](../concepts/runtime-layout.md)
- [tools/prepare.py](tool-prepare.md)
- [빌드와 설치](../procedures/build-and-install.md)
- [앱을 PyInstaller와 cx_Freeze로 묶기](../procedures/freeze-app.md)
- [scikit-build-core로 setup.py 없이 빌드하기 (프로토타입)](../analyses/scikit-build-core-prototype.md)
