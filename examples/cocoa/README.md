# Cocoa 창에 붙이는 cefweaver (macOS)

`NSWindow`의 content view에 cefweaver 브라우저를 자식 `NSView`로 붙이는 예제입니다(`CefApp.parent_view`). SwiftUI의 `NSViewRepresentable`이 만든 뷰도 같은 방식입니다. 오프스크린이 아니라서 CEF가 직접 그리고 입력을 처리합니다.

| 파일 | 내용 |
| --- | --- |
| `quickstart.py` | 창 하나와 브라우저. `NSApp.run()`이 루프를 돌리고 `NSTimer`가 `MessagePump.run()`을 부릅니다. `--seconds N`이면 N초 뒤에 창을 닫는 입력을 스스로 합니다 |

```sh
cd examples/cocoa
uv sync
uv run python quickstart.py https://example.org/
```

알아 둘 것:

- `NSTimer` 블록은 `None`을 돌려줘야 합니다. 값을 돌려주면 PyObjC가 예외를 Objective-C로 올리고 AppKit이 프로세스를 죽입니다.
- 창이 닫히는 중에 `shutdown()`을 부르지 않습니다. `windowShouldClose_`가 `False`를 돌려주고 타이머로 미룹니다.
- 뷰는 메인 스레드에서 `initialize()`를 부르기 전에 있어야 합니다.
- 확인한 범위는 [실행해서 확인한 macOS](../../llm-wiki/pages/reference/verified-findings-macos.md)의 F84입니다.
