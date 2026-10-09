---
title: Wayland와 GPU
---

# Wayland와 GPU

Chromium은 Linux에서 X11과 Wayland 중 하나로 동작합니다(`ozone-platform` 스위치). cefweaver는 쓰임에 따라 기본값을 다르게 고릅니다.

| 쓰임 | 기본값 | 이유 |
| --- | --- | --- |
| `cefweaver.ui` (오프스크린, `ui.Session`) | Wayland 컴포지터가 있으면 `wayland`, 없으면 Chromium이 고름 | 오프스크린은 Wayland에서 정상이고, 일부 기계에서는 X11에서 GPU가 죽어 영상이 안 나옵니다 |
| `cefweaver.CefApp` (창 모드) | `DISPLAY`가 있으면 `x11`(Wayland 데스크톱에서는 XWayland) | 창 모드는 Wayland에서 코드로 닫을 수 없습니다 |

"Wayland 컴포지터가 있다"는 것은 `WAYLAND_DISPLAY`가 가리키는 소켓이 실제로 있다는 뜻입니다. 앱이 `ozone-platform`이나 `ozone-platform-hint`를 직접 주면 그대로 따릅니다.

```python
session = ui.Session(loop, switches=[("ozone-platform", "x11")])    # X11로 되돌리기
```

## 오프스크린과 Wayland

GPU를 켠 채로 Wayland에서 영상(YouTube)과 소리, WebGL이 정상 동작하는 것을 확인했습니다. GTK 3, Qt, Tk, SDL2, wxPython, Kivy의 오프스크린 브라우저에서 모두 같았습니다. 오프스크린에는 네이티브 창이 없어서 아래의 창 모드 문제도 없습니다.

## X11에서 GPU를 켰을 때의 문제

일부 기계에서는 X11(XWayland)에서 GPU 프로세스가 반복해서 죽고 영상 재생이 실패합니다(`<video>`의 `error.code`가 3, 로그에 `gbm_bo_import`, `could not create backing`). 확인한 환경은 AMD 내장 GPU와 NVIDIA 외장 GPU가 같이 있는 노트북(GNOME)입니다. 같은 기계에서 설치된 Chrome은 X11에서도 정상이고 CEF의 예제 앱(`cefsimple`)은 같은 오류가 나므로 cefweaver의 문제가 아니라 CEF의 X11 경로의 문제입니다. 원인은 찾지 못했습니다.

X11을 꼭 써야 한다면 다음이 우회책입니다.

| 스위치 | 효과 |
| --- | --- |
| `disable-gpu` | 영상이 재생됩니다. 대신 **WebGL이 사라집니다**(소프트웨어 대체가 없습니다) |
| `disable-accelerated-video-decode` | 창 모드에서는 3번 모두 통과, 오프스크린에서는 3번 중 2번 통과했습니다. 완전한 해결은 아닙니다 |

> 시험해 본 기계는 한 대뿐입니다. GPU가 하나뿐인 기계나 다른 컴포지터(KDE, Sway 등)에서는 확인하지 못했습니다. 문제가 나면 `ozone-platform` 스위치로 `x11`과 `wayland`를 바꿔 보세요.

## 창 모드와 Wayland

`CefApp`으로 만든 창은 Wayland에서 뜨고 페이지도 정상으로 돕니다. 문제는 **코드로 닫을 때**입니다. `close_browser()`가 끝나지 않고, 그 상태에서 `shutdown()`을 부르면 `CefShutdown()` 안에서 프로세스가 비정상 종료합니다. 래퍼 없는 CEF 예제(`cefsimple --use-native`)에 닫기 호출을 더해도 X11은 정상 종료하고 Wayland는 끝나지 않으므로 CEF의 한계입니다. 창의 닫기 버튼으로 닫는 경로는 시험하지 못했습니다. 그래서 창 모드는 X11을 기본으로 씁니다.
