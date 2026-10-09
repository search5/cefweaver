---
title: 컨텍스트 메뉴
---

# 컨텍스트 메뉴 (오른쪽 클릭)

오프스크린 브라우저에서는 CEF가 메뉴를 그려 주지 않습니다. 그래서 `cefweaver.ui`가 CEF의 메뉴 모델을 읽어 **툴킷의 메뉴 위젯**으로 보여 줍니다. 어댑터에 `show_menu`가 있는 툴킷에서 됩니다.

| 툴킷 | 메뉴 |
| --- | --- |
| GTK 3 | `Gtk.Menu` |
| Qt | `QMenu` |
| Tk | `tkinter.Menu` |
| wxPython | `wx.Menu` |
| SDL2, Kivy | 없음 ([툴킷별 상태](toolkits.md) 참고) |

## 항목은 누가 실행하나요

메뉴의 항목은 대부분 CEF가 정한 표준 명령입니다(뒤로, 앞으로, 복사, 붙여넣기, 맞춤법 추천 등). 어떤 항목이 보일지는 클릭한 곳에 따라 달라집니다(글자를 선택했는지, 입력란인지, 링크인지, 틀린 철자인지). 라벨은 로케일을 따릅니다(한국어에서는 `뒤로(B)` 같은 모양).

선택한 항목을 실행하는 주체는 항목에 따라 다릅니다. 메뉴가 열려 있는 동안 툴킷의 메뉴가 키보드 포커스를 가져가고, 그 뒤에 CEF에게 시키면 아무 일도 하지 않는 명령이 있기 때문입니다.

| 항목 | 실행 |
| --- | --- |
| 복사, 잘라내기, 붙여넣기, 일반 텍스트로 붙여넣기 | 뷰가 **툴킷의 클립보드**로 처리합니다(Ctrl+C 등과 같은 경로). Wayland에서는 CEF의 클립보드가 컴포지터의 것이라 툴킷에 닿지 않기 때문입니다 |
| 실행 취소, 다시 실행, 삭제, 전체 선택 | 뷰가 클릭된 프레임의 편집 API로 직접 실행합니다 |
| 맞춤법 추천 단어, 사전에 추가 | 뷰가 `BrowserHost.replace_misspelling()`, `add_word_to_dictionary()`로 실행합니다 |
| 그 밖의 표준 명령(뒤로, 앞으로, 새로 고침 등) | CEF에 `continue_`로 넘겨 CEF가 실행합니다 |
| 앱이 더한 항목 | 앱이 준 함수(`action`)를 실행합니다 |

## 앱이 메뉴를 고치기

`view.on_context_menu`에 훅을 걸어 항목을 빼거나 더합니다.

```python
from cefweaver import ui

def hook(info, items):
    # 맞춤법 항목을 빼고, 앱의 항목을 하나 더합니다
    spelling = set(ui.menu.SPELLING_SUGGESTIONS) | {ui.menu.ADD_TO_DICTIONARY}
    items = [item for item in items if item.command_id not in spelling]
    items.append(ui.menu.MenuItem("페이지 주소 보기", action=lambda: print(info.page_url)))
    return items                                  # None을 돌려주면 메뉴를 보이지 않습니다

widget.view.on_context_menu = hook                # 세션을 시작하기 전에 줍니다
```

- `info`는 클릭한 곳을 알려 줍니다: `x`, `y`(뷰 좌표), `link_url`, `source_url`, `page_url`, `selection_text`, `is_editable`, `misspelled_word`, `dictionary_suggestions`, 그리고 CEF의 원본 `params`.
- `items`는 `ui.menu.MenuItem`의 목록입니다. `kind`(`command`, `check`, `radio`, `separator`, `submenu`), `label`, `enabled`, `checked`, `children`, `command_id`를 가집니다. 구분선은 훅이 돌려준 목록에서 맨 앞, 맨 뒤, 연달아 있는 것이 정리됩니다.
- `MenuItem("라벨", action=함수)`는 앱의 항목입니다. 고르면 함수만 실행되고 CEF에는 알리지 않습니다.
- 훅이나 어댑터의 `show_menu`가 예외를 내면 메뉴를 취소하고 `sys.excepthook`으로 보고합니다.

## 새 툴킷에 메뉴 붙이기

어댑터에 `show_menu(items, x, y, done)`를 구현합니다. `items`는 위의 `MenuItem` 목록이고 `(x, y)`는 뷰 좌표입니다. 사용자가 항목을 고르면 `done(그 항목의 command_id)`를, 그냥 닫으면 `done(None)`을 **한 번만** 부릅니다.

실제 데스크톱에서만 나타나는 함정이 있었으니 알아 두세요.

- CEF는 오른쪽 버튼을 **누르는 순간** 메뉴를 요청합니다. 메뉴가 버튼이 눌린 채로 뜨면 이어지는 뗌이 메뉴를 닫는 툴킷이 있습니다(wx). 버튼이 떨어질 때까지 기다렸다가 여세요. GTK 3은 위젯이 받은 실제 버튼 이벤트로 메뉴를 띄우면 됩니다.
- 메뉴가 열려 있는 동안 위젯이 포커스를 잃고 CEF에 "포커스 없음"이 전달될 수 있습니다. 위의 표처럼 뷰가 이를 고려해 명령을 실행하므로 어댑터가 할 일은 없습니다.

## 알려진 제약

- 메뉴의 `인쇄`는 항목이 보이지만 인쇄는 동작하지 않습니다([한계와 알려진 제약](limitations.md)).
- 틀린 철자(영어)를 우클릭하면 추천 단어와 `사전에 추가` 항목이 붙습니다. 필요 없으면 위 훅으로 거를 수 있습니다.
