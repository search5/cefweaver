---
title: 출력 인자와 목록 (Python API)
type: reference
sources:
  - tools/gen/typesys.py
  - tools/gen/emit_cython.py
  - cefweaver/_cefweaver.pyi
updated: 2026-10-10
---

# 출력 인자와 목록 (Python API)

[Python API 참조](python-api.md)에서 나눈 페이지입니다. 생성된 메서드가 C++의 출력 인자와 목록을 Python에서 어떻게 주고받는지 설명합니다.

## 출력 인자를 돌려주는 메서드

C++에서 값을 참조 인자로 돌려주는 라이브러리 메서드는 파이썬에서 **반환값**입니다. 반환값이 있으면 그것이 먼저이고 출력이 뒤따릅니다.

```python
ok, key_code, shift, ctrl, alt = menu.get_accelerator(command_id)   # MenuModel
ok, color = menu.get_color(command_id, types.MenuColorType.TEXT)

point = display.convert_point_to_pixels(types.Point(10, 20))        # Display: a point goes in and comes back
```

구조체 참조(`CefPoint&`)만 입출력으로 다룹니다(`CefDisplay`와 `CefView`의 좌표 변환이 값을 읽고 고치기 때문). 그 밖의 참조 인자는 출력 전용이며 헤더가 방향을 표시하지 않으므로 이 구분은 헤더가 아닌 추정에 근거합니다([알려진 제약과 미검증 항목](known-constraints.md)).

## 목록을 주고받는 메서드

목록의 요소는 문자열(`list[str]`), 숫자(`list[int]`), 값 타입(`list[Rect]`, `list[Range]`), 객체(`list[Display]`)입니다. 라이브러리 메서드에 주는 목록은 아무 시퀀스나 되고 그 안의 값 타입은 일반 튜플도 됩니다.

```python
settings = cefweaver.PrintSettings.create()
settings.set_page_ranges([types.Range(1, 3), (5, 5)])
settings.get_page_ranges()                      # [Range(from_=1, to=3), Range(from_=5, to=5)]
cefweaver.Display.get_all_displays()            # [Display, ...]
ok, ids = cefweaver.TaskManager.get_task_manager().get_task_ids_list()   # (True, [0, 1, ...])

class Drag(cefweaver.DragHandler):
    def on_draggable_regions_changed(self, browser, frame, regions):
        # CSS `-webkit-app-region: drag` gives [DraggableRegion(bounds=Rect(10, 20, 300, 40), draggable=1)]
        ...
```

`Client.get_drag_handler()`가 `DragHandler`를 돌려주면 드래그 영역 변화를 받습니다(`on_drag_enter`는 `DragData`와 함께 옵니다, F54). 프레임 식별자는 `"5-725574D5..."` 같은 문자열이고, 이름 목록의 순서는 호출마다 같다는 보장이 없습니다(`['inner', '']`와 `['', 'inner']`가 모두 나왔습니다). 시험에서 `srcdoc` iframe을 쓸 때는 `data:` 페이지가 아니라 `add_resource` 페이지에 넣어야 합니다(F27).

## 관련 페이지

- [Python API 참조](python-api.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
