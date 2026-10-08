---
title: 오프스크린 렌더링
type: reference
sources:
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - native/cefwrapper/cef_wrapper_client_handler.h
  - native/cefwrapper/cef_wrapper_client_handler.cc
  - native/cefwrapper/library.cpp
  - native/cefwrapper/global_vars.h
  - cefweaver/_cefweaver.pyx
  - tools/gen/typesys.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 오프스크린 렌더링

브라우저에 창이 없고 CEF가 그린 픽셀을 `RenderHandler.on_paint()`가 받는 방식입니다. java-cef의 `CefBrowserOsr`와 같은 용도이고, 클라이언트의 `RenderHandler`가 `native/render_handler.cpp`와 같은 역할입니다([java-cef 위키의 RenderHandler와 WindowHandler](/home/jiho/cef_framework/java-cef/docs/llm-wiki/pages/native-handler-render-window.md)).

## 쓰는 방법

```python
class Render(cefweaver.RenderHandler):
    def get_view_rect(self, browser):                 # 필수: 보이는 영역의 크기
        return cefweaver.Rect(0, 0, 800, 600)
    def on_paint(self, browser, type, dirty_rects, buffer, width, height):
        pixels = bytes(buffer)                        # 호출이 끝나면 buffer는 무효: 복사해서 쓴다

class MyClient(cefweaver.Client):
    render = Render()
    def get_render_handler(self): return self.render

app.offscreen = True                                   # initialize() 전에만
app.windowless_frame_rate = 30                         # 1~60, 기본 30
app.set_client(MyClient())
```

| 항목 | 동작 |
| --- | --- |
| `CefApp.offscreen` | 기본 `False`. `initialize()` 뒤에 바꾸면 `RuntimeError`. 켜면 `CefWindowInfo::SetAsWindowless`로 브라우저를 만듭니다(Alloy 스타일). |
| `CefApp.windowless_frame_rate` | 1~60(범위 밖은 `ValueError`), 기본 30. `on_paint()` 호출의 초당 상한입니다. |
| `on_paint(browser, type, dirty_rects, buffer, width, height)` | `type`은 `PaintElementType.VIEW`(본 화면) 또는 `POPUP`, `dirty_rects`는 `Rect`의 목록, `buffer`는 BGRA 32비트 픽셀의 **읽기 전용** `memoryview`(길이 `width * height * 4`)입니다. 호출이 끝나면 뷰가 무효가 되어 `len()` 등이 `ValueError`입니다. |
| `get_view_rect(browser)` | `Rect`를 돌려줍니다. 크기를 바꾸고 `browser.get_host().was_resized()`를 부르면 새 크기로 다시 그립니다. |
| 마우스, 키보드 입력 | `send_mouse_click_event`, `send_mouse_move_event`, `send_mouse_wheel_event`, `send_key_event`(`KeyEvent`: `RAWKEYDOWN`, `CHAR`, `KEYUP`을 차례로 보냄)가 동작합니다. 포커스는 `set_focus(True)`. |
| `get_screen_info(browser)` | `(True, ScreenInfo)`를 돌려주면 CEF가 `device_scale_factor` 등을 씁니다. 배율 2.0이면 페이지의 `devicePixelRatio`가 2이고 프레임이 `2배` 크기(400x200)로 옵니다. `False`면 CEF의 기본(1.0). |
| 터치, IME | `send_touch_event(TouchEvent)`, `ime_set_composition(text, [CompositionUnderline], replacement_range, selection_range)`, `ime_cancel_composition()`은 인자가 변환되어 호출됩니다(동작의 결과는 시험하지 않음). |

## 구현

- 읽기용 버퍼 종류: 핸들러의 `const void* buffer`에 크기 인자가 없을 때 헤더가 말하는 크기를 `tools/gen/typesys.py`의 `SIZED_BUFFERS`에 표로 둡니다(`OnPaint`: `width * height * 4`). `Buffer`에 `size_expr`와 `readonly`를 더했고, C++ 프록시가 크기를 계산해 함수 표에 넘기며, Cython이 `PyBUF_READ`의 `memoryview`로 감쌉니다. 이전에는 `void*` 다음에 정수가 오면 그 정수를 크기로 짝지었고, `OnPaint`의 `width`가 크기로 잘못 짝지어질 뻔했습니다.
- `CefWrapperClientHandler`는 `CwRenderHandlerForward`를 상속하고 `GetRenderHandler()`가 사용자의 핸들러를 전달합니다(사용자에게 핸들러가 없으면 `nullptr`).
- `OnBeforePopup`은 오프스크린 브라우저에서 `true`로 팝업을 막습니다. java-cef도 같습니다(`life_span_handler.cpp`: `IsWindowRenderingDisabled()`면 막음). 창 있는 브라우저는 기존대로 CEF의 기본 동작(허용)입니다.
- `CloseAllBrowsers`는 브라우저 목록의 복사본을 순회합니다(아래 F38).

## 제약

- **`start_dragging`(`CefDragData`), `on_accelerated_paint`(포인터가 있는 구조체), `get_accessibility_handler`는 생성되지 않습니다**(보고서에 이유가 있음). java-cef는 `StartDragging`까지 구현합니다.
- 렌더 핸들러가 없는 오프스크린 브라우저는 시험하지 않았습니다(`get_view_rect`가 없으면 빈 크기).
- 팝업(`PaintElementType.POPUP`)의 `on_paint`와 `on_popup_show`, `on_popup_size`는 시험하지 않았습니다(`<select>`의 드롭다운 등).
- 키보드는 영문 한 글자 입력만 시험했습니다(다른 키, 수정자, 한글 IME의 결과는 시험하지 않음). 터치와 IME는 호출이 받아들여지는지만 확인했습니다.
- GPU 가속 페인트(`on_accelerated_paint`)는 쓰지 않습니다. CPU 버퍼만 받습니다.

## 관련 페이지

- [Python API 참조](python-api.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
- [실험으로 확인한 사실](verified-findings.md)
- [C++ 핸들러](../components/native-handlers.md)
