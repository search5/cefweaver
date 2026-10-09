---
title: 리소스 제공 (스킴 핸들러와 add_resource)
type: concept
sources:
  - cefweaver/_cefweaver.pyx
  - cefweaver/cef_api.pxi
  - tools/gen/scope.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 리소스 제공 (스킴 핸들러와 add_resource)

네트워크 없이 가짜 URL의 페이지를 제공하는 기능입니다. 바인딩 생성기의 1단계 범위이며([바인딩 생성기의 설계](binding-generator.md)), java-cef의 시험이 쓰는 `addResource`에 해당합니다([java-cef 시험과의 비교](../analyses/java-cef-test-comparison.md)).

## 생성된 저수준 API

CEF에서 `CefSchemeHandlerFactory`는 등록된 스킴과 도메인의 요청마다 `Create()`로 `CefResourceHandler`를 만듭니다. Python에서는 다음과 같습니다.

```python
class Factory(cefweaver.SchemeHandlerFactory):
    def create(self, browser, frame, scheme_name, request):
        return MyHandler()          # 또는 None

cefweaver.register_scheme_handler_factory("http", "app.test", Factory())
```

`create()`가 `None`을 돌려주면 "기본 처리를 허용"한다는 뜻입니다. `browser`와 `frame`은 헤더(`optional_param`)가 선택 인자로 표시하므로 `None`일 수 있습니다. 내장 스킴(`http`, `https`)에서 핸들러가 반환되지 않으면 CEF가 내장 처리기를 부른다고 `cef_scheme.h`가 설명합니다. 이 경우의 실제 네트워크 동작은 시험하지 않았습니다.

`ResourceHandler`의 메서드와 반환 형식은 아래와 같고, 출력 인자는 반환값으로 돌려줍니다([핸들러 프록시 구조](handler-proxies.md)).

| 메서드 | 반환 |
| --- | --- |
| `open(request, callback)` | `(handled, handle_request)` |
| `process_request(request, callback)` | `bool` (이전 방식) |
| `get_response_headers(response)` | `(response_length, redirect_url)` |
| `skip(bytes_to_skip, callback)` | `(bool, bytes_skipped)` |
| `read(data_out, callback)` | `(bool, bytes_read)` |
| `read_response(data_out, callback)` | `(bool, bytes_read)` (이전 방식) |
| `cancel()` | 없음 |

- `data_out`은 CEF 버퍼를 가리키는 쓰기 가능한 `memoryview`입니다. 길이가 `bytes_to_read`이며 호출이 끝나면 무효화되므로 보관하면 안 됩니다.
- **응답의 끝**은 `read`가 `(False, 0)`을 돌려줘서 알립니다. 항상 `(True, n)`을 돌려주면 응답이 끝나지 않고 본문이 반복됩니다(초기 시험 코드가 이 오류를 냈습니다).
- **비동기 응답**: `open`이 `(True, False)`를 돌려주면 "처리하지만 나중에 알려 주겠다"는 뜻이고, 나중에(다른 스레드여도 됩니다) `callback.continue_()`를 부릅니다. 지연된 응답은 0.3초 뒤 별도 스레드의 `threading.Timer`로 시험했습니다.
- 핸들러 안의 예외는 `sys.excepthook`으로 보고되고 요청은 실패하지만, 이후 다른 페이지는 정상 로드됩니다(시험으로 확인).

## add_resource

```python
app.initialize("about:blank")
app.add_resource("http://app.test/index.html", "<h1>hello</h1>",
                 mime_type="text/html", headers={"X-Test": "yes"}, status=200)
app.load_url("http://app.test/index.html")
```

`CefApp.add_resource()`(`cefweaver/_cefweaver.pyx`)는 생성된 API만 써서 구현한 손으로 쓴 편의 기능입니다.

- `initialize()` 후에만 부를 수 있습니다(그 전에는 `RuntimeError`). `http`, `https`가 아니거나 호스트가 없는 URL은 `ValueError`입니다.
- 내용은 `str`(UTF-8로 인코딩)이나 `bytes`입니다.
- 요청 URL의 쿼리와 프래그먼트는 무시하고 `scheme://netloc/path`로 찾습니다(`_resource_key`).
- `(scheme, hostname)` 쌍마다 처음 한 번만 `register_scheme_handler_factory()`를 부릅니다. 모든 리소스는 `CefApp`이 가진 하나의 `_StaticResourceFactory`가 담당합니다.
- `_StaticResource`(`ResourceHandler` 하위 클래스)가 `open`에서 `(True, True)`를 돌려주고, `get_response_headers`에서 MIME 형식, 상태 코드, 헤더(`set_header_by_name`, 덮어쓰기)를 설정하고, `read`에서 `memoryview`로 본문을 나눠 복사합니다.

시험으로 확인한 것은 한글 제목의 페이지, 하위 리소스(스크립트), 300KB 본문(여러 번 나눠 읽힌 뒤 해시 일치), 응답 헤더, 404 상태입니다(`tests/test_smoke.py`).

## 관련 페이지

- [핸들러 프록시 구조](handler-proxies.md)
- [생성된 파일](../components/generated-files.md)
- [시험](../components/tests.md)
- [사용하지 않는 코드와 유산](../components/legacy-code.md)
