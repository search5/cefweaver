---
title: 공유 텍스처 (GPU 가속 페인트)
type: reference
sources:
  - cefweaver/texture.py
  - native/cefwrapper/cef_wrapper_browser_process_handler.cc
  - tools/gen/model.py
  - tests/test_smoke.py
  - tests/egl_dmabuf.py
updated: 2026-10-08
---

# 공유 텍스처 (GPU 가속 페인트)

오프스크린 브라우저가 픽셀 대신 GPU 메모리를 넘겨 주는 방식입니다. CPU로 복사하지 않으므로 GPU로 그리는 위젯(OpenGL, Vulkan)에 알맞습니다. 기능은 열려 있지만 **픽셀 내용은 이 개발 환경에서 확인하지 못했습니다**([F66](verified-findings-handlers.md)).

## 쓰는 방법

```python
app.offscreen = True
app.shared_texture = True                  # initialize() 전에. create_browser(shared_texture=...)도 됩니다
class Render(cefweaver.RenderHandler):
    def get_view_rect(self, browser): return cefweaver.Rect(0, 0, 800, 600)
    def on_accelerated_paint(self, browser, type, dirty_rects, info):
        plane = info.planes[0]             # Linux: dmabuf 파일 디스크립터
        data = cefweaver.read_plane(plane) # 선형(info.modifier == 0)이면 CPU로 복사
```

| 항목 | 설명 |
| --- | --- |
| `CefApp.shared_texture`, `create_browser(shared_texture=)` | 켜면 `on_paint`가 아니라 `on_accelerated_paint`가 불립니다 |
| `types.AcceleratedPaintInfo` | `planes`(튜플), `modifier`, `format`(`ColorType`), `extra` |
| `types.AcceleratedPaintNativePixmapPlane` | `stride`, `offset`, `size`, `fd` |
| `types.AcceleratedPaintInfoCommon` (`info.extra`) | `timestamp`, `coded_size`, `visible_rect`, `content_rect`, `source_size`, `capture_update_rect`, `region_capture_rect`, `capture_counter`와 `has_*` 표시 |
| `cefweaver.read_plane(plane, length=None)` | 평면을 `bytes`로 복사합니다(`mmap`과 `DMA_BUF_IOCTL_SYNC`). 선형 텍스처만 되고, 안 되면 `OSError` |

## 규칙

- **파일 디스크립터는 콜백이 돌아올 때까지만 유효**하고 텍스처는 풀에서 다시 쓰입니다. 오래 쓰려면 콜백 안에서 `os.dup(plane.fd)`로 복제하고 GL에서 가져옵니다(`EGL_EXT_image_dma_buf_import`).
- 가져오기는 `EGL_LINUX_DMA_BUF_EXT`와 `EGL_LINUX_DRM_FOURCC_EXT`(`BGRA_8888`이면 `ARGB8888`), `fd`, `offset`, `stride`, `modifier`로 합니다. 일부 드라이버는 그 텍스처를 렌더 대상으로 쓰지 못하므로 외부 텍스처(`GL_TEXTURE_EXTERNAL_OES`)로 샘플링해서 그려야 합니다(F66, `tests/egl_dmabuf.py`).
- **GPU가 없으면 `on_paint`로 되돌아갑니다.** 켜 놓아도 GPU가 없는 환경(Xvfb)에서는 CEF가 `on_paint`로 그림을 줍니다. 응용은 두 콜백을 모두 다뤄야 합니다.
- 텍스처를 내려면 DRI3가 있는 디스플레이 서버와 dmabuf를 내보내는 GPU 드라이버가 필요합니다. 독점 NVIDIA 드라이버에서는 ANGLE이 Vulkan을 써야 했습니다(`--use-gl=angle --use-angle=vulkan --enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan`). 이 스위치는 환경에 따라 다르므로 래퍼가 자동으로 넣지 않고 `add_command_line_switch`로 줍니다.

## 생성기의 확장

`CefAcceleratedPaintInfo`는 구조체 안에 구조체 배열(`planes[4]`)과 개수(`plane_count`)가 있어 지금까지의 구조체 종류로는 읽지 못했습니다. 생성기가 (1) 개수가 딸린 구조체 배열을 튜플 필드로, (2) C++ 클래스가 없는 C 구조체(`RAW_STRUCTS`)를, (3) 플랫폼마다 다른 구조체는 Linux 정의를 읽습니다. 이 구조체는 CEF가 Python에 주기만 하므로 Python에서 C++로 바꾸는 코드는 만들지 않습니다.

## 관련 페이지

- [오프스크린 렌더링](offscreen-rendering.md)
- [실행해서 확인한 핸들러](verified-findings-handlers.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
