---
title: 바이트열과 시간
type: reference
sources:
  - tools/gen/typesys.py
  - tools/gen/emit_cython.py
  - tools/gen/emit_pyi.py
  - tools/gen/scope.py
  - tests/test_generator.py
  - tests/test_smoke.py
updated: 2026-10-08
---

# 바이트열과 시간

`void*`와 `CefBaseTime`을 Python 값으로 바꾸는 규칙입니다. 포인터는 헤더만으로는 길이와 소유자를 알 수 없어서 규약을 `tools/gen/typesys.py`의 표에 적고, 표에 없는 `void*`는 이유와 함께 제외합니다. 시험 `test_every_pointer_to_void_is_generated_or_says_why`가 "아무 설명 없는 `untyped pointer`"가 남지 않게 지킵니다.

## 포인터의 표

| 표 | 규약 | Python | 해당 메서드 |
| --- | --- | --- | --- |
| (자동) | 라이브러리의 `const void* p, size_t n`(뒤에 `size_t`가 또 오면 제외) | 바이트열 입력 | `BinaryValue.create`, `BrowserHost.send_dev_tools_message`, `Image.add_*` 등 |
| `BYTES_IN_COPY` | const가 없지만 CEF가 복사만 하는 `void*` | 바이트열 입력 | `StreamReader.create_for_data`, `V8Value.create_array_buffer_with_copy` |
| `BYTES_OUT` | `void* buffer, size_t size`를 CEF가 채움 | `get_data(size, offset) -> bytes` 등 | `BinaryValue.get_data`, `ZipReader.read_file` |
| `BYTES_SIZE_FIRST` | 크기가 포인터 앞: `size_t size, void* bytes` | `set_to_bytes(bytes)`, `get_bytes(size) -> bytes` | `PostDataElement` |
| `ITEM_BYTES` | `ptr, size, n`(`fread`/`fwrite`) | `read(n, size=1)`, `write(data, size=1)` | 스트림([스트림과 ZIP 읽기](streams.md)) |
| `SIZED_BUFFERS` | 핸들러의 크기 없는 포인터(헤더 주석이 크기를 말함) | 읽기 전용 또는 쓰기 가능한 `memoryview` | `RenderHandler.on_paint`, `ReadHandler.read`, `WriteHandler.write` |
| (자동, 핸들러) | `const void* p, size_t n`이면 읽기 전용, 아니면 쓰기 가능한 `memoryview` | `memoryview` | `DevToolsMessageObserver`, `ServerHandler.on_web_socket_message` 등 |
| `DELIBERATE_POINTERS` | 일부러 제외 | (사유가 보고서에 적힘) | 아래 |

일부러 제외하는 포인터는 CEF나 V8이 소유하는 메모리를 가리키거나(`BinaryValue.get_raw_data`, `SharedMemoryRegion.memory`, `V8BackingStore.data`, `V8Value.get_array_buffer_data`), V8과 공유되어 콜백으로 해제되거나(`V8Value.create_array_buffer`, `V8ArrayBufferReleaseCallback.release_buffer`), CEF가 핸들러가 돌려준 포인터를 보관하는 것(`ResourceBundleHandler.get_data_resource`, `..._for_scale`)입니다. Python 객체가 그 메모리보다 오래 살면 해제된 메모리를 가리킬 수 있어서입니다. 복사하는 대체 메서드가 있으면 그것을 씁니다(`get_data`, `create_array_buffer_with_copy`).

## 시간

`CefBaseTime`은 1601-01-01 UTC부터의 마이크로초(`cef_time.h`)이고 Python에서는 시간대가 있는 `datetime`(UTC)입니다. CEF의 "시간 없음"(0)은 `None`입니다. 시간대 없는 `datetime`을 주면 UTC로 봅니다. 변환은 산술이라 CEF 함수를 부르지 않고 마이크로초 정밀도를 유지합니다.

| 방향 | 지원 |
| --- | --- |
| 라이브러리 메서드의 반환 | 지원: `DownloadItem.get_start_time`/`get_end_time`, `ZipReader.get_file_last_modified`(이 둘은 시험으로 확인), 범위 밖 `NavigationEntry`, `X509Certificate`, `V8Value.get_date_value` |
| 라이브러리 메서드의 입력 | 지원(예: `V8Value.create_date`, 범위 밖) |
| 핸들러 메서드의 입력 | 지원 |
| 핸들러의 반환과 출력 | 지원하지 않음 |
| 구조체 안의 필드(쿠키) | 지원하지 않음(쿠키 구조체가 없음) |

java-cef는 `CefBaseTime`을 `java.util.Date`로 바꾸는 한 방향(CEF에서 Java로)뿐이고 `cef_time_from_basetime`을 거쳐 밀리초로 줄입니다(`jni_scoped_helpers.cpp`의 `NewJNIDate`).

## 관련 페이지

- [스트림과 ZIP 읽기](streams.md)
- [바인딩 생성기의 설계](../concepts/binding-generator.md)
- [생성 범위와 커버리지](generated-api-coverage.md)
