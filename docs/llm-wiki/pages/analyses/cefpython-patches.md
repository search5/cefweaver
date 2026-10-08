---
title: cefpython의 CEF 패치와 cefweaver
type: analysis
sources:
  - tools/build_cef.py
  - native/cefwrapper/library.cpp
  - cefweaver/__init__.py
updated: 2026-10-08
---

# cefpython의 CEF 패치와 cefweaver

"cefpython은 왜 CEF에 자체 패치를 적용했고, cefweaver는 왜 그것을 가져오지 않았는가"에 답하려고 조사한 내용입니다. 조사한 자료: `/home/jiho/cef_framework/cefpython/docs/llm-wiki/pages/components/patches.md`와 `procedures/obtain-cef-binaries.md`, `tools/automate.py`, `patches/`의 파일들, 그리고 현재 CEF 소스 `/home/jiho/cef_framework/cef_origin`(master, 2026-09-29)입니다.

## cefpython의 패치

`patches/`의 파일과 적용 상태(cefpython 위키와 `patch.py` 기준)입니다.

| 파일 | 내용 | 상태 |
| --- | --- | --- |
| `issue231.patch` | `CefOverridePath`를 추가해 `PK_DIR_EXE`, `PK_DIR_MODULE` 경로를 덮어쓸 수 있게 함(Linux에서 `icudtl.dat` 탐색 실패, Issue #231) | `patch.py`에서 Linux일 때 적용 |
| `issue125.patch` | `ignore_certificate_errors`일 때 인증서 오류가 있어도 HTTPS 캐시에 쓰도록 함 | 비활성(v66부터) |
| `issue218_linux.patch` | wxWidgets의 `GtkPizza` 부모 위젯 처리(`browser_host_impl_gtk.cc`) | `patch.py`에서 참조하지 않음 |
| `issue73_linux`, `include.gypi` | tcmalloc 문제를 `use_allocator=none`으로 해결 | Spotify 빌드에는 2016-06부터 이미 적용 |

**패치는 `automate.py --build-cef`로 CEF를 소스에서 빌드할 때만** 적용됩니다. 위키(2017년 문서 기준)에 따르면 Windows와 Mac은 Spotify의 prebuilt를 그대로 썼고 Linux만 사용자 패치를 적용한 바이너리를 썼습니다. cefpython의 `automate.py`는 `patches/*.patch`를 CEF의 `patch/patches/`로 복사하고 `patch/patch.cfg`에 `patch.py`의 내용을 덧붙입니다.

## 현재 CEF에 적용되는가

CEF master(2026-09-29)에서 `git apply --check -p0 issue231.patch`로 확인했습니다. 수정은 하지 않았습니다.

- 패치가 건드리는 파일 5개 가운데 **3개가 현재 CEF에 없습니다**: `include/capi/cef_path_util_capi.h`, `libcef_dll/libcef_dll.cc`, `libcef_dll/wrapper/libcef_dll_wrapper.cc`. `include/cef_path_util.h`와 `libcef/browser/path_util_impl.cc`는 있습니다.
- 현재 CEF의 `include/`와 `libcef/`에는 `OverridePath`/`cef_override_path`가 **없습니다**. 즉 같은 API가 정식으로 들어오지도 않았습니다.
- `issue218_linux.patch`의 대상 `libcef/browser/browser_host_impl_gtk.cc`가 없습니다.

그러므로 이 패치들은 그대로는 적용되지 않습니다. 다른 CEF 버전(154 배포본이 아닌 master)에서 확인한 것이어서 154의 정확한 상태는 아닙니다.

## cefweaver가 패치를 가져오지 않은 이유

1. **기본이 prebuilt입니다.** 패치는 소스 빌드에만 적용되는데, 이 프로젝트의 기본 흐름은 CEF 빌드 서버의 배포본을 내려받는 것입니다.
2. **문제를 배치로 피합니다.** issue231이 해결하려던 것은 `icudtl.dat`를 찾지 못하는 문제입니다. CEF 154 Linux에서 `icudtl.dat`는 `libcef.so`가 있는 디렉터리에서 찾고 `resources_dir_path`로는 바뀌지 않는다는 것을 시험으로 확인했습니다. 따라서 런타임 파일을 `libcef.so`와 같은 디렉터리에 두면 문제가 없고 패치가 필요하지 않습니다([런타임 파일 배치](../concepts/runtime-layout.md), [실험으로 확인한 사실](../reference/verified-findings.md) F1). 패치가 필요한 경우는 런타임 파일을 `libcef.so`와 다른 곳에 두고 싶을 때입니다.
3. **패치가 현재 CEF에 맞지 않습니다.** 위에서 확인했습니다.
4. **`build_cef.py`에는 패치 적용 장치가 없습니다.** 필요해지면 cefpython처럼 `cef/patch/patches/`와 `patch.cfg`를 이용하는 방식을 따를 수 있습니다. `automate-git.py`는 `--no-cef-update`와 `--force-patch-update` 같은 옵션을 가지고 있습니다(옵션 이름만 확인).

## 열린 질문

- 현재 CEF가 `icudtl.dat`나 리소스 위치를 바꾸는 다른 정식 방법을 제공하는지는 조사하지 않았습니다.
- tcmalloc 문제(issue73)에 해당하는 설정을 `GN_DEFINES`의 `use_allocator=none`으로 소스 빌드에 넣었으나 CEF 154에서 필요한지는 확인하지 못했습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [CEF 확보 방식](../concepts/cef-acquisition.md)
- [tools/build_cef.py](../components/tool-build-cef.md)
- [관련 프로젝트](../reference/related-projects.md)
