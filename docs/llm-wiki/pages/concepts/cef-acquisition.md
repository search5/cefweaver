---
title: CEF 확보 방식
type: concept
sources:
  - CMakeLists.txt
  - cmake/DownloadCEF.cmake
  - tools/prepare.py
  - tools/build_cef.py
updated: 2026-10-08
---

# CEF 확보 방식

cefweaver는 `libcef.so`(CEF 본체)를 컴파일하지 않고 **이미 만들어진 CEF 배포본**을 가져다 씁니다. 배포본을 얻는 방법은 세 가지이고, 어느 쪽이든 결과는 같은 모양의 `cef_binary_<버전>_<플랫폼>/` 디렉터리입니다(`cmake/FindCEF.cmake`, `include/`, `Release/`, `Resources/`, `libcef_dll/` 포함).

| 방법 | 명령 | 설명 |
| --- | --- | --- |
| prebuilt 자동 다운로드(기본) | `python tools/prepare.py` | CEF 빌드 서버(`cef-builds.spotifycdn.com`)의 `standard` 배포본(`.tar.bz2`)을 받아 `third_party/cef/`에 풉니다. SHA1을 검증합니다. |
| 기존 디렉터리 지정 | `--cef-root PATH` 또는 환경변수 `CEF_ROOT` | 직접 빌드했거나 이미 풀어 둔 배포본을 씁니다. |
| 소스 빌드 | `python tools/prepare.py --build-cef` | CEF의 `automate-git.py`로 Chromium과 CEF를 빌드해 배포본을 만듭니다. |

우선순위는 `--cef-root`, 환경변수 `CEF_ROOT`, 자동 다운로드 순입니다(`CMakeLists.txt` 68~85행, `tools/prepare.py`).

## prebuilt

기본 버전은 `CMakeLists.txt`의 `CEF_VERSION`(현재 `154.0.34+g14c5a08+chromium-154.0.8037.98`)입니다. `--cef-version`으로 바꿀 수 있고 **전체 버전 이름**만 받습니다. `--list-versions [필터]`는 CEF 빌드 서버의 `index.json`(약 10MB)을 받아 현재 플랫폼의 `standard` 배포본 전체 이름을 최신순으로 보여 줍니다. 인덱스는 `build/native/cef_index.json`에 24시간 캐시되고, 네트워크가 안 되면 만료된 캐시를 경고와 함께 씁니다. `--cef-version`은 인덱스에 있는 이름인지 먼저 검증합니다.

## 소스 빌드 (--build-cef)

`tools/build_cef.py`(`prepare.py`가 불러 씁니다)는 전체 버전 이름에서 CEF 브랜치와 커밋을 뽑습니다. `154.0.34+g14c5a08+chromium-154.0.8037.98`이면 브랜치는 Chromium 빌드 번호 `8037`, 커밋은 `14c5a08`입니다. 이 가정은 CEF 저장소에서 브랜치 `8037`의 최신 커밋이 `14c5a089...`임을 `git ls-remote`로 확인했습니다. 그다음 해당 커밋의 `automate-git.py`를 GitHub에서 받아 `GN_DEFINES`를 설정하고 실행하며, 결과인 `chromium/src/cef/binary_distrib/cef_binary_*_linux64`를 찾아 `--cef-root`처럼 넘깁니다.

필요 자원은 디스크 약 120GB, 메모리 16GB 이상이며 몇 시간이 걸립니다. 이 자원을 미리 확인하고 부족하면 아무것도 내려받기 전에 중단합니다. `--dry-run`으로 계획과 명령만 볼 수 있습니다. **실제 빌드는 실행하지 못했습니다**: 이 개발 환경의 디스크 여유가 약 69GB여서 `--dry-run`, 옵션 검증, 안전장치까지만 확인했습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md), [tools/build_cef.py](../components/tool-build-cef.md)).

## 확보 뒤에 일어나는 일

`prepare.py`는 CMake가 `CEFWEAVER_CEF_ROOT`에 기록한 확정 경로를 읽어서 `build/native/cef`에 링크(Windows는 junction)를 만들고, 이후 단계(`pyproject.toml`의 `include-dirs`, `library-dirs`)는 이 고정 경로만 봅니다. 그래서 prebuilt와 소스 빌드의 차이가 이후 단계에 드러나지 않습니다.

## 캐시된 CEF_ROOT 결함

초기에는 `DownloadCEF.cmake`가 `CEF_ROOT`를 CMake 캐시(`CACHE INTERNAL`)에 남겼습니다. 그러면 이후 실행에서 사용자 지정 값과 구분할 수 없어 `--cef-version`을 바꿔도 **조용히 옛 버전이 사용**되었습니다. 지금은 `CEF_ROOT`를 캐시하지 않고, 확정 경로는 `CEFWEAVER_CEF_ROOT`에만 기록하며, `--cef-root`가 없으면 `-UCEF_ROOT`로 캐시에 남은 값을 지웁니다. 세 경우(옛 캐시에서 새 버전 요청, `--cef-root` 지정, 이후 지정 없이 새 버전 요청)를 실행해 확인했습니다.

## 관련 페이지

- [tools/prepare.py](../components/tool-prepare.md)
- [루트 CMake와 CEF 다운로드](../components/root-cmake.md)
- [CEF 확보하기](../procedures/obtain-cef.md)
- [cefpython의 CEF 패치와 cefweaver](../analyses/cefpython-patches.md)
