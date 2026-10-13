---
title: 루트 CMake와 CEF 다운로드
type: component
sources:
  - tests/test_download_cef.py
  - tools/safe_extract.py
  - CMakeLists.txt
  - cmake/DownloadCEF.cmake
  - native/cefwrapper/CMakeLists.txt
  - native/cefsubprocess/CMakeLists.txt
  - third_party/cef/README.txt
  - native/cefwrapper/mac_runtime.mm
updated: 2026-10-13
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
- 디렉터리가 없으면 `https://cef-builds.spotifycdn.com/<이름>.tar.bz2`를 받습니다(`CEF_DOWNLOAD_BASE_URL`로 바꿀 수 있고 시험은 `file:` 주소를 씁니다). 이름의 `+`는 `%2B`로 바꿉니다.
- **검증 (2026-10-13에 고침)**: `.sha1`을 받아 40자리 16진수인지 확인하고, 아카이브를 `.part` 파일로 받아 SHA1을 직접 계산해 맞을 때만 제 이름으로 옮깁니다. 틀리면 지우고 `FATAL_ERROR`입니다. 이전 구현은 `file(DOWNLOAD ... EXPECTED_HASH)`를 썼는데, 해시가 틀려 멈춰도 파일이 남아 다음 실행이 `NOT EXISTS` 조건 때문에 검증 없이 그 파일을 풀었습니다. 이미 있는 아카이브도 쓰기 전에 `.sha1`과 다시 대조하고 맞지 않으면 다시 받습니다.
- **추출 (2026-10-13에 고침)**: `tools/safe_extract.py`(Python)가 풉니다. 모든 멤버를 먼저 검사해 `..`, 절대 경로, 앞선 심볼릭 링크를 따라가서 밖으로 나가는 이름, 밖을 가리키는 링크, 장치 파일을 거부하고(하나라도 있으면 아무것도 풀지 않음) 통과하면 Python의 `data` 필터까지 걸어 풉니다. 이전의 `cmake -E tar xzf`는 이런 쓰기를 막지 못했습니다. 임시 폴더(`.unpack-<이름>`)에 풀고 배포본 폴더를 통째로 옮겨서, 중간에 끊긴 추출을 끝난 것으로 오인하지 않습니다.
- 버전과 플랫폼 이름은 글자, 숫자, `.+_-`만 받고 `..`는 거부합니다(파일 이름과 URL에 쓰이므로).
- 시험 `tests/test_download_cef.py` 24개(`tools/safe_extract.py` 13개, DownloadCEF 11개)가 직접 만든 아카이브와 `file:` 주소로 경로 탈출 일곱 가지, 틀린 해시의 우회, 비정상 `.sha1`, 경로 모양의 버전을 확인합니다(CEF와 네트워크 불필요). 이전 구현에서는 DownloadCEF 쪽 10개 중 8개가 실패합니다.
- `CEF_ROOT`를 `PARENT_SCOPE` 일반 변수로만 설정합니다. 이전에는 `CACHE INTERNAL`이었고, 그 때문에 옛 버전이 고정되는 결함이 있었습니다.
- 표준(`standard`) 배포본만 받습니다. `minimal`과 `client` 배포본은 쓰지 않습니다.

Windows에서는 `find_package(CEF)` 앞에서 `USE_SANDBOX`를 `OFF`로 고정합니다(래퍼가 `no_sandbox`를 쓰고 `cef_sandbox.lib`는 VS 버전이 맞아야 링크됩니다). 이것이 없으면 `IMPORTED_LOCATION not set for imported target "cef_sandbox_lib"`로 구성이 끝나지 않았습니다([F116](../reference/verified-findings-windows.md)).

## 네이티브 타깃의 CMake

| 파일 | Linux | Windows |
| --- | --- | --- |
| `native/cefwrapper/CMakeLists.txt` | `libcefwrapper.a`(정적, `POSITION_INDEPENDENT_CODE ON`, `libcef_lib`와 `libcef_dll_wrapper`와 `${CMAKE_DL_LIBS}` 링크). 소스에 `cef_wrapper_client_handler_linux.cc`가 추가됩니다. | 정적 라이브러리(원래 구성). 소스에 `cef_wrapper_client_handler_win.cc`. |
| `native/cefsubprocess/CMakeLists.txt` | 실행 파일 `cefsubprocess`(RPATH `$ORIGIN`, CEF 바이너리와 리소스를 출력 디렉터리에 복사, `libminigbm.so`가 있으면 추가 복사) | `WIN32` 실행 파일, 매니페스트, 출력 디렉터리로 복사(옛 외부 대상 복사는 지움) |

macOS: `native/cefwrapper/CMakeLists.txt`는 Linux처럼 PIC 정적 라이브러리를 만들되 `libcef`는 링크하지 않고(`libcef_lib`는 mac에 없음), `.mm` 두 개(`mac_runtime.mm`, `cef_wrapper_client_handler_mac.mm`)를 ARC로 컴파일합니다. `native/cefsubprocess/CMakeLists.txt`는 CEF가 정한 접미사(`(Alerts)`, `(GPU)`, `(Plugin)`, `(Renderer)`)마다 도우미 앱 타깃을 만들고 `native/cefsubprocess/mac/`의 plist를 씁니다. 도우미 앱을 모아 `cefsubprocess.app`으로 조립하는 일은 CMake가 아니라 `tools/prepare.py`가 합니다. Windows 분기에는 이 저장소에 없는 `src/PyCef_Dev`, `cefwrappertest` 디렉터리로 복사하는 줄이 남아 있습니다([사용하지 않는 코드와 유산](legacy-code.md)).

## 관련 페이지

- [tools/prepare.py](tool-prepare.md)
- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [cefsubprocess 실행 파일](native-cefsubprocess.md)
- [빌드와 설치](../procedures/build-and-install.md)
