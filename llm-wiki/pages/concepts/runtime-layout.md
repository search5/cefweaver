---
title: 런타임 파일 배치
type: concept
sources:
  - cefweaver/__init__.py
  - native/cefwrapper/library.cpp
  - tools/prepare.py
  - native/cefsubprocess/CMakeLists.txt
  - pyproject.toml
  - native/cefwrapper/mac_runtime.mm
  - setup.py
updated: 2026-10-09
---

# 런타임 파일 배치

Linux에서 CEF는 실행 중에 `libcef.so`와 여러 리소스 파일이 필요합니다. cefweaver는 이 파일들을 **확장 모듈과 같은 디렉터리**(`cefweaver/` 패키지 디렉터리)에 둡니다.

## 배치

154 배포본 기준으로 `tools/prepare.py`가 패키지 디렉터리에 복사하는 항목은 11개입니다.

| 항목 | 설명 |
| --- | --- |
| `libcef.so` | CEF 본체. 복사본만 `strip --strip-unneeded`합니다(1.45GB에서 약 272MB). |
| `libvk_swiftshader.so`, `libvulkan.so.1`, `vk_swiftshader_icd.json` | 소프트웨어 Vulkan 구현과 그 설정 |
| `v8_context_snapshot.bin` | V8 스냅샷 |
| `icudtl.dat` | ICU 데이터 |
| `resources.pak`, `chrome_100_percent.pak`, `chrome_200_percent.pak` | 리소스 팩 |
| `locales/` | 지역별 리소스 |
| `cefsubprocess` | 서브프로세스 실행 파일(우리가 컴파일) |

CEF 배포본의 `Release/`와 `Resources/` 아래 항목을 모두 복사하되 `chrome-sandbox`만 제외합니다(샌드박스를 쓰지 않으므로). 그래서 CEF 버전마다 항목 수가 달라질 수 있습니다(이전에 쓰던 120 배포본에는 `snapshot_blob.bin`도 있었습니다). 복사한 총량은 약 359MB, 만들어진 wheel은 약 148MB, 설치하면 약 363MB입니다.

## 같은 디렉터리여야 하는 이유

시험으로 확인한 사실입니다([실험으로 확인한 사실](../reference/verified-findings.md)).

- **CEF 154는 Linux에서 `icudtl.dat`를 `libcef.so`가 있는 디렉터리에서 찾습니다.** `libcef.so`와 리소스를 서로 다른 디렉터리에 두고 `resources_dir_path`를 정확히 지정해도 `Invalid file descriptor to ICU data received`로 초기화가 실패했습니다. 같은 디렉터리에 두면 `resources_dir_path`가 가짜 경로여도 성공했습니다. 따라서 `CefApp.set_resources_path()`는 `icudtl.dat`에 영향을 주지 못하고, 기본값은 설정하지 않는 것입니다.
- `cefweaver/__init__.py`가 확장 모듈을 가져오기 **전에** `ctypes.CDLL(libcef.so, RTLD_GLOBAL)`로 `libcef.so`를 먼저 올립니다. cefpython이 같은 방식을 쓰고, java-cef의 실행 스크립트는 `LD_PRELOAD=libcef.so`를 설정합니다.
- 확장 모듈과 `cefsubprocess`는 모두 `$ORIGIN`을 RPATH로 가져서 같은 디렉터리의 `libcef.so`를 찾습니다(`pyproject.toml`의 `extra-link-args`, `native/cefsubprocess/CMakeLists.txt`의 `INSTALL_RPATH`).

서브프로세스 실행 파일도 같은 디렉터리에 두면 `libcef.so`를 두 곳에 복사하지 않아도 됩니다. 기본 서브프로세스 경로가 `<모듈 디렉터리>/cefsubprocess`인 이유입니다. 모듈 디렉터리는 `dladdr()`로 알아냅니다(`library.cpp`의 `ModuleDir()`).

## macOS

macOS는 `libcef.so` 대신 `Chromium Embedded Framework.framework`이고, 도우미가 5개이며, 모두 가짜 메인 번들 안에 둡니다.

```
cefweaver/_cefweaver.cpython-3xx-darwin.so
cefweaver/cefsubprocess.app/Contents/Info.plist
cefweaver/cefsubprocess.app/Contents/Frameworks/Chromium Embedded Framework.framework/
cefweaver/cefsubprocess.app/Contents/Frameworks/cefsubprocess Helper.app
                                               .../cefsubprocess Helper (Alerts|GPU|Plugin|Renderer).app
```

- 도우미는 자기 위치에서 `../../..`(자기 `.app`이 든 디렉터리)에 프레임워크가 있기를 기대합니다(`CefScopedLibraryLoader::LoadInHelper()`가 그렇게 찾음). 그래서 도우미 앱과 프레임워크가 같은 `Contents/Frameworks/` 안에 나란히 있어야 합니다.
- 브라우저 프로세스(Python)는 `CefSettings.main_bundle_path`(`cefsubprocess.app`)와 `framework_dir_path`로 이 배치를 CEF에 알립니다. `browser_subprocess_path`는 도우미(`cefsubprocess Helper`)의 실행 파일입니다.
- 프레임워크는 확장 모듈을 가져올 때 `cef_load_library()`로 올립니다(`__init__.py`에서 미리 올릴 것은 없음). 아이콘이나 리소스는 프레임워크 안의 `Resources/`에 있어 따로 복사하지 않습니다.
- CEF 154의 프레임워크는 `Versions/` 없는 평평한 구조라 wheel(zip)에 담아도 구조가 깨지지 않습니다. 서명은 배포본과 CMake가 만든 ad hoc 서명 그대로입니다(F79).

## 개발 트리와 wheel

스테이징된 파일은 `.gitignore`로 git에서 제외되고, `MANIFEST.in`으로 sdist에서도 제외됩니다. wheel에는 `package-data` 규칙으로 포함됩니다([패키징](../components/packaging.md)). 개발 중에 같은 디렉터리의 파일을 바꾸면 설치된 wheel이 아니라 이 디렉터리가 바뀐 것입니다. 시험은 설치된 wheel을 대상으로 합니다([시험](../components/tests.md)).

Windows의 배치는 다릅니다. 서브프로세스 기본 경로가 현재 작업 디렉터리 기준 `cefsubprocess/cefsubprocess.exe`이며 이 경로는 검증하지 못했습니다([플랫폼 지원 현황](platform-support.md)).

## 관련 페이지

- [CEF 확보 방식](cef-acquisition.md)
- [tools/prepare.py](../components/tool-prepare.md)
- [프로세스 모델과 스레드](process-model-and-threads.md)
- [앱을 PyInstaller와 cx_Freeze로 묶기](../procedures/freeze-app.md)
