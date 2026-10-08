---
title: 실제 영상이 재생되는지 확인하기 (유튜브)
type: procedure
sources:
  - tests/playback_check.py
  - examples/gtk3/quickstart.py
  - cefweaver/ui/session.py
updated: 2026-10-08
---

# 실제 영상이 재생되는지 확인하기 (유튜브)

단위 시험은 네트워크와 실제 사이트를 쓰지 않으므로, 실제 영상(유튜브)이 도는지는 **수동 점검**으로 확인합니다. 도구는 `tests/playback_check.py`이고 시험 모음에는 들어 있지 않습니다(네트워크와 유튜브에 의존).

```sh
# 기본 CEF 앱(자기 창이 있는 앱)
xvfb-run -a python tests/playback_check.py windowed
# 예제의 quickstart.py를 그대로(오프스크린): gtk3, qt, tk, sdl2, wx, kivy
xvfb-run -a python tests/playback_check.py gtk3 GDK_BACKEND=x11
xvfb-run -a python tests/playback_check.py qt --venv .venv-pyside QT_QPA_PLATFORM=xcb
```

가상 화면(`xvfb-run`)에서 하고, 소리는 Chromium의 가짜 출력(`disable-audio-output`)으로 보내므로 **아무도 듣지 않습니다**. 점검이 하는 일은 다음과 같습니다.

1. 툴킷이면 해당 예제의 환경(uv)에서 `quickstart.py`를 **고치지 않고** 실행하되, `Session.start`에 점검을 끼웁니다. 3초마다 페이지가 `<video>`의 상태(`currentTime`, `paused`, `readyState`, 크기, 오류, 광고 여부)를 노출한 함수 `__probe`로 알려 주고(`bridge.evaluate`는 쓰지 않음: 아래), 뷰의 그림이 이전과 다른지 CRC로 셉니다. 일정은 루프 객체의 `call_later`로 잡으므로 툴킷에 상관없습니다.
2. 끝나면 창을 닫기 버튼처럼(`WM_DELETE_WINDOW`) 닫고 프로그램이 **종료 코드 0**으로 끝나는지 봅니다. 작업 폴더는 임시 디렉터리입니다(CEF가 `cache/`를 작업 폴더에 만들기 때문).
3. **합격 기준**: 영상의 시간이 시계의 80% 이상으로 흐르고, 멈추지 않았고, 데이터가 있고(`readyState` 3 이상), 오류가 없고, (오프스크린은) 그림이 3가지 이상으로 바뀝니다.

결과는 [F73](../reference/verified-findings-media.md)에 있습니다. 소리가 실제로 나는지는 이 도구로 확인하지 않습니다(필요하면 `disable-audio-output`을 빼고 실제 화면에서 사람이 듣습니다. 실제 화면에 창이 열리므로 허락을 받고 하십시오).

## 관련 페이지

- [시험 실행하기](run-tests.md)
- [UI 어댑터 API](../reference/ui-api.md)
