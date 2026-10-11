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

DIAL 싱크(이 네트워크의 40초 검색에서 싱크 세 개가 모두 Cast였고 DIAL 싱크는 없었음), 스피커 그룹(`그룹` 싱크, 실행마다 목록에 있다가 없다가 함), `욕실`(화면 없는 스피커)에서의 재생, 탭 미러링(CEF 소스 `libcef/browser/media_router/media_router_impl.cc`의 `GetSource`가 `http`/`https` URL에 "We don't support tab/desktop mirroring"이라는 주석과 함께 NULL을 돌려줍니다. 2026-10-11에 소스로 확인. 우회 방안은 아래), 장치 전원이나 Wi-Fi가 끊길 때의 상태, `GET_STATUS`(응답이 오지 않음), Chromecast with Google TV 같은 다른 기종, macOS. `client_connect`가 없어도 되는지.

## 탭 미러링을 하려면 (조사만 했고 만들지 않았습니다)

`MediaRouter`로는 안 됩니다(위). 가능한 우회로는 두 가지를 생각했고 둘 다 시험하지 않았습니다.

1. **직접 송출**: 시제품으로 `집`에서 동작했습니다(F114: naver.com을 보냈고 화면의 겹친 시각이 실제와 일치하는 듯함, 지연은 숫자로 재지 않음, 소리 없음, 상태는 `BUFFERING`과 `PLAYING`을 자주 오감). 라이브러리에는 넣지 않았습니다. 인코더(gstreamer)가 필요하고, 소리(`AudioHandler`), 안정적인 재생, 정리가 남았습니다.
2. **Chrome 런타임의 Cast 메뉴**: CEF 154의 Chrome 스타일 브라우저에 Cast 기능이 있는지는 확인하지 않았습니다.

## 관련 페이지

- [열린 API 확인 기록](verified-findings-opened.md)
- [JavascriptBridge](javascript-bridge.md)
