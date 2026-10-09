---
title: Chromium의 Wayland와 X11 동작
type: analysis
sources:
  - tests/test_smoke.py
  - CLAUDE.md
  - native/cefwrapper/cef_wrapper_client_handler_linux.cc
updated: 2026-10-09
---

# Chromium의 Wayland와 X11 동작

"Wayland 환경에서 Chromium 자체가 동작하는가"를 확인한 조사입니다. 프로젝트의 우선순위는 먼저 Chromium 자체가 되고, 그다음 창 단독 사용과 GUI 툴킷 임베딩의 기본 동작을 정하는 것입니다.

## 환경

Linux 6.17, Wayland 세션(`XDG_SESSION_TYPE=wayland`, `WAYLAND_DISPLAY=wayland-0`)과 XWayland(`DISPLAY=:0`), NVIDIA GeForce RTX 4060 Laptop GPU, CEF 154.0.34, Python 3.13. 헤드리스 Wayland 컴파지터(weston, cage, sway)는 없습니다.

## 먼저 알게 된 사실: 환경변수가 플랫폼을 고른다

`ozone-platform`을 지정하지 않으면 Chromium이 환경을 보고 고르며, `WAYLAND_DISPLAY`가 있으면 **실제 Wayland 화면에 창을 직접 엽니다.** 처음에 이 사실을 모르고 시험해서 개발 PC의 실제 화면에 시험 창이 잠깐 열렸습니다(Xvfb로 격리된다고 가정했으나 로그에 Wayland 항목 `wayland_object.cc`가 나와서 알았습니다). 그래서 모든 시험은 `env -u WAYLAND_DISPLAY`, `xvfb-run`, `ozone-platform=x11`을 함께 씁니다([시험](../components/tests.md)).

## 실험

한 페이지가 로드 후에 `window.innerWidth`, `innerHeight`, `devicePixelRatio`, WebGL 렌더러 문자열, 그리고 1.5초 동안의 `requestAnimationFrame` 호출 횟수를 JS 바인딩으로 Python에 보고하게 했습니다. 두 경우를 비교했습니다.

1. 네이티브 Wayland: `ozone-platform=wayland`, `WAYLAND_DISPLAY` 유지(실제 화면에 창이 열림)
2. XWayland: `ozone-platform=x11`, `WAYLAND_DISPLAY` 제거(`DISPLAY=:0`을 통해 실제 화면에 창이 열림)

| | 네이티브 Wayland | XWayland(X11) |
| --- | --- | --- |
| 종료 | 정상 (코드 0) | 정상 (코드 0) |
| JS → Python 보고 | 정상 | 정상 |
| 창 크기 | 1227 x 1445 | 1187 x 1319 |
| `devicePixelRatio` | 1 | 1 |
| WebGL 렌더러 | ANGLE, NVIDIA RTX 4060 (OpenGL ES 3.2) | ANGLE, NVIDIA RTX 4060 (OpenGL 4.5) |
| 1.5초 동안 프레임 | 91 | 93 |
| `stack smashing` | 0건 | 0건 |
| 오류 로그 | GTK 설정 관련 1줄 | mojo 메시지 거부 1줄 |

네이티브 Wayland와 XWayland 모두 Chromium이 동작했고, GPU 가속이 실제로 쓰였으며(WebGL 렌더러가 소프트웨어 렌더러가 아니라 NVIDIA GPU), 프레임이 약 60fps였습니다. `ozone-platform=wayland`를 명시해도 정상이었습니다.

## 확인하지 못한 것

- **눈으로 본 화면**: 확인한 것은 페이지가 스스로 측정해 보고한 값뿐이고 스크린샷 도구가 없었습니다. 창이 실제로 뜨고 배경색과 제목이 보였는지는 사용자가 확인해야 합니다.
- XWayland에서 나온 `Message 0 rejected by interface blink.mojom.WidgetHost` 오류의 원인(종료 중 일회성으로 보이나 조사하지 않았습니다).
- `devicePixelRatio`가 1인 것이 이 화면의 실제 배율과 맞는지. 고해상도 배율에서의 Wayland와 XWayland의 선명도 차이.
- 위 "실험"은 **Chrome 스타일** 창으로 한 것입니다. Alloy 스타일의 결과는 아래 절에 있습니다.
- 창 제목은 이 조사 당시 Linux에서 `PlatformTitleChange`가 비어 있었습니다. Alloy 전환과 함께 X11로 설정하도록 구현했습니다.
- GUI 툴킷 임베딩이 Wayland에서 되는지.

## Alloy 스타일에서의 결과 (2026-10-08, 실제 데스크톱에서 실행)

래퍼가 Alloy 스타일로 바뀐 뒤 같은 환경(GNOME mutter, Wayland 세션 + XWayland)에서 다시 확인했습니다. 사용자가 실제 화면에 창을 여는 것을 허락했습니다.

| `ozone-platform` | 결과 |
| --- | --- |
| `x11`(XWayland) | **정상.** 종료 코드 0, 88프레임, WebGL은 NVIDIA RTX 4060, 창 제목이 X11 창에 설정됨, `get_runtime_style() == 2` |
| `wayland` | **크래시.** 약 1초 뒤 브라우저 프로세스가 `SIGTRAP`(종료 코드 133)으로 끝남 |
| 지정하지 않음 | 위와 같음(`WAYLAND_DISPLAY`가 있으면 Chromium이 Wayland를 고르므로 크래시) |

크래시를 가른 방법과 결과입니다.

- **페이지와 무관합니다.** 아무 스크립트도 없는 페이지도, 애니메이션 프레임이나 WebGL이 있는 페이지도 같았습니다.
- **창 제목 코드와 무관합니다.** 제목 처리를 통째로 없앤 변형도 같았습니다.
- **스타일 때문이 아니라는 단서**: CEF 공식 예제 `cefsimple`은 같은 `libcef`에서 `--use-alloy-style`과 `--use-views`의 모든 조합이 Wayland에서 6초 동안 살아 있었습니다(그림이 나오는지는 확인하지 못했습니다). **영상 재생도 확인했습니다**(2026-10-09, GPU 켠 채 YouTube가 15초 정상 재생, `cefsimple` Chrome 스타일과 Alloy 스타일 모두, [F75](../reference/verified-findings-media.md)). 우리 래퍼에서 죽는 것은 시작이 아니라 **코드로 닫을 때**이고, 래퍼 없는 `cefsimple`도 같은 코드로 닫으면 Wayland에서 끝나지 않아서 CEF의 한계입니다([F31](../reference/verified-findings-api.md)). 외부 메시지 펌프(`CefDoMessageLoopWork`)를 쓰는 점이 `cefsimple`과 다르지만 Chrome 스타일은 같은 펌프로 Wayland에서 동작했습니다.
- 크래시 지점은 메인 스레드의 `libcef.so` 안입니다. 배포된 `libcef`에 심볼이 없고 심볼이 있는 원본(1.4GB)은 `gdb`가 읽다가 죽어서 함수 이름까지는 보지 못했습니다.

**결정**: 사용자가 `ozone-platform`을 지정하지 않았고 X 디스플레이(`DISPLAY`)가 있으면 `x11`을 기본으로 씁니다([설계 결정 기록](../reference/design-decisions.md)). 아래 "정해야 할 것"의 (나)를 조건부로 채택한 것입니다. 창 관리자가 있는 실제 데스크톱에서 이 기본값으로 창이 뜨고 제목이 보이는 것을 확인했습니다([실험으로 확인한 사실 2](../reference/verified-findings-api.md) F31).

## 임베딩에 관한 근거

CEF의 `parent_window`는 X11 `Window` 핸들입니다(`cef_origin` 위키 `db/ko/structs_03.json`). 이 핸들을 받아 자식 창으로 만드는 코드(`libcef/browser/native/browser_platform_delegate_native_linux.cc`)는 `SUPPORTS_OZONE_X11` 빌드에서만 컴파일됩니다. README가 내세우는 wxPython, PyQt 같은 툴킷 안에 넣는 방식은 X11 창 핸들에 의존하므로, Wayland 세션에서는 XWayland(`ozone-platform=x11`)를 쓰거나 오프스크린 렌더링을 쓰는 것이 후보입니다. 이 부분은 문서와 소스를 읽은 추론이며 실행해서 확인하지 않았습니다.

## 정해야 할 것

| 쟁점 | 선택지 |
| --- | --- |
| 기본 동작 | (가) Chromium에 맡김 (나) 항상 X11(XWayland)로 강제 (다) 부모 창을 줄 때만 X11. **Alloy 스타일에서 (가)는 Wayland 세션에서 크래시하므로 (나)를 조건부(`DISPLAY`가 있을 때)로 채택했습니다.** |
| 툴킷 임베딩 | XWayland 또는 오프스크린 렌더링 |
| 시험 | 지금의 Xvfb 유지, 나중에 헤드리스 Wayland 컴파지터 도입 |

제안은 (가)를 유지하고 임베딩 용도는 X11 강제를 문서화하는 것이었습니다. 이미 `add_command_line_switch("ozone-platform", "x11")`로 할 수 있어 코드 변경이 필요 없습니다. (나)는 Wayland 사용자를 XWayland로 밀어내는 부작용이 있습니다. 창 단독 사용과 툴킷 임베딩 둘 다 목표이므로 결정은 Chromium이 확인된 뒤로 미뤘습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [플랫폼 지원 현황](../concepts/platform-support.md)
- [시험](../components/tests.md)
- [실험으로 확인한 사실](../reference/verified-findings.md)
