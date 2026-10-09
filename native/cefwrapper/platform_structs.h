#ifndef CEFWEAVER_PLATFORM_STRUCTS_H_
#define CEFWEAVER_PLATFORM_STRUCTS_H_

// CEF defines a few structs differently on each platform (include/internal/cef_types_linux.h,
// _mac.h and _win.h). The generated bindings are the same everywhere, so they read these
// structs in their Linux form through the types below (see PLATFORM_STRUCTS in tools/gen/
// model.py). On Linux the types are CEF's own; elsewhere they are a copy of the Linux form
// that only holds what the platform has in common with it.

#include "include/internal/cef_types.h"
#include "include/internal/cef_types_wrappers.h"

#if defined(OS_LINUX)

typedef cef_accelerated_paint_native_pixmap_plane_t CwAcceleratedPaintNativePixmapPlane;
typedef CefAcceleratedPaintInfo CwAcceleratedPaintInfo;

inline const CwAcceleratedPaintInfo& CwAcceleratedPaintInfoFromCef(
    const CefAcceleratedPaintInfo& info) {
  return info;
}

#else

struct CwAcceleratedPaintNativePixmapPlane {
  uint32_t stride;
  uint64_t offset;
  uint64_t size;
  int fd;
};

// The shared texture of this platform (an IOSurface on macOS, a handle on Windows) is not
// passed to Python yet: the planes stay empty, the format and the common info are the real ones.
struct CwAcceleratedPaintInfo {
  CwAcceleratedPaintNativePixmapPlane planes[4];
  int plane_count;
  uint64_t modifier;
  cef_color_type_t format;
  cef_accelerated_paint_info_common_t extra;
};

inline CwAcceleratedPaintInfo CwAcceleratedPaintInfoFromCef(const CefAcceleratedPaintInfo& info) {
  CwAcceleratedPaintInfo result = {};
  result.format = info.format;
  result.extra = info.extra;
  return result;
}

#endif

#endif  // CEFWEAVER_PLATFORM_STRUCTS_H_
