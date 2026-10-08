---
title: CEF 확보하기
type: procedure
sources:
  - tools/prepare.py
  - tools/build_cef.py
  - README.rst
updated: 2026-10-08
---

# CEF 확보하기

개념은 [CEF 확보 방식](../concepts/cef-acquisition.md)에 있습니다. 모든 명령은 저장소 루트에서 실행합니다.

## 가능한 prebuilt 버전 보기

```sh
python tools/prepare.py --list-versions                  # 현재 플랫폼의 stable 최신 20개
python tools/prepare.py --list-versions 154              # 154로 시작하는 버전만
python tools/prepare.py --list-versions --channel beta   # beta 채널
python tools/prepare.py --list-versions --limit 0        # 제한 없이 전체
python tools/prepare.py --list-versions --platform windows64   # 다른 플랫폼의 목록
```

출력의 첫 열은 **전체 버전 이름**이며 그대로 복사해서 `--cef-version`에 쓸 수 있습니다. 기본 버전 줄에는 `<- default`가 표시됩니다. 최신순은 버전 번호 기준입니다. 인덱스는 하루 캐시하고, `--refresh-index`로 강제 갱신합니다.

## 방법 1: prebuilt 다운로드

```sh
python tools/prepare.py                                                        # 기본 버전
python tools/prepare.py --cef-version "154.0.34+g14c5a08+chromium-154.0.8037.98"
```

`--cef-version`은 **전체 이름만** 받습니다. `120` 같은 접두사를 주면 "not an available build"로 거부합니다(어떤 빌드가 선택될지 모호하고 기록의 재현성이 떨어지기 때문입니다). 이름이 인덱스에 없으면 내려받기 전에 실패합니다.

## 방법 2: 이미 있는 배포본 지정

```sh
python tools/prepare.py --cef-root /path/to/cef_binary_154.0.34+g14c5a08+chromium-154.0.8037.98_linux64
CEF_ROOT=/path/to/cef_binary_... python tools/prepare.py
```

디렉터리에 `cmake/FindCEF.cmake`가 있어야 합니다. 소스 빌드 결과는 `chromium/src/cef/binary_distrib/cef_binary_*_linux64`를 지정합니다. `--cef-root`를 주면 `--cef-version`은 무시되고 경고가 나옵니다.

## 방법 3: 소스 빌드

```sh
python tools/prepare.py --build-cef --dry-run          # 계획과 명령만 확인 (필수 권장)
python tools/prepare.py --build-cef --cef-build-dir /data/cef_src --proprietary-codecs
```

필요 자원은 디스크 약 120GB, 메모리 16GB 이상, 수 시간입니다. 기본 저장 위치는 `build/cef_src`이며 경로에 공백이 없어야 합니다. 이미 만들어진 배포본이 있으면 재사용하고 `--rebuild`로 강제합니다. **실제 빌드는 검증하지 못했으므로** 처음 실행하면 첫 결과를 확인하고 필요하면 `--gn-defines`를 조정합니다([tools/build_cef.py](../components/tool-build-cef.md)).

## 확인

`prepare.py`의 마지막 출력이 확정된 `CEF_ROOT`를 보여 줍니다. 빌드 중에 `CEF version in use: ...`가 한 번 출력되어 실제로 쓰는 버전을 알 수 있습니다. 같은 `build/native`에서 버전을 바꿔도 이전 버전이 고정되지 않음을 세 경우로 확인했습니다.

## 관련 페이지

- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [CEF 버전 올리기](update-cef-version.md)
- [tools/prepare.py](../components/tool-prepare.md)
