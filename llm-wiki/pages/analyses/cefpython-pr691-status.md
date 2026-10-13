---
title: cefpython PR 691 (CEF 147 갱신)의 상황과 cefweaver에 주는 의미
type: analysis
sources:
  - cmake/DownloadCEF.cmake
  - tools/prepare.py
  - tools/build_cef.py
  - tools/stability/reload_bindings.py
  - native/cefwrapper/generated/cefweaver_proxies.h
  - native/cefwrapper/library.cpp
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - cefweaver/bridge.py
updated: 2026-10-13
---

# cefpython PR 691 (CEF 147 갱신)의 상황과 cefweaver에 주는 의미

cefpython 저장소의 PR [#691](https://github.com/cztomczak/cefpython/pull/691) 본문, 일반 댓글 68개, 리뷰 183개(본문이 있는 것 6개), 코드 리뷰 댓글 342개를 `gh api`로 받아 모두 읽었습니다(2026-10-13). 읽은 시점의 사실이고 PR은 계속 바뀝니다.

## PR의 상태

- 제목은 "Add CEF 147, Python 3.10–3.14, Linux/macOS ARM64/Windows support with modern build system"이고 상태는 **열림(미병합)**입니다. 작성자는 `linesight`(기여자), 검토자는 저장소 소유자 `cztomczak`입니다.
- 2026-05-03에 열렸고 마지막 활동은 2026-10-12(소유자의 쿠키 콜백 지적)입니다. 커밋 100개, 파일 259개, +15,231/-22,977줄입니다.
- 소유자의 리뷰는 모두 `CHANGES_REQUESTED`입니다(2026-06-08, 06-09, 06-10 두 번, 07-27, 10-08). 병합 가능 상태는 `clean`이지만 승인은 없습니다.
- 작성자가 2026-06-29에 빌드 시스템을 따로 PR로 떼자고 했으나 소유자는 같은 검토를 반복하기 싫다며 거절했고, 07-03에도 이 PR에서 빌드 시스템 변경을 더 늘리지 말라고 했습니다.
- cefpython의 마지막 정식 릴리스는 v66.1(2021-02-16)입니다. 이 PR은 CEF 66(2018)에서 147로 올리는 것이고, 먼저 `cefpython123` 브랜치(CEF 123)에서 한 작업을 이어받습니다(소유자가 `cefpython147` 브랜치를 만들어 기준으로 삼음).

## PR의 내용

- CEF 147.0.10(Chromium 147), Python 3.10~3.14, Windows 10+ x64, Linux x64(GTK3/X11), macOS arm64(Intel 제외). 빌드를 scikit-build-core와 CMake로 바꾸고 GitHub Actions가 플랫폼 세 개와 Python 다섯 버전의 wheel을 만듭니다. Cython 3.2로 올렸습니다.
- 작성자는 AI(Claude)를 쓴 것을 밝혔고, 소유자가 "AI가 만든 변경을 모두 확인하느냐"고 물었습니다(작성자: 검토하지만 일관성이 어긋난 곳을 놓쳤다).

## 검토에서 문제가 된 것

- **근거 없는 우회책**: X11/XWayland 임베딩, Wayland 창 관리, 메시지 루프 교체, 브라우저 생성을 미루는 폴링 등. 소유자가 CEF/Chromium 이슈나 커밋 근거를 요구했고 작성자가 대부분 철회했습니다. 소유자의 방침은 "우회책은 CEF Python 이슈 트래커에 이슈가 있고 논의된 뒤에만 받는다"입니다. 네이티브 Wayland 임베딩은 CEF 자체의 미해결 이슈([#2804](https://github.com/chromiumembedded/cef/issues/2804))라 cefpython이 직접 구현하지 않기로 했습니다.
- **침묵하는 조기 반환**: 쿠키·로드·V8 콜백에서 `browser`/`frame`이 NULL일 때 조용히 건너뛰는 코드. CEF 헤더가 이 값들이 service worker나 `CefURLRequest` 요청에서 NULL일 수 있다고 적었으므로 허용하되 로그와 문서를 요구했습니다. 2026-10-12에도 `CanSendCookie`/`CanSaveCookie`가 NULL일 때 `False`를 돌려주는 오류가 지적되었습니다.
- **예외 전파**: Cython 3으로 `except *`를 `noexcept`로 바꾸자 핸들러에서 새는 예외가 `sys.unraisablehook`으로 가서 놓치기 쉬워졌습니다. `cef.UnraisableHook` 어댑터를 두기로 했고 문서화 요구가 남았습니다.
- **빌드와 배포**: 표준 헤더를 byte 단위로 같게 다시 가져오기, SHA1 검증 필수화, `tarfile` 경로 탈출 방어, 버전 체계(`147.0.devN+g해시`), wheel을 설치해서 시험하기, 예제의 스모크 시험, Linux wheel 크기(strip 전 356 MB, 심볼 테이블을 남기면 약 166 MB), `msvcp140.dll` 동봉.
- **문서**: 이전 버전(v66+)부터의 이전 가이드가 없다는 점과 가이드에 Cython 내부 사정이 들어간 점.
- **시험의 불안정**: CI의 헤드리스 GUI 시험에 드문 실패가 있었고, 소유자는 CI 전용 Chromium 스위치를 시험에 넣지 말고 기본 설정으로 돌리라고 했습니다.
- 이 과정에서 열린 이슈: [#695](https://github.com/cztomczak/cefpython/issues/695)(Chromium 샌드박스 켜기, 지금은 모든 플랫폼에서 꺼짐), [#696](https://github.com/cztomczak/cefpython/issues/696)(GCC `-Wstringop-overflow`), [#699](https://github.com/cztomczak/cefpython/issues/699)(Chromium 146 이상에서 `Reload()` 뒤 JavaScript 바인딩이 깨짐).

## cefweaver에 주는 의미

**상황 판단**
- cefpython의 CEF 갱신은 5개월째 병합되지 않았고, 검토자가 작업 범위와 근거에 엄격해서 끝나는 시점을 알 수 없습니다. 병합되더라도 CEF 147이고 Alloy 런타임이 없는 구조(아래)와 GTK3/X11 중심이라, cefweaver(CEF 154, 생성된 API, 오프스크린 툴킷 어댑터 일곱 개)와는 접근이 다릅니다.
- 같은 문제를 마주하고 있습니다: 샌드박스 비활성(cefweaver도 `no_sandbox`, [프로덕션 배포 가능성](../reference/production-readiness.md)), 네이티브 Wayland 임베딩 불가(CEF 한계), 시험 안정성, wheel 크기.

**직접 확인한 것(2026-10-13, CEF 154, Linux, 설치된 wheel)**
- cefpython #699(`Reload()` 뒤 바인딩이 깨짐)는 **cefweaver에서 재현되지 않았습니다.** `tools/stability/reload_bindings.py`가 `JavascriptBridge.expose`와 `add_javascript_binding`을 페이지에서 부르며 재로드 3번, 같은 사이트 이동, 다른 사이트 이동, 원래 사이트로 복귀를 거쳐 호출이 일곱 번 모두 도착했습니다(`calls {'bridge': 7, 'binding': 7}`). 이 시험의 한계: 뒤로 가기는 bfcache에서 되살아나 스크립트가 다시 실행되지 않아 포함하지 않았고, Windows와 macOS에서는 돌리지 않았습니다.
- `browser`/`frame`이 NULL일 수 있는 콜백에서 cefweaver는 **None으로 넘깁니다**: 생성된 프록시가 `browser.get()`/`frame.get()`을 그대로 넘기고 스텁의 타입은 `Browser | None`, `Frame | None`입니다(`CookieAccessFilter.can_send_cookie` 등, 헤더의 `optional_param`을 따름). 콜백이 건너뛰어지지 않고 Python 핸들러에 도달합니다. 다만 service worker나 `URLRequest` 출처의 쿠키 콜백이 실제로 오는 상황은 이번에 시험하지 않았습니다.
- cefweaver는 CEF 154에서 Alloy 런타임 스타일(`CEF_RUNTIME_STYLE_ALLOY`)로 브라우저를 만들고(`cef_wrapper_browser_process_handler.cc:95`) 시험이 이를 확인합니다. cefpython 쪽 작성자가 한때 "Alloy 런타임이 M128에서 제거되어 초기화 직후 브라우저를 만들 수 없다"고 주장했으나 나중에 "문장이 뒤섞였고 타이밍 문제일 뿐"이라며 철회했습니다.

**참고할 점**
- 소유자가 요구한 "우회책마다 이슈, 근거, 제거 조건" 방식은 `known-constraints.md`의 운영 방식과 같은 방향입니다.
- Linux wheel 크기 논의: 심볼 테이블(`.symtab`)을 남기고 DWARF만 제거하면 약 +26 MB로 심볼화된 역추적을 얻는다는 계산이 나왔습니다. cefweaver의 wheel(약 156 MB)에도 적용해 볼 수 있는지는 확인하지 않았습니다.
- 소유자가 지적한 `tarfile` 경로 탈출과 SHA1 필수 검증은 아래 "소유자가 지적한 보안 항목을 cefweaver에 대조한 결과"에서 확인했고, **해시 검증 우회와 추출 경로 탈출 방어 부재**가 나왔습니다.

## 소유자가 지적한 보안 항목을 cefweaver에 대조한 결과 (2026-10-13)

소유자가 `tools/download_cef.py`에서 지적한 것은 (1) SHA1 검증을 필수로 하고 빈 값을 허용하지 않을 것, (2) `tarfile` 추출의 경로 탈출 방어(`data_filter`)입니다. cefweaver는 CEF를 `cmake/DownloadCEF.cmake`가 받습니다(`CEF_ROOT`가 없을 때). 실제로 돌려 확인했습니다(CMake 4.2.3).

| 항목 | 결과 |
| --- | --- |
| 해시를 반드시 확인하는가 | `file(DOWNLOAD ... EXPECTED_HASH SHA1=...)`이 받을 때 확인합니다. 해시가 빈 값이거나 틀리면 오류로 멈춥니다(빈 값이 검증을 건너뛰게 하지 않음). |
| **해시 검증 우회** | **있었고 고쳤습니다.** 해시가 틀려서 멈춘 뒤에도 내려받은 파일이 디스크에 남고, 다음 실행은 `if(NOT EXISTS 아카이브)`가 거짓이라 내려받기와 검증을 건너뛰고 그 파일을 그대로 풉니다. 같은 논리를 복제해 두 번 실행해서 두 번째 실행이 해시가 틀린 아카이브를 풀어내는 것을 확인했습니다. |
| **추출의 경로 탈출 방어** | **없었고 고쳤습니다.** `cmake -E tar xzf`는 `../`가 든 이름, 절대 경로, 추출 위치 밖을 가리키는 심볼릭 링크를 따라 쓰는 파일을 모두 추출 폴더 밖에 썼습니다(세 방식을 만든 시험용 아카이브로 확인). |
| 해시의 출처 | `.sha1`을 아카이브와 같은 서버(`cef-builds.spotifycdn.com`, HTTPS)에서 받습니다. 전송 중 손상과 중간자 공격은 막지만 서버가 뚫려 아카이브와 `.sha1`이 함께 바뀌면 막지 못합니다. CEF가 서명이나 별도 해시 목록을 제공하는지는 확인하지 못했습니다. |
| 위의 두 약점이 닿는 범위 | `CEF_ROOT`를 주지 않고 빌드할 때(`prepare.py` 또는 `uv build`가 CEF를 받는 경우)만입니다. `--cef-root`나 `CEF_ROOT`로 준비한 배포본, 설치된 wheel을 쓰는 사용자에게는 닿지 않습니다. |
| `automate-git.py` 내려받기(`--build-cef`) | CEF 소스의 커밋(버전 이름에서 나온 해시)으로 고정한 `raw.githubusercontent.com` 주소(HTTPS)에서 받아 실행합니다. 해시 검증은 없고 커밋 고정에 의존합니다. 사용자가 직접 `--build-cef`를 줄 때만 실행됩니다. |
| 버전 이름 검증 | 인덱스에 있는 이름인지 확인하지만 인덱스를 받지 못하면 경고만 하고 건너뜁니다. `-DCEF_VERSION`의 값은 파일 경로에 그대로 쓰이므로 `..`가 든 값이 폴더 밖을 가리킬 수 있습니다(빌드하는 사람이 주는 값이라 위험은 낮음). |
| 원격 디버깅 포트 | 기본은 꺼짐. 켜면 `127.0.0.1`에만 열렸습니다(`ss -ltn`으로 확인). 같은 컴퓨터의 다른 프로세스나 사용자는 접속할 수 있습니다. |
| 환경 변수가 코드를 고르는가 | `CEFQT_BINDING`은 `pyqt6`와 `pyside6`만 받고 그 밖의 값은 무시합니다. 외부 값이 모듈 이름으로 쓰이는 곳은 없었습니다. |
| 셸 실행 | `tools/`, `cefweaver/`, 시험, 예제 어디에도 `shell=True`나 `os.system`이 없었습니다(생성기의 vendor 폴더 제외). |

### 고친 내용과 확인 (2026-10-13)

- `cmake/DownloadCEF.cmake`: 아카이브를 `.part`로 받아 SHA1을 직접 계산해 맞을 때만 제 이름으로 옮기고, 틀리면 지웁니다. 이미 있는 아카이브도 `.sha1`과 다시 대조하고, `.sha1`이 40자리 16진수가 아니면 오류입니다. 임시 폴더에 풀어 배포본 폴더를 통째로 옮기며, 버전과 플랫폼 이름은 글자, 숫자, `.+_-`만 받습니다.
- `tools/safe_extract.py`: 모든 멤버를 먼저 검사해(앞선 링크를 따라간 뒤의 경로까지) 하나라도 위험하면 아무것도 풀지 않고, 통과하면 모드를 `& 0o755`로 줄여 풉니다(Python 3.12 이상은 `data` 필터도).
- `tests/test_download_cef.py` 24개가 위 공격들과 우회를 막는지 확인하고, 이전 구현에서는 8개가 실패합니다.
- **실제 CEF로 확인**: 실제 CDN에서 154.0.34 배포본(660 MB)을 새 코드로 받아 풀고(2분 28초), 기존에 `cmake -E tar`로 푼 배포본과 비교해 비디렉터리 1,319개의 모드, 종류, 이름, 링크 대상, 크기가 모두 같았습니다(디렉터리 모드는 umask를 따라 다를 수 있음). 이미 받은 아카이브를 다시 검증하고 푸는 경로도 실제 아카이브로 확인했습니다. 실제 배포본에는 심볼릭 링크가 없었습니다.

## 한계

- PR의 코드 자체를 받아 읽지는 않았고, 댓글과 리뷰 본문, 이슈 본문으로 파악했습니다. 작성자의 설명은 작성자의 주장이며 일부는 직접 검증하지 않았습니다.
- cefweaver의 확인은 Linux 한 환경입니다.

## 관련 페이지

- [cefpython과 cefweaver의 API 차이](cefpython-comparison.md)
- [프로덕션 배포 가능성](../reference/production-readiness.md)
- [알려진 제약과 미검증 항목](../reference/known-constraints.md)
