---
title: Chromium의 Wayland와 X11 동작
type: analysis
sources:
  - tests/test_smoke.py
  - CLAUDE.md
  - native/cefwrapper/cef_wrapper_client_handler_linux.cc
updated: 2026-10-08
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
- 창 제목은 Linux에서 `PlatformTitleChange`가 비어 있어서(`cef_wrapper_client_handler_linux.cc`) 페이지의 `<title>`이 창에 반영되지 않았을 가능성이 높습니다.
- GUI 툴킷 임베딩이 Wayland에서 되는지.

## 임베딩에 관한 근거

CEF의 `parent_window`는 X11 `Window` 핸들입니다(`cef_origin` 위키 `db/ko/structs_03.json`). 이 핸들을 받아 자식 창으로 만드는 코드(`libcef/browser/native/browser_platform_delegate_native_linux.cc`)는 `SUPPORTS_OZONE_X11` 빌드에서만 컴파일됩니다. README가 내세우는 wxPython, PyQt 같은 툴킷 안에 넣는 방식은 X11 창 핸들에 의존하므로, Wayland 세션에서는 XWayland(`ozone-platform=x11`)를 쓰거나 오프스크린 렌더링을 쓰는 것이 후보입니다. 이 부분은 문서와 소스를 읽은 추론이며 실행해서 확인하지 않았습니다.

## 정해야 할 것

| 쟁점 | 선택지 |
| --- | --- |
| 기본 동작 | (가) Chromium에 맡김(현재) (나) 항상 X11(XWayland)로 강제 (다) 부모 창을 줄 때만 X11 |
| 툴킷 임베딩 | XWayland 또는 오프스크린 렌더링 |
| 시험 | 지금의 Xvfb 유지, 나중에 헤드리스 Wayland 컴파지터 도입 |

제안은 (가)를 유지하고 임베딩 용도는 X11 강제를 문서화하는 것이었습니다. 이미 `add_command_line_switch("ozone-platform", "x11")`로 할 수 있어 코드 변경이 필요 없습니다. (나)는 Wayland 사용자를 XWayland로 밀어내는 부작용이 있습니다. 창 단독 사용과 툴킷 임베딩 둘 다 목표이므로 결정은 Chromium이 확인된 뒤로 미뤘습니다([알려진 제약과 미검증 항목](../reference/known-constraints.md)).

## 관련 페이지

- [플랫폼 지원 현황](../concepts/platform-support.md)
- [시험](../components/tests.md)
- [실험으로 확인한 사실](../reference/verified-findings.md)
