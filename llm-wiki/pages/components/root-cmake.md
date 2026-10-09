---
title: 루트 CMake와 CEF 다운로드
type: component
sources:
  - CMakeLists.txt
  - cmake/DownloadCEF.cmake
  - native/cefwrapper/CMakeLists.txt
  - native/cefsubprocess/CMakeLists.txt
  - third_party/cef/README.txt
  - native/cefwrapper/mac_runtime.mm
updated: 2026-10-09
---

# 루트 CMake와 CEF 다운로드

`CMakeLists.txt`는 CEF 템플릿(`cefsimple` 예제의 구성)에서 출발한 파일이고, 저작권 표시도 CEF 프로젝트의 것을 유지합니다. 같은 구조가 java-cef의 `CMakeLists.txt`와 `DownloadCEF.cmake`에도 있습니다([관련 프로젝트](../reference/related-projects.md)).

## 구성 순서

1. `cmake_minimum_required(VERSION 3.19)`, 구성 유형은 `Debug`와 `Release`, 프로젝트 이름 `cefweaver`.
2. **CEF 버전**: `CEF_VERSION`이 정의되지 않았으면 `154.0.34+g14c5a08+chromium-154.0.8037.98`을 씁니다(`-DCEF_VERSION=...`으로 덮어씁니다).
3. (이전에 있던 macOS 중단은 제거했습니다.)
4. **플랫폼 판별**: `linux64`, `linux32`, `windows64`, `windows32`(포인터 크기로 구분), `macosarm64`, `macosx64`(`PROJECT_ARCH`나 호스트 프로세서로 구분).
5. **CEF 확보**: `-DCEF_ROOT`, 환경변수 `CEF_ROOT`, 자동 다운로드(`DownloadCEF`) 순입니다. 지정한 경로에 `cmake/FindCEF.cmake`가 없으면 `FATAL_ERROR`입니다.
6. 확정한 경로를 캐시 변수 `CEFWEAVER_CEF_ROOT`에 기록하고(`tools/prepare.py`가 읽습니다), `include/cef_version.h`에서 실제 쓰는 CEF 버전을 읽어 로그로 남깁니다. `CEF_ROOT` 자체는 캐시하지 않습니다([CEF 확보 방식](../concepts/cef-acquisition.md)).
7. `find_package(CEF REQUIRED)`로 CEF 배포본의 `cmake/FindCEF.cmake`를 읽습니다. 이후의 `ADD_LOGICAL_TARGET`, `SET_CEF_TARGET_OUT_DIR`, `COPY_FILES` 같은 매크로와 `OS_LINUX` 같은 변수는 모두 CEF가 제공합니다.
8. **Python 확인**: 환경변수 `PYTHON_EXECUTABLE` 또는 `find_package(PythonInterp)`. `prepare.py`는 `-DPYTHON_EXECUTABLE`을 넘깁니다.
9. CEF의 `README.txt`를 빌드 디렉터리에 복사합니다.
10. **clang-format 다운로드**: 옵션 `CEFWEAVER_FETCH_CLANG_FORMAT`(기본 `OFF`)일 때만 `tools/buildtools/download_from_google_storage.py`를 실행합니다. 기본이 꺼진 이유는 이 단계가 Python 3.14에서 gsutil의 `six.moves` 오류로 구성 전체를 중단시켰고, 빌드에 필요하지 않기 때문입니다([저장소 메타데이터](repo-metadata.md)).
11. 하위 디렉터리: `libcef_dll_wrapper`(`CEF_LIBCEF_DLL_WRAPPER_PATH`, CEF 배포본 안), `native/cefwrapper`, `native/cefsubprocess`. `#add_subdirectory(native)`와 `src/cefwrappertest`는 주석 처리되어 있습니다.
12. `PRINT_CEF_CONFIG()`로 구성을 출력합니다.

## cmake/DownloadCEF.cmake

`DownloadCEF(platform version download_dir)` 함수입니다.

- 배포본 이름은 `cef_binary_<버전>_<플랫폼>`이고 풀린 위치는 `third_party/cef/` 아래입니다.
- 디렉터리가 없으면 `https://cef-builds.spotifycdn.com/<이름>.tar.bz2`를 받습니다. 이름의 `+`는 `%2B`로 바꿉니다. 먼저 `.sha1`을 받고 본 파일을 `EXPECTED_HASH SHA1=...`로 검증합니다.
- `cmake -E tar xzf`로 풉니다. 옵션에 `z`(gzip)가 있지만 `.tar.bz2`도 실제로 풀렸습니다.
- `CEF_ROOT`를 `PARENT_SCOPE` 일반 변수로만 설정합니다. 이전에는 `CACHE INTERNAL`이었고, 그 때문에 옛 버전이 고정되는 결함이 있었습니다.
- 표준(`standard`) 배포본만 받습니다. `minimal`과 `client` 배포본은 쓰지 않습니다.

## 네이티브 타깃의 CMake

| 파일 | Linux | Windows |
| --- | --- | --- |
| `native/cefwrapper/CMakeLists.txt` | `libcefwrapper.a`(정적, `POSITION_INDEPENDENT_CODE ON`, `libcef_lib`와 `libcef_dll_wrapper`와 `${CMAKE_DL_LIBS}` 링크). 소스에 `cef_wrapper_client_handler_linux.cc`가 추가됩니다. | 정적 라이브러리(원래 구성). 소스에 `cef_wrapper_client_handler_win.cc`. |
| `native/cefsubprocess/CMakeLists.txt` | 실행 파일 `cefsubprocess`(RPATH `$ORIGIN`, CEF 바이너리와 리소스를 출력 디렉터리에 복사, `libminigbm.so`가 있으면 추가 복사) | `WIN32` 실행 파일, 매니페스트, 여러 대상 디렉터리로 복사 |

macOS: `native/cefwrapper/CMakeLists.txt`는 Linux처럼 PIC 정적 라이브러리를 만들되 `libcef`는 링크하지 않고(`libcef_lib`는 mac에 없음), `.mm` 두 개(`mac_runtime.mm`, `cef_wrapper_client_handler_mac.mm`)를 ARC로 컴파일합니다. `native/cefsubprocess/CMakeLists.txt`는 CEF가 정한 접미사(`(Alerts)`, `(GPU)`, `(Plugin)`, `(Renderer)`)마다 도우미 앱 타깃을 만들고 `native/cefsubprocess/mac/`의 plist를 씁니다. 도우미 앱을 모아 `cefsubprocess.app`으로 조립하는 일은 CMake가 아니라 `tools/prepare.py`가 합니다. Windows 분기에는 이 저장소에 없는 `src/PyCef_Dev`, `cefwrappertest` 디렉터리로 복사하는 줄이 남아 있습니다([사용하지 않는 코드와 유산](legacy-code.md)).

## 관련 페이지

- [tools/prepare.py](tool-prepare.md)
- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [cefsubprocess 실행 파일](native-cefsubprocess.md)
- [빌드와 설치](../procedures/build-and-install.md)
