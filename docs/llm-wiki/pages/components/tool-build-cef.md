---
title: tools/build_cef.py
type: component
sources:
  - tools/build_cef.py
  - tools/prepare.py
  - README.rst
updated: 2026-10-08
---

# tools/build_cef.py

cefpython의 `automate.py --build-cef`에 해당하는 소스 빌드 도구입니다. 단독 실행(`python tools/build_cef.py ...`)도 되고 `prepare.py --build-cef`가 불러 쓰기도 합니다. **실제 빌드는 실행하지 못했습니다**(이 개발 환경의 디스크 여유가 약 69GB로 요구량에 못 미칩니다). 확인한 것은 계획 출력, 브랜치와 커밋 검증, 옵션, 안전장치입니다.

## 흐름 (build_cef 함수)

1. **버전 해석**: `parse_version()`이 전체 이름에서 브랜치와 커밋을 뽑습니다. `154.0.34+g14c5a08+chromium-154.0.8037.98` → 브랜치 `8037`(Chromium 빌드 번호), 커밋 `14c5a08`. 옛 형식 `3.3683.1920.g9f41a27`도 처리합니다(브랜치 `3683`). 접두사만 준 이름(`120`)은 거부합니다.
2. **환경 검사**(`check_environment`): Linux x86_64만, `git`과 `python3`가 PATH에 있어야 하고, 경로에 공백이 없어야 하며, 디스크 여유 120GB와 메모리 16GB를 확인합니다. 자원 부족은 `--skip-resource-check`가 없으면 오류로 중단하고 **아무것도 내려받기 전에** 끝냅니다(`--dry-run`에서는 보고만 합니다).
3. **원격 검증**(`remote_checks`, `--offline`이면 생략): `git ls-remote https://github.com/chromiumembedded/cef.git refs/heads/<브랜치>`로 브랜치가 있는지, 그 끝 커밋이 요청한 커밋인지 알려 줍니다. 브랜치가 없으면 오류입니다.
4. **기존 배포본 재사용**: `<cef-build-dir>/chromium/src/cef/binary_distrib/`에 완전한 `cef_binary_*_linux64`가 이미 있으면 빌드하지 않습니다(`--rebuild`로 강제).
5. **스크립트 받기**: 요청한 커밋의 `tools/automate/automate-git.py`를 GitHub raw에서 받아 빌드 디렉터리에 둡니다(버전이 맞는 스크립트를 쓰기 위해서입니다).
6. **명령 구성과 실행**: 아래 명령을 환경변수 `GN_DEFINES`와 함께 실행합니다.
7. **결과 탐색**(`find_distribution`): `_minimal`, `_client`, `_sandbox`, `_tools`, `_symbols` 접미사를 제외하고 `cmake/FindCEF.cmake`가 있는 가장 최근 디렉터리를 고릅니다.

## automate-git.py 명령

```
python automate-git.py --download-dir=<dir> --depot-tools-dir=<dir>/depot_tools
    --branch=<브랜치> --checkout=<커밋> --x64-build --no-debug-build
    --build-target=cefsimple --force-build
    [--no-chromium-history] [--no-distrib-archive] [--with-pgo-profiles]
    [--no-depot-tools-update]
```

선택 플래그(`--no-chromium-history`, `--no-distrib-archive`, `--with-pgo-profiles`)는 **받은 스크립트의 텍스트에 그 옵션이 있을 때만** 붙입니다. `--with-pgo-profiles`는 `--fast-build`이면 빼 줍니다. 154 커밋의 스크립트에는 이 옵션들과 `--download-dir`, `--depot-tools-dir`, `--branch`, `--checkout`, `--x64-build`, `--no-debug-build`, `--build-target`, `--force-build`, `--no-depot-tools-update`가 모두 있음을 확인했습니다.

## GN_DEFINES

| 경우 | 값 |
| --- | --- |
| 기본 | `is_official_build=true use_sysroot=true use_allocator=none symbol_level=1 is_cfi=false` |
| `--fast-build` | `is_official_build` 없이 나머지 동일 |
| `--proprietary-codecs` | 위에 `proprietary_codecs=true ffmpeg_branding=Chrome` 추가 |
| `--gn-defines TEXT` | 위 모두 무시하고 `TEXT`만 사용 |

기본값은 CEF 문서(`automated_build_setup.md`의 Linux 구성)를 바탕으로 했고, `use_allocator=none`은 이 프로젝트에서 덧붙인 설정입니다(CEF 문서의 해당 구성에는 없습니다). cefpython이 Python에 CEF를 올릴 때 tcmalloc 문제를 피하려고 같은 설정을 썼기 때문인데, CEF 154에서도 필요한지는 확인하지 못했습니다. 필요 없으면 `--gn-defines`로 바꿉니다.

## 한계

- cefpython의 `--build-cef`와 달리 CEF에 자체 패치를 적용하지 않습니다([cefpython의 CEF 패치와 cefweaver](../analyses/cefpython-patches.md)).
- Linux 외 플랫폼은 구현하지 않았고 오류로 중단합니다.
- 소스 빌드로 만든 배포본이 `prepare.py`의 나머지 흐름(CMake 빌드, 스테이징)에서 prebuilt와 똑같이 동작하는지는 확인하지 못했습니다.

## 관련 페이지

- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [tools/prepare.py](tool-prepare.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
