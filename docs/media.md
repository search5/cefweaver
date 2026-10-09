---
title: 소리, 마이크, 카메라
---

# 소리, 마이크, 카메라

## 페이지의 소리 재생

기본은 CEF(Chromium)가 시스템 오디오로 직접 재생합니다. 앱이 소리를 받아 다루고 싶으면 뷰에 `audio=`를 줍니다.

```python
widget = CefCanvas(root, session, audio="auto")       # 툴킷 위젯의 생성자에 줍니다
```

| `audio=` | 뜻 |
| --- | --- |
| 주지 않음(`None`) | CEF가 재생합니다 |
| `"auto"` | 툴킷의 싱크가 있으면 그것을, 없으면 pygame을 씁니다. 둘 다 없으면 CEF가 재생합니다 |
| 싱크 객체 | 직접 만든 싱크를 씁니다 |

- **툴킷의 싱크**: Qt는 `QtSink`(QtMultimedia), SDL2는 `SdlSink`입니다. GTK 3, Tk, wx, Kivy에는 재생 API가 없어서 pygame(`cefweaver[pygame]`)을 씁니다.
- **싱크의 모양**: `start(sample_rate, channels)`, `write(samples, frames)`, `stop()` 세 메서드입니다. `samples`는 `frames * channels`개의 little-endian float32이고 채널이 끼어 있습니다(interleaved). `write`는 CEF의 오디오 스레드에서 불리므로 막으면 안 됩니다.
- **오류**: 싱크가 예외를 내면 싱크를 떼어 내고 `view.on_audio_error(메시지)`로 한 번 알립니다. 그 뒤로는 CEF가 재생하지 않으므로 소리가 없습니다.
- **음소거**: `view.audio_muted = True`.
- 소리 크기가 필요하면 싱크의 `volume`(0.0에서 1.0)을 조절합니다.

> 소리를 CEF가 아니라 앱이 재생하면 CEF 자체의 재생을 대신하는 것이라, 영상과 소리의 어긋남은 싱크의 지연(수십 ms에서 100 ms 안팎)만큼 생길 수 있습니다. 시험에서는 YouTube 영상이 시계와 같은 속도로 재생되고 끊김이 없었습니다.

## 마이크와 카메라

페이지가 `getUserMedia`로 마이크나 카메라를 요청하면 앱이 허용 여부를 **정책**으로 정합니다. 정책을 주지 않으면 CEF의 기본 처리인 **거부**입니다.

```python
from cefweaver import ui

widget.view.media_permissions = ui.permissions.allow_origins("https://meet.example.org")
session.start(widget)                                 # 정책은 세션을 시작하기 전에 줍니다
```

`allow_origins(...)`는 지정한 출처에만 마이크와 카메라를 주고, 화면 캡처는 주지 않습니다. 더 세밀하게 정하려면 정책을 함수로 씁니다.

```python
def policy(request):
    # request.origin, request.permissions (types.MediaAccessPermissionTypes), request.is_main_frame
    if request.origin.startswith("https://meet.example.org"):
        request.allow()                               # 요청한 것을 모두. request.allow(권한)으로 일부만도 됩니다
    else:
        request.deny()

widget.view.media_permissions = policy
```

- 답은 **지금** 해도 되고 **나중에**(사용자에게 물어본 뒤) 해도 됩니다. 한 번만 유효합니다.
- 정책이 예외를 내면 거부하고 오류를 보고합니다.
- 허용하면 소리와 영상은 **Chromium이 시스템 장치에서 직접** 받습니다. 시험에서 마이크(48 kHz)와 USB 웹캠(640x480, 약 30 fps)이 열려 데이터가 들어오는 것을 확인했습니다.
- 앱이 장치 대신 직접 소리나 영상을 대는 방식(파일, 가상 장치, 다른 믹서)은 아직 없습니다.

> 마이크가 시스템에서 음소거이면 장치는 열리지만 트랙이 `muted`이고 소리가 들어오지 않습니다. 소리가 안 들어오면 시스템의 입력 음소거를 먼저 확인하세요.
