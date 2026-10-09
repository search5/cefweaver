---
title: 실행해서 확인한 미디어 (F71부터)
type: reference
sources:
  - tests/test_smoke.py
  - tests/playback_check.py
  - native/cefwrapper/cef_wrapper_client_handler.h
  - tools/gen/typesys.py
  - cefweaver/bridge.py
  - cefweaver/ui/audio.py
  - cefweaver/ui/toolkits/sdl2.py
  - cefweaver/ui/toolkits/qt.py
  - tests/test_ui.py
updated: 2026-10-09
---

# 실행해서 확인한 미디어 (F71부터)

마이크와 카메라의 권한 핸들러, 오디오 핸들러, 실제 유튜브 영상의 재생에서 실행해서 확인한 사실입니다. 앞의 항목은 [실행해서 확인한 핸들러](verified-findings-handlers.md)에 있습니다.

## F71. 권한 핸들러 (마이크, 카메라)

방법: 가짜 장치 스위치(`use-fake-device-for-media-stream`)로 장치 없는 환경에서, `http://localhost/`(보안 컨텍스트)의 페이지가 `navigator.mediaDevices.getUserMedia({audio: true})`를 부르게 하고 `PermissionHandler`의 결정에 따른 결과를 제목으로 읽었습니다(`WithCef`의 시험 4개).

- **확인함**: `on_request_media_access_permission`이 출처 `'http://localhost/'`, 권한 `1`(`MediaAccessPermissionTypes.DEVICE_AUDIO_CAPTURE`), 메인 프레임 여부 `True`와 함께 불립니다. `callback.continue_(requested_permissions)`로 허용하면 `granted:1`(오디오 트랙 1개), `callback.cancel()`로 거부하면 `denied:NotAllowedError`입니다.
- **확인함**: 핸들러가 `False`를 돌려주면(기본 처리) 이 환경의 스타일에서 페이지는 **거부**되고 `denied:NotAllowedError`를 받습니다. 헤더 주석("Alloy 스타일의 기본 처리는 거부")과 같습니다.
- **확인함**: `enable-media-stream` 스위치(cefpython이 안내하는 방법)를 주면 핸들러가 거부하도록 해 놓아도 `granted:1`이고 **핸들러는 불리지 않습니다**(`asked`가 빔). 헤더 주석("이 스위치를 쓰면 이 메서드는 불리지 않음")과 같습니다.
- **발견한 결함(수정함)**: 범위에 `PermissionHandler`를 넣고 생성만 해서는 핸들러가 한 번도 불리지 않았습니다. 래퍼의 손으로 쓴 `CefWrapperClientHandler`는 핸들러마다 `Get...Handler()`를 직접 나열하므로 `CwPermissionHandlerForward`를 상속하고 `GetPermissionHandler()`를 더해야 했습니다(이런 핸들러를 더할 때마다 필요한 단계).
- 확인하지 못한 것: 화면 캡처(`DESKTOP_*`), 비디오(`DEVICE_VIDEO_CAPTURE`), `on_show_permission_prompt`(카메라 PTZ, 클립보드 등의 권한 프롬프트), Chrome 스타일의 기본 처리(권한 UI), 실제 마이크.

## F72. 오디오 핸들러

방법: 440Hz 사인파를 WebAudio로 재생하는 페이지(`autoplay-policy=no-user-gesture-required`)를 열고 `AudioHandler`가 받는 것을 읽었습니다(`WithCef`의 시험 4개).

- **확인함**: 스트림은 스테레오(`ChannelLayout.LAYOUT_STEREO`), 44100Hz, `frames_per_buffer` 1024, 채널 2개로 시작하고 6초 동안 패킷 253개가 왔습니다. `on_audio_stream_packet(browser, data, pts)`의 `data`는 채널마다 하나, 길이 1024인 읽기 전용 `float32` `memoryview`의 `list`이고 샘플의 최댓값은 1.0(첫 패킷은 0.0)입니다. `pts`는 정수이고 커지며, 호출이 끝난 뒤 뷰를 쓰면 `ValueError`입니다(소유는 CEF). 페이지를 떠나면(`about:blank`) `on_audio_stream_stopped`가 불립니다.
- **확인함**: `get_audio_parameters`가 `(True, AudioParameters(LAYOUT_STEREO, 48000, 480))`를 돌려주면 시작 매개변수가 그대로이고 패킷이 480프레임씩 옵니다. `(False, ...)`를 돌려주면 캡처가 일어나지 않아 시작도 패킷도 없습니다.
- **확인함(스위치)**: `mute-audio`를 주면 오디오 스트림이 만들어지지 않아 **핸들러가 불리지 않습니다**(`get_audio_handler`도 불리지 않음). 시험에서 소리를 내지 않으려면 `disable-audio-output`(가짜 출력 장치)을 씁니다: 스트림과 패킷은 그대로 오고 소리는 나지 않습니다.
- **사고와 교훈**: 처음에는 래퍼의 `CefWrapperClientHandler`에 `GetAudioHandler()`를 더하지 않아 핸들러가 CEF에 전달되지 않았고, 시험 페이지의 440Hz 음이 **실제 스피커로 재생**되었습니다(선생님이 "삐 소리가 들려"라고 알려 주셨습니다). 핸들러를 더할 때마다 이 getter가 필요합니다(권한 핸들러 때와 같은 단계, [F71](verified-findings-handlers.md)). 소리를 내는 시험은 처음부터 `disable-audio-output`과 함께 돌려야 합니다.
- 확인하지 못한 것: 핸들러가 있을 때 기본 출력 장치로도 소리가 나가는지(`disable-audio-output` 없이 켜 보면 소리가 날 수 있어 시험하지 않음), 모노와 5.1 같은 다른 채널 배치, `on_audio_stream_error`가 불리는 경우, 한 브라우저에서 스트림이 여러 번 시작되는 경우(헤더는 가능하다고 함). 채널 수는 프록시가 `on_audio_stream_started`의 `channels`를 기억하므로 스트림이 새로 시작되면 갱신되지만, 여러 스트림이 겹치는 경우는 확인하지 않았습니다.

## F73. 유튜브 영상의 재생

페이지: `https://www.youtube.com/watch?v=Ds-jo86CZRg&list=RDl1n6eqfNl4Q&index=3`. 가상 화면(Xvfb)에서 소리는 가짜 출력으로 보내고(`disable-audio-output`), 3초마다 `<video>`의 상태를 읽었습니다([절차](../procedures/check-playback.md), 도구 `tests/playback_check.py`).

- **확인함(기본 CEF 앱, 자기 창)**: 12.0초 동안 영상이 12.0초 흐르고 멈춤이 없으며(`paused=false`, `readyState=4`) 854x480, 오류도 광고도 없었습니다. 오디오 핸들러(F72)를 달고 40초를 돌렸을 때 스테레오 44100Hz 패킷 1770개가 왔고 샘플의 최댓값은 0.51(실제 소리)이었습니다.
- **확인함(오프스크린)**: 같은 영상이 GTK 3, Qt(PyQt6와 PySide6), Tk, SDL2, wx, Kivy의 `quickstart.py`를 **고치지 않고** 돌려서 모두 재생되었습니다: 시간이 시계와 같은 속도로 흐르고(예: GTK 15.0초 동안 14.8초), 멈춤과 오류가 없고, 뷰의 그림이 계속 바뀌고(CRC로 센 서로 다른 그림이 늘어남), 창을 닫으면 종료 코드 0, `stack smashing` 없음. GTK에서는 해상도가 854x480에서 1280x720으로 올라갔습니다(적응형).
- **확인함(코덱)**: `MediaSource.isTypeSupported`로 VP9(WebM), AV1, Opus는 **지원**, H.264(`avc1`)와 AAC(`mp4a`)는 **미지원**입니다. 표준 CEF 빌드는 독점 코덱을 넣지 않기 때문이며, 유튜브가 VP9와 Opus로 내려주어서 재생됩니다. H.264만 내려주는 사이트는 재생되지 않습니다(이 환경에서 확인하지는 않음).
- **발견한 결함(수정함)**: 점검을 만들다가 `JavascriptBridge`에 노출한 함수가 **하나도 없으면** 렌더러의 shim이 설치되지 않아(`window.__cefweaverBridge`가 `undefined`) `evaluate`와 `execute_function`이 동작하지 않는 것을 찾았습니다. 시험은 항상 함수를 노출해서 드러나지 않았습니다. 브리지를 만들 때 이름 목록을 `"[]"`로라도 설정하도록 고쳤습니다(시험 `test_a_bridge_that_exposes_nothing_still_evaluates_and_calls_the_page`).
- **발견한 한계(미수정)**: `bridge.evaluate`는 유튜브와 GitHub에서 Trusted Types/CSP 때문에 `EvalError`입니다([알려진 제약](known-constraints.md)).
- **확인하지 못한 것**: 실제로 소리가 나는지(아무도 듣지 않는 가짜 출력으로만 했음), 실제 화면(Wayland)과 GPU 가속, 광고가 붙는 영상, 동의 창이 뜨는 지역, 로그인, DRM이 걸린 영상(Widevine이 없음), 장시간 재생, 다른 해상도로의 크기 변경 중 재생. 영상이 한 번만 확인된 것이고 네트워크 상태에 따라 달라질 수 있습니다.

## F74: 페이지의 소리를 싱크로 재생하기 (2026-10-09)

`BrowserView(adapter, audio="auto")`는 툴킷의 `audio_sink()`가 있으면 그것을(SDL2: `SDL_QueueAudio`, Qt: `QAudioSink`), 없으면 pygame의 `PygameSink`를 씁니다. 가짜 출력(`disable-audio-output`)과 음량 0으로 YouTube를 15초 재생해서 확인했습니다.

| 환경 | 싱크 | 15초 동안 | 끊김 |
| --- | --- | --- | --- |
| sdl2 | `SdlSink` | 약 69만 frame 기록, 거의 전부 소비 | 0 |
| qt (PyQt6, PySide6) | `QtSink` | 약 69~70만 frame 기록, 전부 소비 | 0 |
| gtk3, tk, wx, kivy | `PygameSink` | 약 67~71만 frame 기록, 거의 전부 소비 | 0 |

- **교착 (원인 확인)**: pygame의 `AudioDevice.close()`는 GIL을 쥔 채 SDL 오디오 스레드를 기다리고, 그 스레드는 Python 콜백을 실행하려고 GIL을 기다립니다. 콜백이 계속 도는 동안 닫으면 8번 중 7번 멈췄습니다(`faulthandler`로 `stop`에서 멈춘 것을 확인). `ctypes`로 `SDL_CloseAudioDevice`를 부르면(GIL을 놓음) 40번 열고 닫아도 멈추지 않아서 `_close_device`가 그렇게 합니다.
- **끊김 방지**: 기록 간격의 흔들림이 들리지 않도록 처음과 비었다가 다시 찰 때 약 0.1초(pygame은 0.04초)를 모은 뒤 재생합니다. 40 ms로는 SDL 싱크가 smoke에서 10번 끊겼고 100 ms에서 0이었습니다.
- **지연 상한**: 응용이 따라가지 못하면 0.5초를 넘는 오래된 소리를 버립니다(`dropped`).
- **PySide6**: `QAudioSink.stateChanged`에 슬롯을 연결하면 `QAudio::State` 변환 오류가 납니다. 신호 대신 `state()`를 주기적으로 읽습니다.
- **스피커로 들은 것 (2026-10-09, 선생님이 확인)**: 440 Hz 시험음은 `PygameSink`와 `SdlSink` 모두 들렸고, 실제 YouTube 소리는 sdl2, qt(PyQt6, PySide6), gtk3, wx, kivy, tk 일곱 환경 모두 들렸습니다(`--loud --no-gpu`, 시스템 출력 음량 34%). 수치도 맞았습니다: 싱크에 들어간 샘플의 peak 약 0.5, 시스템 출력 monitor(`parec`)의 peak 16716/32768.
- **확인하지 못한 것**: 소리와 화면의 어긋남 정도.

## F75: 실제 화면에서의 GPU 오류와 점검 도구의 함정 (2026-10-09)

- **실제 화면(XWayland)에서만** GPU 프로세스가 `gbm_bo_import ... nullptr`, `CreateSharedImage: could not create backing`으로 반복해서 죽고 영상 디코드가 실패합니다(`<video>.error.code` 3). xvfb에서는 나지 않습니다.
- **래퍼와 무관함 (검증)**: 기본 CEF 앱(창 모드)과 래퍼 없는 `cefsimple`(Chrome 스타일과 `--use-alloy-style` 모두, `--no-sandbox --ozone-platform=x11`)에서도 같은 오류가 3번씩 나옵니다.
- **환경**: 하이브리드 GPU 노트북(AMD HawkPoint `renderD128`, NVIDIA RTX 4060 `renderD129`), XWayland. xvfb에는 GPU가 없어서 이 오류가 나지 않습니다.
- **우회 시험** (YouTube, 실제 화면, 같은 조건으로 반복). 합격은 영상이 시계대로 재생되는 것입니다.

| 모드 | 스위치 | 결과 |
| --- | --- | --- |
| 창 모드 | 없음 | 0/3 |
| 창 모드 | `disable-accelerated-video-decode` | **3/3** (`gbm` 오류 없음) |
| 창 모드 | `disable-gpu-memory-buffer-video-frames` | 0/3 |
| 창 모드 | `disable-features=VaapiVideoDecoder,AcceleratedVideoDecodeLinux` | 0/1 |
| 오프스크린(gtk3, sdl2) | 없음 | 0/6 |
| 오프스크린 | `disable-accelerated-video-decode` | 0/6 (gtk3, sdl2) |
| 오프스크린 | `disable-gpu-compositing`, `use-gl=angle`+`use-angle=swiftshader`, `disable-gpu-memory-buffer-compositor-resources`+`disable-gpu-memory-buffer-video-frames`, `in-process-gpu`, `disable-gpu-sandbox`, `render-node-override=renderD128`/`renderD129`, `use-gl=egl`, `use-angle=gl`, `use-gl=angle`+`use-angle=gl` | 각 0/2 또는 0/3 |
| 오프스크린 | `disable-accelerated-video-decode`+`disable-gpu-memory-buffer-video-frames`(+`disable-gpu-memory-buffer-compositor-resources`, 또는 `disable-features=AcceleratedVideoDecodeLinux,...`) | 각 0/3 |
| 오프스크린 | **`disable-gpu`** | **통과** (일곱 환경) |

- **사운드 모듈과 무관함 (검증)**: 싱크와 pygame을 전혀 쓰지 않는 GTK 3(`--audio` 없음)도 2번 모두 같은 오류로 실패했습니다. 기본 CEF 앱과 `cefsimple`에는 애초에 사운드 모듈이 없습니다.
- **GPU를 켜면 WebGL은 됩니다 (검증)**: 오프스크린 GTK 3에서 GPU를 켜면 WebGL이 NVIDIA GeForce RTX 4060(ANGLE, OpenGL 4.5)으로 동작하고(3초에 93~94 frame, 픽셀 값 맞음, 컨텍스트 손실과 GPU 프로세스 종료 없음), `disable-gpu`를 켜면 `getContext('webgl')`이 null이라 **WebGL이 없습니다**(소프트웨어 대체 없음). 즉 영상 재생만 GPU 켠 상태에서 실패하고, `disable-gpu`는 WebGL을 잃는 대가가 있습니다.
- **Chrome과 Wayland 대조 (검증, 2026-10-09)**: 같은 기계, 같은 영상, GPU 켠 상태, 소리 없음, DevTools로 `<video>`를 읽었습니다(스크래치 프로브).

| 프로그램 | X11 | 네이티브 Wayland |
| --- | --- | --- |
| Chrome 155 (설치본, 임시 프로필) | 재생 정상 2/2, `gbm_bo_import` 0 | 재생 정상 |
| `cefsimple` Chrome 스타일 (CEF 154) | **실패**, `gbm_bo_import` 3, GPU 종료 3 | 재생 정상 |
| `cefsimple` Alloy 스타일 (CEF 154) | **실패**, `gbm_bo_import` 3, GPU 종료 3 | 재생 정상 |
| cefweaver (Alloy, 오프스크린) | **실패** (위 표) | 약 1초 뒤 `SIGTRAP` ([F31](verified-findings-api.md)) |

  따라서 문제는 XWayland 자체도 CEF 자체도 아니고 **CEF의 X11 경로**입니다(같은 X11에서 Chrome은 됩니다). 그리고 래퍼 없는 `cefsimple`은 Alloy 스타일도 Wayland에서 영상까지 재생하므로, cefweaver가 Wayland에서 죽는 것은 **래퍼 쪽 원인**일 가능성이 큽니다(F31의 "그림이 나오는지는 확인하지 못했다"를 메움). Wayland를 쓸 수 있다면 GPU를 켠 채 영상이 됩니다.
  Chrome이 X11에서 되고 CEF가 안 되는 이유는 모릅니다.
- **추정(미확인)**: 창 모드는 영상 디코드를 끄면 되지만 오프스크린은 안 되는 것으로 보아, 오프스크린에서 합성된 영상 프레임을 읽어 오는 경로에 별도의 버퍼 import가 있고 그것이 실패하는 것으로 보입니다. 그 경로를 끄는 스위치는 찾지 못했습니다. 상세 로그(`--log-file`)에는 `gbm_bo_import` 줄이 없어 포맷과 modifier는 알 수 없었습니다.
- **Tk 창을 닫아도 끝나지 않던 것은 점검 도구의 문제였습니다.** Tk는 창에 프로세스 번호를 달지 않아 대체 검색이 "화면의 유일한 창"을 골랐는데, 실제 화면에서는 `mutter guard window`가 걸려 닫기 신호가 Tk에 닿지 않았습니다. `--class Tk`로 한정한 뒤 닫는 신호에서 종료까지 0.18초(xvfb 0.12초), 종료 코드 0입니다.
- **Kivy**는 `--no-gpu`에서 처음 한 번 실패했고(영상 요소가 없음) 같은 조건 12번에서 다시 나지 않았습니다. 원인 미조사입니다.

## 관련 페이지

- [실행해서 확인한 핸들러 (F55부터)](verified-findings-handlers.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [실제 영상이 재생되는지 확인하기](../procedures/check-playback.md)
- [java-cef 동등성](java-cef-parity.md)
