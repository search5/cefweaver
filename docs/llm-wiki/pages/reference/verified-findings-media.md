---
title: 실행해서 확인한 미디어 (F71부터)
type: reference
sources:
  - tests/test_smoke.py
  - tests/playback_check.py
  - native/cefwrapper/cef_wrapper_client_handler.h
  - tools/gen/typesys.py
  - cefweaver/bridge.py
updated: 2026-10-08
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

## 관련 페이지

- [실행해서 확인한 핸들러 (F55부터)](verified-findings-handlers.md)
- [알려진 제약과 미검증 항목](known-constraints.md)
- [실제 영상이 재생되는지 확인하기](../procedures/check-playback.md)
- [java-cef 동등성](java-cef-parity.md)
