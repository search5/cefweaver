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
  - .github/workflows/build-test.yml
  - .gitattributes
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

`OS_MAC` 분기가 `-framework Cocoa`, `-framework AppKit`, `-framework IOSurface`, `-Wl,-ObjC`를 더합니다(`setup.py`가 주던 값). `libcef`는 링크하지 않습니다. 배포 대상 12.0은 `-mmacosx-version-min=12.0`을 컴파일과 링크에 주는 것과, `pyproject.toml`의 `[[tool.scikit-build.overrides]]`(`if.platform-system = "^darwin"`, `cmake.define.CMAKE_OSX_DEPLOYMENT_TARGET = "12.0"`)가 정합니다. 후자가 없으면 wheel 태그가 빌드한 컴퓨터의 버전(`macosx_26_0_arm64`)이 되어 더 낡은 macOS에 설치되지 않습니다. `cefsubprocess.app`(CEF 프레임워크와 도우미 앱 5개와 Info.plist)은 같은 파일의 `install(DIRECTORY ...)`가 wheel에 넣습니다. 도우미 앱은 strip하지 않고 그대로 복사합니다(`install.strip`이 ad hoc 서명을 깨기 때문). 처음에는 `prepare.py`의 스테이징 결과를 `wheel.packages`가 파일로 가져가는 줄 알았으나, `.gitignore`에 있는 폴더를 scikit-build-core가 빼서 wheel에 앱이 하나도 없었습니다. **macOS arm64에서 빌드하고 구동해 확인했습니다**([F93](../reference/verified-findings-macos.md)).

## Windows

같은 CMake가 Windows(Visual Studio 생성기)에서 빌드합니다([F116](../reference/verified-findings-windows.md)). 달라지는 점: `WIN32`에서 `USE_SANDBOX`를 끕니다. `OS_WIN` 분기는 `target_compile_definitions(NOMINMAX WIN32_LEAN_AND_MEAN UNICODE _UNICODE)`, `MSVC_RUNTIME_LIBRARY MultiThreaded`(`/MT`), `/utf-8 /bigobj`를 줍니다. 런타임 `install()`은 Linux와 같이 `cefsubprocess.exe`와 `Release/*`, `Resources/*`를 넣되 `.lib`를 빼고, `libcef.so`를 줄이는 `strip`은 Linux에서만 돕니다. wheel 태그는 `cp313-cp313-win_amd64`이고 약 180MB입니다. `pyproject.toml`의 extras에 `pywin32 = ["pywin32>=306; sys_platform == 'win32'"]`가 있습니다.

`.gitattributes`(`* text=auto eol=lf`)가 모든 파일을 LF로 고정합니다. Windows의 git이 `core.autocrlf=true`로 CRLF 파일을 만들어서, 생성 파일을 바이트 단위로 비교하는 시험(`test_generated_files_are_up_to_date`)이 실패했기 때문입니다.

## sdist와 `uv build`

- 인자 없는 `uv build`가 sdist와 wheel을 모두 만들었습니다(`CEF_ROOT` 지정, 약 1분 39초, sdist 1,062,753바이트, wheel 156,076,196바이트). 따로 실행한 `uv build --sdist`는 약 1MB의 sdist를 만들었고, 그 sdist 하나로 `uv build --wheel`이 wheel을 만들었습니다(2026-10-11, `CEF_ROOT` 없이 실행했으므로 CMake가 CEF를 구했습니다. 어디에서 구했는지는 확인하지 않았습니다).
- 이 이유로 `MANIFEST.in`을 지웠습니다(scikit-build-core는 쓰지 않고, sdist에는 git이 추적하는 파일이 들어갑니다). sdist에는 `docs/`, `examples/`, `llm-wiki/`, `tests/`, `tools/`도 들어 있습니다(361개 항목). 줄일지는 정하지 않았습니다.

## git에서 제외되는 파일

`.gitignore`가 `cefweaver/_cefweaver.cpp`(옛 setuptools 빌드의 Cython 생성물), `cef_binary*`, `build/`를 제외합니다. 이제 Linux에서는 런타임이 소스 트리에 복사되지 않습니다.

## wheel의 특성

- 태그는 `cp311-abi3-linux_x86_64`처럼 안정 ABI(abi3)와 로컬 플랫폼 태그입니다(아래 "abi3"). PyPI에 올리려면 manylinux 규격이 필요한데, `auditwheel show`는 이 wheel에 `linux_x86_64`만 허용했습니다(빌드 호스트의 glibc 2.43 심볼과, CEF가 요구하는 허용 목록 밖의 시스템 라이브러리 때문. F24).
- 크기: 약 156,076,117바이트(2026-10-11, scikit-build-core로 만든 것). 설치하면 약 363MB입니다(이전 값, 다시 재지 않음).
- 빌드 시간: `uv build --wheel`은 한 번에 약 1분 37초였습니다(2026-10-11). 빌드 격리를 끄면(`--no-build-isolation`) 증분 빌드가 되는 것은 프로토타입에서 확인했습니다.

## 메타데이터의 불일치

`pyproject.toml`에는 이 프로젝트의 현재 상태와 맞지 않는 항목이 있습니다. `dependencies = ["numpy>=1.26.2"]`는 코드 어디에서도 쓰이지 않습니다. classifier의 macOS(arm64만)와 Windows(11 x86_64만)는 일부 환경에서만 확인했습니다. `requires-python = ">=3.11"`과 달리 classifier는 3.11과 3.12만 적혀 있습니다(시험은 3.11~3.14에서 했습니다). [알려진 제약과 미검증 항목](../reference/known-constraints.md)에 모았습니다.

## CI (`build-test.yml`)

- `.github/workflows/build-test.yml`은 수동 실행(`workflow_dispatch`) 전용입니다. 입력은 `platform`(both, linux, macos), `python-version`(3.13), `run-tests`, `upload-wheel`이고, ubuntu-24.04와 macos-14에서 `uv build --wheel`로 wheel을 만들어 설치한 뒤 시험하고 wheel을 산출물로 보관합니다.
- macOS 분기를 맡은 세션이 작성해 로컬 커밋으로만 두었고, 이 저장소에서 받아 옮겼습니다. 아직 GitHub에서 실행해 보지 못했고(YAML 구조만 확인), Linux의 apt 패키지 목록은 짐작한 것입니다. Windows 실행(`platform`에 `windows`와 `all`, 러너 `windows-2025`)은 2026-10-11에 더했지만 **GitHub에서 돌려 보지 못했습니다.** wheel은 `.venv-test\Scripts\python.exe`로 설치하고 시험은 `xvfb-run` 없이 돕니다.
- 첫 실행에서는 위키 점검 시험이 `/home/jiho/...`를 가리키는 링크 하나 때문에 실패해서 한동안 환경 변수로 건너뛰었습니다. 2026-10-12에 그 링크를 인라인 코드로 바꾸고 `lint.py`가 저장소 밖을 가리키는 링크를 오류로 보게 해서, 지금은 CI에서도 이 시험이 돌아갑니다. 첫 실행(2026-10-11)에서 Linux는 빌드와 설치가 통과했고 시험 546개 중 2개(위키 점검, locale 시험)가, macOS는 4개(위키 점검과 시험 3개)가 실패했습니다. Linux의 locale 시험은 [F115](../reference/verified-findings-opened.md)로 원인을 확인해 고쳤고, macOS의 시험 두 개는 시간 가정을 고쳤습니다. 수정 뒤 실행(2026-10-11, `38122943773`)은 Linux 5분 11초, macOS 17분 8초에 546개가 모두 통과했습니다(건너뜀 각각 136개, 141개, 예상된 실패 3개). wheel은 산출물로 보관되었습니다(Linux 약 155MB, macOS 약 147MB). 고치지 않은 macOS의 한국어 조합 밑줄 시험은 이번에 통과했지만 이전 실패의 원인은 확인하지 못했습니다.
- 전체 실행(`38157822305`, 2026-10-11)에서 Linux는 547개가 모두 통과했고, macOS는 한국어 조합 밑줄 시험 1개, Windows는 8개(페이지의 JavaScript 응답, 대화 상자, 화면 배율, 찾기 등을 기다리다 시간 초과)가 실패했습니다. Windows 러너에는 실제 데스크톱과 GPU가 없을 수 있다는 것은 추정이고, abi3 때문인지 러너 때문인지는 가리지 못했습니다(개발 컴퓨터에서 abi3 wheel로 같은 시험을 돌려 보는 것이 필요함). 그때까지 Windows는 **빌드와 wheel 설치의 성공만 릴리스 기준**으로 삼고, 시험 결과는 참고로만 봅니다.
- Linux aarch64: `platform=linux-arm`(러너 `ubuntu-24.04-arm`, 이미지 `manylinux_2_28_aarch64`)을 2026-10-12에 실행(`38181679332`)했습니다. `CMakeLists.txt`가 호스트가 ARM이면 `PROJECT_ARCH=arm64`와 `linuxarm64`를 고르게 한 뒤 빌드와 `auditwheel repair`가 통과해 `cefweaver-0.1.0-cp311-abi3-manylinux_2_28_aarch64.whl`이 만들어졌고, 시험 547개 중 1개가 실패했습니다(건너뜀 136, 예상된 실패 3). 실패한 것은 macOS에서도 실패하던 한국어 조합 밑줄 시험이며 이번 값은 `(160, 160)`입니다. 이 실패 때문에 산출물 보관 단계는 건너뛰었습니다. 원인은 러너에 한국어 글꼴이 없는 것이었습니다: `fc-list :lang=ko`가 비어 있었고(픽셀 수 `thin=160, thick=160, default=312, dotted=155`), apt 목록에 `fonts-noto-cjk`를 더해 다시 실행(`38189969143`)하자 547개가 모두 통과했습니다(`OK`, 건너뜀 136, 예상된 실패 3). macOS의 같은 시험 실패가 같은 원인인지는 확인하지 못했습니다(macOS 러너의 글꼴은 보지 않음). Windows ARM64 분기는 `CMakeLists.txt`에 넣었지만 실행하지 않았습니다.
- 푸시에는 토큰의 `workflow` 범위가 필요합니다. 이 컴퓨터의 `gh` 토큰에는 `gist`, `read:org`, `repo`, `write:packages`만 있습니다.

## abi3 (Linux x86_64만 확인)

- `pyproject.toml`의 `wheel.py-api = "cp311"`과 `CefweaverExtension.cmake`의 `USE_SABI 3.11`(`Development.SABIModule`)로 확장 모듈 `_cefweaver.abi3.so`를 만듭니다. Python 3.11 이상이면 wheel 하나(`cp311-abi3-<플랫폼>`)가 모두 받아서 Python 버전마다 wheel을 따로 내지 않습니다. Cython이 `Py_LIMITED_API`를 감지해 limited API 모드로 컴파일합니다. 시험 결과는 [F123](../reference/verified-findings-opened.md)에 있습니다.
- 저장소에서 만든 wheel(Python 3.12로 빌드)로 3.14 전체 시험 547개가 통과했습니다. macOS와 Windows의 abi3 빌드, 성능은 확인하지 못했습니다.

## manylinux (Linux x86_64만 확인)

- 호스트에서 만든 wheel은 태그가 `linux_x86_64`이고 `GLIBC_2.38`을 요구해 PyPI에 올릴 수 없습니다. manylinux_2_28 컨테이너에서 빌드하고 `auditwheel repair --exclude`(시스템 라이브러리 22개)로 태그를 붙이면 glibc 2.28(AlmaLinux 8)에서 시험이 통과합니다. 절차와 제외 목록은 [F122](../reference/verified-findings-opened.md)에 있습니다.
- 2026-10-12에 `build-test.yml`의 Linux 빌드 단계를 이 컨테이너 절차로 바꿨습니다(yum 패키지 설치, `uv build`, `auditwheel repair --exclude`). 제외 목록은 F122의 이름에 `.so`, `.so.0`, `.so.1`, `.so.2`를 붙여 만든 것입니다. Linux만 실행(`38180556005`, 2026-10-12, 9분 38초)하자 `cefweaver-0.1.0-cp311-abi3-manylinux_2_28_x86_64.whl`이 만들어졌고(산출물 약 157.6MB), 설치해서 시험 547개가 `OK`였습니다(건너뜀 136, 예상된 실패 3). 시험은 호스트(ubuntu-24.04)에 설치해서 합니다. aarch64, Windows ARM64, macOS x86_64, 여러 Python 버전과 PyPI의 크기 제한(wheel 약 155MB, 조합이 늘면 한 릴리스가 수 GB)은 계획 단계입니다.

## 관련 페이지

- [런타임 파일 배치](../concepts/runtime-layout.md)
- [tools/prepare.py](tool-prepare.md)
- [빌드와 설치](../procedures/build-and-install.md)
- [앱을 PyInstaller와 cx_Freeze로 묶기](../procedures/freeze-app.md)
- [scikit-build-core로 setup.py 없이 빌드하기 (프로토타입)](../analyses/scikit-build-core-prototype.md)
