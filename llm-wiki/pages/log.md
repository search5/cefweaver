
## [2026-10-08] ingest | 드래그 시작 전략과 드롭 통합 (cefweaver.ui)

- 툴킷 고유의 사정이던 wx의 "다음 이동에서 시작"과 Qt의 "루프에서 시작"을 어댑터의 `drag_start`(`immediate`, `posted`, `on_motion`)로 뷰에 올렸고, 자기 드래그와 외부 드롭의 구분(wx의 `_dragging_out`)도 뷰의 `drag_enter` 등과 `dragging_out`으로 옮겼습니다. 여섯 예제의 점검은 바뀌지 않고 통과합니다. Qt는 `post`가 같은 스레드에서도 큐를 거치게 고쳤습니다("루프에서"의 의미).
