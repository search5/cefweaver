---
title: tools/prepare.py
type: component
sources:
  - tools/prepare.py
  - tools/build_cef.py
  - CMakeLists.txt
updated: 2026-10-08
---

# tools/prepare.py

`uv build --wheel` 전에 실행하는 사전 준비 도구입니다. 표준 라이브러리만 씁니다(`build_cef.py`를 가져와 소스 빌드 옵션을 공유). 이 분리의 이유는 확장 모듈을 빌드할 때 CEF의 헤더와 컴파일된 라이브러리가 이미 있어야 하기 때문입니다([설계 결정 기록](../reference/design-decisions.md)).

## 하는 일 (main의 순서)

1. `--list-versions`이면 목록만 보여 주고 끝냅니다.
2. `--build-cef`이면 `build_cef.build_cef(args)`로 CEF를 소스 빌드하고 결과 경로를 `--cef-root`로 삼습니다. `--dry-run`이면 여기서 끝납니다. `--cef-root`와 함께 쓰면 오류입니다.
3. CEF 루트를 정합니다(`--cef-root`, 환경변수 `CEF_ROOT`). 지정한 경로에 `cmake/FindCEF.cmake`가 없으면 오류입니다.
4. `--cef-version`이 있고 루트가 없으면 인덱스에서 이름을 검증합니다(`validate_cef_version`).
5. `cmake -S <저장소> -B <빌드 디렉터리> -DCMAKE_BUILD_TYPE=... -DPYTHON_EXECUTABLE=...`. 루트가 있으면 `-DCEF_ROOT=`, 없으면 `-UCEF_ROOT`(캐시에 남은 값 제거), `--cef-version`이 있으면 `-DCEF_VERSION=`을 덧붙입니다.
6. `cmake --build`.
7. `CMakeCache.txt`에서 `CEFWEAVER_CEF_ROOT`를 읽어 확정 경로를 얻습니다.
8. `build/native/cef`에 링크를 만듭니다(`link_cef`; Windows는 `mklink /J` junction).
9. `--no-stage`가 아니면 런타임을 `cefweaver/`에 스테이징합니다(`stage_runtime`, Linux만).
10. `build/native/prepare.json`에 `cef_root`, `cef_link`, `staged`, `build_dir`, `config`를 기록합니다.

## 옵션

| 옵션 | 설명 |
| --- | --- |
| `--cef-root PATH` | 기존 CEF 배포본 사용 |
| `--cef-version NAME` | prebuilt 전체 버전 이름 (접두사는 거부) |
| `--list-versions [FILTER]` | 전체 버전 이름 목록. `FILTER`는 앞부분이 같은 것만 걸러서 보여 주는 용도 |
| `--channel {stable,beta}`, `--limit N` (0은 전체), `--platform KEY`, `--refresh-index` | 목록 조회 옵션 |
| `--build-cef` 및 `--cef-build-dir`, `--fast-build`, `--proprietary-codecs`, `--gn-defines`, `--no-depot-tools-update`, `--rebuild`, `--skip-resource-check`, `--offline`, `--dry-run` | 소스 빌드([tools/build_cef.py](tool-build-cef.md)) |
| `--no-stage`, `--no-strip` | 런타임 스테이징 생략, 스테이징한 `libcef.so`의 strip 생략 |
| `--build-dir DIR`, `--config {Debug,Release}` | 빌드 디렉터리(기본 `build/native`)와 구성(기본 `Release`) |

## 버전 조회

- `detect_cef_platform()`이 플랫폼 키(`linux64` 등)를 정합니다. ARM이면 `linuxarm64`처럼 키는 만들지만 이 프로젝트는 ARM을 지원하지 않습니다.
- `load_index()`가 `https://cef-builds.spotifycdn.com/index.json`을 받아 `build/native/cef_index.json`에 24시간 캐시합니다. 실패하면 만료된 캐시를 경고와 함께 쓰고, 캐시도 없으면 오류입니다.
- `standard_builds()`가 `standard` 배포본이 있는 버전을 **버전 번호 기준 최신순**으로 돌려줍니다. 인덱스 자체의 순서는 빌드 날짜순이라 쓰지 않습니다. 옛 형식 이름(`3.3683.1920.g9f41a27`)도 정렬할 수 있도록 앞쪽 숫자 부분만 키로 씁니다.
- 기본 버전 표시는 `CMakeLists.txt`의 `set(CEF_VERSION "...")`를 정규식으로 읽습니다.

## 런타임 스테이징

`stage_runtime()`은 이전에 스테이징한 항목(`build/native/staged_runtime.json`)을 지우고, CEF 배포본의 `Release/`와 `Resources/` 아래 모든 항목(`chrome-sandbox` 제외)과 `cefsubprocess`를 `cefweaver/`로 복사합니다. `libcef.so`의 **복사본**만 `strip --strip-unneeded`합니다. CEF 배포본 자체는 건드리지 않습니다. 결과 배치는 [런타임 파일 배치](../concepts/runtime-layout.md)에 있습니다.

## 관련 페이지

- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [tools/build_cef.py](tool-build-cef.md)
- [빌드와 설치](../procedures/build-and-install.md)
- [패키징](packaging.md)
