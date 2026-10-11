---
title: scikit-build-core로 setup.py 없이 빌드하기 (프로토타입)
type: analysis
sources:
  - pyproject.toml
  - CMakeLists.txt
  - tools/prepare.py
  - native/cefwrapper/CMakeLists.txt
updated: 2026-10-11
---

# scikit-build-core로 setup.py 없이 빌드하기 (프로토타입)

Windows 지원을 시작하며 나온 질문("`setup.py`를 피할 수 있는가, A안으로 가능한가")에 답하려고, 확장 모듈을 CMake에서 빌드하는 방식을 **Linux에서 프로토타입**으로 확인한 기록입니다. 처음에는 임시 작업 트리에서 만들고 지웠고 결정은 하지 않았으나, 같은 날(2026-10-11) 사용자가 A안을 정해 저장소에 반영했습니다(`setup.py`와 `MANIFEST.in` 삭제, `cmake/CefweaverExtension.cmake` 추가, `prepare.py`의 Linux 스테이징 제거). 반영한 결과의 확인은 [verified-findings-opened.md의 F113](../reference/verified-findings-opened.md)에 있습니다. 아래는 프로토타입 시점의 기록입니다.

## 왜 이 방식인가

`setup.py`는 CMake가 정한 컴파일 옵션을 손으로 되풀이합니다(코드의 주석: "Must match how the CEF wrapper libraries were compiled"). Linux에서는 어긋나도 대개 경고이지만 Windows에서는 런타임 라이브러리(`/MD`와 `/MT`)나 `_ITERATOR_DEBUG_LEVEL`이 어긋나면 링크가 실패할 것으로 예상합니다(예상이고 확인하지 못했습니다). 확장도 CMake 타깃이면 `cefwrapper`, `libcef_dll_wrapper`, `libcef`와 같은 플래그 집합과 라이브러리 이름과 순서를 CMake가 한 곳에서 정합니다.

## 만든 것

- `pyproject.toml`: 빌드 백엔드를 `scikit_build_core.build`로 바꾸고(`requires`에 `scikit-build-core`, `Cython`, `cmake`), `[tool.scikit-build]`에 `build-dir`, `wheel.packages = ["cefweaver"]`, `wheel.exclude`(`.pyx`, `.pxd`, `.pxi`), `install.strip = true`를 둡니다. `setup.py`는 지웁니다.
- `CMakeLists.txt`: `native/cefsubprocess` 뒤에 `if(SKBUILD) include(CefweaverExtension) endif()`를 더합니다(`prepare.py`로 하는 기존 흐름은 `SKBUILD`가 없어서 바뀌지 않음).
- `cmake/CefweaverExtension.cmake`(새 파일, 전문):

```cmake
# The Python extension module cefweaver._cefweaver and the files of the wheel (scikit-build-core).
#
# The module is built here and not in setup.py so that it gets the same compiler, runtime library and link
# libraries as cefwrapper and libcef_dll_wrapper (they come from CEF's own cmake), on every platform.

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_program(CYTHON_EXECUTABLE NAMES cython cython3 HINTS "${Python_EXECUTABLE}/.." REQUIRED)

set(CEFWEAVER_PYX "${CMAKE_SOURCE_DIR}/cefweaver/_cefweaver.pyx")
set(CEFWEAVER_CPP "${CMAKE_CURRENT_BINARY_DIR}/_cefweaver.cpp")
# The .pyx includes the .pxi files; a change of any of them must run Cython again.
file(GLOB_RECURSE CEFWEAVER_CYTHON_DEPS CONFIGURE_DEPENDS
     "${CMAKE_SOURCE_DIR}/cefweaver/*.pxi" "${CMAKE_SOURCE_DIR}/cefweaver/*.pxd")
add_custom_command(
  OUTPUT "${CEFWEAVER_CPP}"
  COMMAND "${CYTHON_EXECUTABLE}" --cplus -I "${CMAKE_SOURCE_DIR}/cefweaver" "${CEFWEAVER_PYX}" -o "${CEFWEAVER_CPP}"
  DEPENDS "${CEFWEAVER_PYX}" ${CEFWEAVER_CYTHON_DEPS}
  COMMENT "Cython: _cefweaver.pyx"
  VERBATIM)

Python_add_library(_cefweaver MODULE WITH_SOABI "${CEFWEAVER_CPP}")
target_include_directories(_cefweaver PRIVATE "${CEF_ROOT}" "${CMAKE_SOURCE_DIR}/native/cefwrapper")
target_compile_definitions(_cefweaver PRIVATE NDEBUG=1 $<$<PLATFORM_ID:Linux>:_FILE_OFFSET_BITS=64>)
target_compile_features(_cefweaver PRIVATE cxx_std_20)
# cefwrapper brings libcef_dll_wrapper, libcef and the system libraries (in the right order).
target_link_libraries(_cefweaver PRIVATE cefwrapper)
if(OS_LINUX)
  set_target_properties(_cefweaver PROPERTIES BUILD_WITH_INSTALL_RPATH ON INSTALL_RPATH "$ORIGIN")
endif()
install(TARGETS _cefweaver LIBRARY DESTINATION cefweaver RUNTIME DESTINATION cefweaver)

# The CEF runtime next to the module (CEF looks for icudtl.dat next to libcef.so; cefsubprocess finds libcef.so through
# its rpath). The sandbox helper is not used (no_sandbox).
if(OS_LINUX)
  install(TARGETS cefsubprocess RUNTIME DESTINATION cefweaver)
  file(GLOB CEFWEAVER_RUNTIME "${CEF_ROOT}/Release/*" "${CEF_ROOT}/Resources/*")
  list(FILTER CEFWEAVER_RUNTIME EXCLUDE REGEX "/chrome-sandbox$")
  foreach(entry IN LISTS CEFWEAVER_RUNTIME)
    if(IS_DIRECTORY "${entry}")
      install(DIRECTORY "${entry}" DESTINATION cefweaver)
    else()
      install(PROGRAMS "${entry}" DESTINATION cefweaver)
    endif()
  endforeach()
  # install.strip strips targets only; libcef.so (1.4 GB with its symbols, about 270 MB without) is a plain file here.
  install(CODE "
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND \"${CMAKE_STRIP}\" --strip-unneeded \"\${CMAKE_INSTALL_PREFIX}/cefweaver/libcef.so\")
    endif()")
endif()
requires = ["scikit-build-core>=0.10", "Cython>=3.0", "cmake>=3.28.1"]
build-backend = "scikit_build_core.build"
[tool.scikit-build]
# CMake builds everything: the CEF wrapper libraries, cefsubprocess, the extension module and the staging of the
# CEF runtime into the wheel (see cmake/CefweaverExtension.cmake). CEF comes from $CEF_ROOT or is downloaded.
minimum-version = "build-system.requires"
build-dir = "build/skbuild/{wheel_tag}"
cmake.build-type = "Release"
wheel.packages = ["cefweaver"]
wheel.exclude = ["**/*.pyx", "**/*.pxd", "**/*.pxi", "**/CMakeLists.txt", "**/__pycache__"]
install.strip = true```

## 확인한 것 (Linux x86_64, Python 3.13, CEF 154, 2026-10-11)

- 이 방식으로 wheel이 **첫 시도에 만들어졌습니다**(`CEF_ROOT=<경로> uv build --wheel`).
- 만든 wheel을 설치해 전체 시험(`tests/`)을 돌린 결과가 기존 wheel과 같았습니다: 532개 통과, 건너뜀 9, 예상된 실패 3.
- wheel의 파일 목록은 기존과 같고 다른 것은 의도한 제외(`.pyx`, `.pxd`, `.pxi`)와 setuptools의 `top_level.txt`뿐이었습니다. `libcef.so`는 기존과 같은 크기(272,219,288바이트)로 줄었습니다.
- **`install.strip`은 `install(PROGRAMS)`로 설치한 파일에는 듣지 않았습니다.** 처음에는 `libcef.so`가 1.4GB 그대로였고, `install(CODE ...)`로 `strip --strip-unneeded`를 실행하게 해서 고쳤습니다(`prepare.py`가 하던 것).
- 확장 모듈(`.so`)은 5.9MB가 되어 기존(30.7MB)보다 작습니다. 기존은 strip하지 않았고 이쪽은 `install.strip`이 적용되었기 때문입니다. 충돌 조사에 심볼이 필요하면 `install.strip`을 끄거나 구성에 따라 나눠야 합니다.
- **빌드 시간**: 빌드 격리를 켠 기본 상태에서는 변경이 없어도 매번 약 84초입니다. 격리 환경의 경로가 매번 달라서 CMake가 Cython 규칙을 다시 실행하고 큰 생성 코드(`_cefweaver.cpp`)를 다시 컴파일하기 때문으로 보입니다(원인은 로그의 Cython 실행 횟수로 추정). 격리를 끄면(`--no-build-isolation`, 빌드 의존성을 미리 설치) 변경 없음 14초, `.pxi` 하나 변경 83초(Cython과 큰 파일 컴파일), 래퍼 헤더 변경 17초로 증분 빌드가 됩니다. 기존 `uv build --wheel`도 한 번에 약 1분 45초였습니다.

## 확인하지 못한 것

- **macOS**: 확장의 링크 옵션(`-framework Cocoa AppKit IOSurface`, `-Wl,-ObjC`, `MACOSX_DEPLOYMENT_TARGET`)과 `cefsubprocess.app` 조립(`prepare.py`의 `stage_macos()`)을 CMake로 옮기지 않았습니다. 후자가 가장 큰 이식 대상입니다.
- **Windows**: `CEF_RUNTIME_LIBRARY_FLAG=/MD`와 `USE_SANDBOX=OFF`(`pyproject.toml`의 플랫폼 조건 `overrides`로 줄 수 있어 보이나 시험하지 않음), 런타임 DLL 목록의 설치, MSVC 컴파일은 하나도 확인하지 못했습니다.
- `prepare.py`의 `stage_runtime`은 런타임을 `cefweaver/` 소스 폴더에 복사하므로, 이 방식에서는 `wheel.packages`가 그 파일들까지 묶어 중복됩니다. 이 방식을 채택하면 그 단계를 없애거나 끄도록 바꿔야 합니다(시험하지 않음).
- CEF를 CMake가 내려받는 경로(`CEF_ROOT`를 주지 않을 때)와 sdist 빌드는 시험하지 않았습니다.
- 증분 빌드가 macOS와 Windows에서도 같은지는 모릅니다.

## 관련 페이지

- [패키징](../components/packaging.md)
- [플랫폼 지원 현황](../concepts/platform-support.md)
- [설계 결정 기록](../reference/design-decisions.md)
