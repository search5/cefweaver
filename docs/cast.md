---
title: Cast 장치 (Chromecast)
---

# Cast 장치 (Chromecast)

`cefweaver.Cast`로 같은 네트워크의 Cast 장치를 찾아 연결하고, 영상 주소를 보내서 재생, 일시정지, 탐색, 음량 조절을 합니다. CEF가 주는 것은 `MediaRouter`와 `MediaSink`, `MediaRoute`뿐이고 재생에 쓰는 Cast 프로토콜의 JSON 메시지는 `cefweaver.cast`가 감쌉니다. 확인한 환경은 Linux x86_64, CEF 154, 실제 장치(Google Nest Hub와 다른 Cast 장치 하나)입니다.

```python
import cefweaver

casts = []                                         # Cast 객체는 참조를 계속 들고 있어야 합니다

def on_sinks(sinks):                               # 장치 목록이 바뀔 때마다 불립니다
    print([sink.get_name() for sink in sinks])

def ready(cast):
    casts.append(cast)
    cast.on_sinks = on_sinks

cefweaver.Cast.open(ready)                         # app.initialize() 뒤에 부릅니다

# 목록에서 장치를 찾은 뒤
session = cast.connect(cast.find("거실"), lambda session, result, error: print(result, error))
session.on_status = lambda status: print(status.player_state, status.current_time)
session.load("http://192.168.0.10:8765/video.mp4")  # 장치가 이 주소를 직접 받아 갑니다
session.pause(); session.play(); session.seek(30.0)
session.set_volume(0.3); session.set_muted(False)
session.stop()                                     # 재생과 세션이 끝납니다(장치는 기본 화면으로)
session.disconnect()                               # 재생 없이 연결만 끝낼 때
```

## 동작 방식

- 모든 호출은 `initialize()`를 부른 스레드(메시지 루프)에서 하고, 콜백도 그 스레드에서 불립니다. 호출은 기다리지 않고 바로 돌아오며, 결과는 `on_status`(플레이어 상태), `on_volume`, `on_state`(`connecting`, `connected`, `closed`)로 옵니다.
- 장치가 목록에 나타나는 데 시간이 걸립니다. 처음에는 빈 목록이 오고 뒤이어 장치가 나타났습니다. `on_sinks`를 기다리거나 `cast.refresh()`를 다시 부릅니다.
- 앱이 열리기 전에 부른 명령(`load` 등)은 줄을 서서 기다렸다가 순서대로 나갑니다.
- 장치의 응답은 요청과 번호로 짝지어지지 않습니다. 기대하는 상태(`PLAYING`, `PAUSED`, `IDLE`의 `FINISHED`)를 기다립니다.
- `stop()`을 부르면 장치의 앱이 끝나서 세션이 `closed`가 됩니다. 다시 재생하려면 `connect()`를 다시 합니다.
- 영상 주소는 장치가 받아 가므로 장치에서 닿는 주소여야 합니다(`localhost`가 아님). 서버가 `Content-Type`을 맞게 주고, Range 요청과 CORS 헤더에 응답하면 확인한 장치에서 재생되었습니다. 접근이 거부되는(`403`) 주소는 재생 막대만 잠깐 보이다가 기본 화면으로 돌아갑니다.

## 확인한 것과 못 한 것

확인한 것: 장치 검색(Cast 싱크), 연결, `load`, `pause`, `play`, `seek`, `set_volume`, `set_muted`, `stop`, `disconnect`. 장치 화면에서 `pause`로 영상이 멈추고 `play`로 다시 움직이고 `stop`으로 사진 화면으로 돌아가는 것을 사람이 봤습니다.

확인하지 못한 것: DIAL 장치, 스피커 그룹(`그룹`이라는 싱크는 보였지만 동작은 보지 않음), 탭 화면 미러링(CEF의 API로는 소스를 얻지 못했습니다), 연결이 끊길 때의 동작, `GET_STATUS`. 장치가 없는 환경에서는 가짜 라우터로 라이브러리의 논리만 시험합니다(`tests/test_cast.py`).
