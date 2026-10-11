# The Python extension module cefweaver._cefweaver and the files of the wheel (scikit-build-core).
#
# The module is built here and not in setup.py so that it gets the same compiler, runtime library and link
# libraries as cefwrapper and libcef_dll_wrapper (they come from CEF's own cmake), on every platform.

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_program(CYTHON_EXECUTABLE NAMES cython cython3 HINTS "${Python_EXECUTABLE}/.." REQUIRED)

set(CEFWEAVER_PYX "${CMAKE_SOURCE_DIR}/cefweaver/_cefweaver.pyx")
set(CEFWEAVER_CPP "${CMAKE_CURRENT_BINARY_DIR}/_cefweaver.cpp")
# The .pyx includes the .pxi files; a change of any of them must run Cython again.
file(GLOB_RECURSE CEFWEAVER_CYTHON_DEPS CONFIGURE_DEPENDS
     "${CMAKE_SOURCE_DIR}/cefweaver/*.pxi" "${CMAKE_SOURCE_DIR}/cefweaver/*.pxd")
add_custom_command(
  OUTPUT "${CEFWEAVER_CPP}"
  COMMAND "${CYTHON_EXECUTABLE}" --cplus -I "${CMAKE_SOURCE_DIR}/cefweaver" "${CEFWEAVER_PYX}" -o "${CEFWEAVER_CPP}"
  DEPENDS "${CEFWEAVER_PYX}" ${CEFWEAVER_CYTHON_DEPS}
  COMMENT "Cython: _cefweaver.pyx"
  VERBATIM)

Python_add_library(_cefweaver MODULE WITH_SOABI "${CEFWEAVER_CPP}")
target_include_directories(_cefweaver PRIVATE "${CEF_ROOT}" "${CMAKE_SOURCE_DIR}/native/cefwrapper")
target_compile_definitions(_cefweaver PRIVATE NDEBUG=1 $<$<PLATFORM_ID:Linux>:_FILE_OFFSET_BITS=64>)
target_compile_features(_cefweaver PRIVATE cxx_std_20)
# cefwrapper brings libcef_dll_wrapper, libcef and the system libraries (in the right order).
target_link_libraries(_cefweaver PRIVATE cefwrapper)
if(OS_LINUX)
  set_target_properties(_cefweaver PROPERTIES BUILD_WITH_INSTALL_RPATH ON INSTALL_RPATH "$ORIGIN")
endif()
if(OS_MAC)
  # The frameworks and -ObjC are what setup.py passed (it built and ran on macOS arm64, 2026-10-09); libcef is not linked
  # (the framework is loaded at run time, native/cefwrapper/mac_runtime.mm).
  target_link_libraries(_cefweaver PRIVATE "-framework Cocoa" "-framework AppKit" "-framework IOSurface")
  target_link_options(_cefweaver PRIVATE "-Wl,-ObjC")
  # setup.py set MACOSX_DEPLOYMENT_TARGET=12.0 and -mmacosx-version-min=12.0: the wrapper libraries are built for macOS 12.
  target_compile_options(_cefweaver PRIVATE "-mmacosx-version-min=12.0")
  target_link_options(_cefweaver PRIVATE "-mmacosx-version-min=12.0")
  # The helper apps (native/cefsubprocess) are built with the module.
  add_dependencies(_cefweaver cefsubprocess)
endif()
install(TARGETS _cefweaver LIBRARY DESTINATION cefweaver RUNTIME DESTINATION cefweaver)

# The CEF runtime next to the module (CEF looks for icudtl.dat next to libcef.so; cefsubprocess finds libcef.so through
# its rpath). The sandbox helper is not used (no_sandbox).
if(OS_LINUX)
  install(TARGETS cefsubprocess RUNTIME DESTINATION cefweaver)
  file(GLOB CEFWEAVER_RUNTIME "${CEF_ROOT}/Release/*" "${CEF_ROOT}/Resources/*")
  list(FILTER CEFWEAVER_RUNTIME EXCLUDE REGEX "/chrome-sandbox$")
  foreach(entry IN LISTS CEFWEAVER_RUNTIME)
    if(IS_DIRECTORY "${entry}")
      install(DIRECTORY "${entry}" DESTINATION cefweaver)
    else()
      install(PROGRAMS "${entry}" DESTINATION cefweaver)
    endif()
  endforeach()
  # install.strip strips targets only; libcef.so (1.4 GB with its symbols, about 270 MB without) is a plain file here.
  install(CODE "
    if(CMAKE_INSTALL_DO_STRIP)
      execute_process(COMMAND \"${CMAKE_STRIP}\" --strip-unneeded \"\${CMAKE_INSTALL_PREFIX}/cefweaver/libcef.so\")
    endif()")
endif()

# macOS: cefsubprocess.app, the stand-in for the main app bundle of the Python process (CefSettings.main_bundle_path points
# at it, native/cefwrapper/mac_runtime.mm): the CEF framework and the helper apps in its Contents/Frameworks. The helpers
# look for the framework next to themselves. They are copied as they are (install.strip would invalidate their ad hoc
# signatures, which arm64 needs). The bundle is not in the source tree: .gitignore leaves it out of the wheel.
if(OS_MAC)
  set(CEFWEAVER_APP "cefweaver/cefsubprocess.app/Contents")
  install(FILES "${CMAKE_SOURCE_DIR}/native/cefsubprocess/mac/Info.plist" DESTINATION "${CEFWEAVER_APP}")
  install(DIRECTORY "${CEF_ROOT}/Release/Chromium Embedded Framework.framework" DESTINATION "${CEFWEAVER_APP}/Frameworks"
          USE_SOURCE_PERMISSIONS)
  foreach(helper "" " (Alerts)" " (GPU)" " (Plugin)" " (Renderer)")
    install(DIRECTORY "${CMAKE_BINARY_DIR}/native/cefsubprocess/${CMAKE_BUILD_TYPE}/cefsubprocess Helper${helper}.app"
            DESTINATION "${CEFWEAVER_APP}/Frameworks" USE_SOURCE_PERMISSIONS)
  endforeach()
endif()
