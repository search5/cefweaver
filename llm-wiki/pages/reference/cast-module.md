---
title: cefweaver.cast (Chromecast 검색, 연결, 재생)
type: reference
sources:
  - cefweaver/cast.py
  - cefweaver/__init__.py
  - tests/test_cast.py
updated: 2026-10-11
---

# cefweaver.cast

CEF의 미디어 라우터(`MediaRouter`, `MediaSink`, `MediaRoute`, `MediaObserver`) 위에 얹은 순수 Python 계층입니다. 생성된 바인딩이나 C++은 건드리지 않습니다(`JavascriptBridge`와 같은 방식). 사용자가 Cast 장치의 검색, 연결, 끊기, 재생 단추에 해당하는 API가 있어야 하지 않느냐고 해서 2026-10-11에 만들었습니다. 실제 장치로 확인한 사실은 [F114](verified-findings-opened.md)에 있습니다. 사람이 읽는 설명은 `docs/cast.md`입니다.

## 구성

| 이름 | 역할 |
| --- | --- |
| `Cast(router)` / `Cast.open(callback, request_context=None)` | 라우터에 `MediaObserver`를 등록하고 `sinks`(Cast 싱크만), `on_sinks`, `refresh()`, `find(이름)`, `connect(sink, on_result, application_id)`, `close()`를 제공합니다. `open`은 라우터가 준비되면 `callback(cast)`를 부릅니다. |
| `CastSession` | 한 장치와의 연결. `load`, `play`, `pause`, `seek`, `stop`, `set_volume`, `set_muted`, `disconnect`와 콜백 `on_state`, `on_status`, `on_volume`, `on_message`. |
| `CastStatus` | `MEDIA_STATUS`를 푼 값(`player_state`, `current_time`, `duration`, `idle_reason`, `media_session_id`, `content_id`, `playback_rate`). |

## 프로토콜에서 확인한 것을 코드에 옮긴 부분

- 소스 URN은 `cast:CC1AD845?clientId=<id>`(기본 미디어 수신기)이고 세션마다 `clientId`를 다르게 줍니다.
- 경로가 `CONNECTED`가 되면 `client_connect`(`sequenceNumber` -1)를 먼저 보냅니다. 필요한지는 따로 시험하지 않았고, 확인한 실행에서는 항상 보냈습니다.
- 명령은 모두 `{"type":"v2_message","clientId":...,"sequenceNumber":n,"message":{"type":종류,"requestId":n,"sessionId":<세션>,...}}`입니다. 세션 ID는 `new_session`/`update_session` 메시지에서 얻으므로 그 전의 명령은 줄을 서서 기다립니다. 미디어 명령(`PLAY`, `PAUSE`, `SEEK`, `STOP`)은 `mediaSessionId`(마지막 `MEDIA_STATUS`의 값, 없으면 1)를 더합니다.
- 음량은 `SET_VOLUME`(`volume.level`, `volume.muted`)으로 장치에 주고, 변화는 멀티존 네임스페이스의 `DEVICE_UPDATED`로 읽습니다(세션 시작 때의 값은 `receiver.volume`).
- 응답은 요청과 짝지어지지 않아서(`requestId`를 CEF가 다시 매김) 상태 변화를 알리기만 합니다.
- `stop()`을 보내면 장치의 앱이 끝나고 경로가 사라져 세션이 `closed`가 됩니다(0.2초 뒤).

## 시험

`tests/test_cast.py`의 14개는 가짜 라우터, 싱크, 경로로 실행합니다(CEF가 필요하지 않음): Cast 싱크만 거르기, 연결 전 검사, 클라이언트 ID, 실패한 경로, `client_connect`, 세션 전 명령의 대기와 순서, `mediaSessionId`와 요청 번호, 음량 명령과 범위 검사, `MEDIA_STATUS` 풀기, 음량 두 경로, 알 수 없는 메시지, `disconnect`, 사라지는 경로, `close`.

실제 장치 시험은 자동화하지 않았습니다(장치와 이 컴퓨터가 제공하는 영상 서버가 있어야 함). 한 번 직접 돌린 결과는 F114에 있습니다.

## 확인하지 못한 것

DIAL 싱크, 스피커 그룹(`그룹` 싱크), 탭 미러링(CEF의 소스 URN이 `None`), 연결이 끊길 때의 상태, `GET_STATUS`, Chromecast with Google TV 같은 다른 기종, macOS. `client_connect`가 없어도 되는지.

## 관련 페이지

- [열린 API 확인 기록](verified-findings-opened.md)
- [JavascriptBridge](javascript-bridge.md)
