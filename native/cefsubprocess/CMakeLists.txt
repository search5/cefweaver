# Copyright (c) 2014 The Chromium Embedded Framework Authors. All rights
# reserved. Use of this source code is governed by a BSD-style license that
# can be found in the LICENSE file.

#
# Source files.
#

# cefsubprocess sources.
set(CEFSUB_SRCS
  )
set(CEFSUB_SRCS_WINDOWS
        cefsubprocess.cc
        )
set(CEFSUB_SRCS_LINUX
        cefsubprocess.cc
        )
set(CEFSUB_SRCS_MAC
        cefsubprocess.cc
        )
APPEND_PLATFORM_SOURCES(CEFSUB_SRCS)
source_group(cefsubprocess FILES ${CEFSUB_SRCS})

set(CEFSUB_SRCS
  ${CEFSUB_SRCS}
  )


#
# Shared configuration.
#

# Target executable names.
set(CEF_TARGET "cefsubprocess")
if(OS_MAC)
  set(CEF_HELPER_TARGET "cefsub_Helper")
  # CEF looks for "<main bundle name> Helper*.app" in the main bundle's Contents/Frameworks;
  # the name is also what native/cefwrapper/mac_runtime.mm expects.
  set(CEF_HELPER_OUTPUT_NAME "cefsubprocess Helper")
else()
  # Logical target used to link the libcef library.
  ADD_LOGICAL_TARGET("libcef_lib" "${CEF_LIB_DEBUG}" "${CEF_LIB_RELEASE}")
endif()

# Determine the target output directory.
SET_CEF_TARGET_OUT_DIR()



#
# Windows configuration.
#
add_compile_definitions(_ITERATOR_DEBUG_LEVEL=0)
add_compile_definitions(symbol_level=2)
if(OS_WINDOWS)
  # Executable target.
  add_executable(${CEF_TARGET} WIN32 ${CEFSUB_SRCS})
  add_dependencies(${CEF_TARGET} cefwrapper)
  add_dependencies(${CEF_TARGET} libcef_dll_wrapper)
  SET_EXECUTABLE_TARGET_PROPERTIES(${CEF_TARGET})
  target_link_libraries(${CEF_TARGET} cefwrapper libcef_lib libcef_dll_wrapper ${CEF_STANDARD_LIBS})

  if(USE_SANDBOX)
    # Logical target used to link the cef_sandbox library.
    ADD_LOGICAL_TARGET("cef_sandbox_lib" "${CEF_SANDBOX_LIB_DEBUG}" "${CEF_SANDBOX_LIB_RELEASE}")
    target_link_libraries(${CEF_TARGET} cef_sandbox_lib ${CEF_SANDBOX_STANDARD_LIBS})
  endif()

  # Add the custom manifest files to the executable.
  ADD_WINDOWS_MANIFEST("${CMAKE_CURRENT_SOURCE_DIR}" "${CEF_TARGET}" "exe")

  # Copy binary and resource files to the target output directory.
  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "${CEF_TARGET_OUT_DIR}")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "${CEF_TARGET_OUT_DIR}")

  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "../cefwrappertest/debug/cefsubprocess/")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "../cefwrappertest/debug/cefsubprocess")
  COPY_FILES("${CEF_TARGET}" "cefsubprocess.exe" "${CEF_TARGET_OUT_DIR}" "../cefwrappertest/debug/cefsubprocess")

  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "../cefwrappertest/release/cefsubprocess/")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "../cefwrappertest/release/cefsubprocess")
  COPY_FILES("${CEF_TARGET}" "cefsubprocess.exe" "${CEF_TARGET_OUT_DIR}" "../cefwrappertest/release/cefsubprocess")

  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "../../../src/PyCef_Dev/PyCef/bin/")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "../../../src/PyCef_Dev/PyCef/bin/")

  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "../../../src/PyCef_Dev/PyCef/cefsubprocess/")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "../../../src/PyCef_Dev/PyCef/cefsubprocess/")
  COPY_FILES("${CEF_TARGET}" "cefsubprocess.exe" "${CEF_TARGET_OUT_DIR}" "../../../src/PyCef_Dev/PyCef/cefsubprocess/")
endif()

#
# Linux configuration.
#
if(OS_LINUX)
  add_executable(${CEF_TARGET} ${CEFSUB_SRCS})
  add_dependencies(${CEF_TARGET} cefwrapper)
  add_dependencies(${CEF_TARGET} libcef_dll_wrapper)
  SET_EXECUTABLE_TARGET_PROPERTIES(${CEF_TARGET})
  target_link_libraries(${CEF_TARGET} cefwrapper libcef_lib libcef_dll_wrapper ${CEF_STANDARD_LIBS})

  # Set rpath so that libcef.so can be placed next to the executable.
  set_target_properties(${CEF_TARGET} PROPERTIES INSTALL_RPATH "$ORIGIN")
  set_target_properties(${CEF_TARGET} PROPERTIES BUILD_WITH_INSTALL_RPATH TRUE)
  set_target_properties(${CEF_TARGET} PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${CEF_TARGET_OUT_DIR})

  # Copy binary and resource files to the target output directory.
  COPY_FILES("${CEF_TARGET}" "${CEF_BINARY_FILES}" "${CEF_BINARY_DIR}" "${CEF_TARGET_OUT_DIR}")
  COPY_FILES("${CEF_TARGET}" "${CEF_RESOURCE_FILES}" "${CEF_RESOURCE_DIR}" "${CEF_TARGET_OUT_DIR}")
  if(EXISTS "${CEF_BINARY_DIR}/libminigbm.so")
    COPY_FILES("${CEF_TARGET}" "libminigbm.so" "${CEF_BINARY_DIR}" "${CEF_TARGET_OUT_DIR}")
  endif()
endif()

#
# macOS configuration.
#
# The helper apps are what CEF starts as its child processes (GPU, renderer, ...); each is the
# same executable in a bundle of its own. tools/prepare.py puts them, the CEF framework and
# Info.plist together as cefsubprocess.app in the Python package (the stand-in for the main app
# bundle of the Python process). The framework is not linked: the helpers load it at run time.
#
if(OS_MAC)
  set(CEFSUB_MAC_APPS)
  foreach(_suffix_list ${CEF_HELPER_APP_SUFFIXES})
    # Convert to a list and extract the suffix values.
    string(REPLACE ":" ";" _suffix_list ${_suffix_list})
    list(GET _suffix_list 0 _name_suffix)
    list(GET _suffix_list 1 _target_suffix)
    list(GET _suffix_list 2 _plist_suffix)

    set(_helper_target "${CEF_HELPER_TARGET}${_target_suffix}")
    set(_helper_output_name "${CEF_HELPER_OUTPUT_NAME}${_name_suffix}")

    # One Info.plist per helper, written by hand because MACOSX_BUNDLE_INFO_PLIST uses global
    # variables and would put the wrong values into all but one of the targets.
    set(_helper_info_plist "${CMAKE_CURRENT_BINARY_DIR}/helper-Info${_target_suffix}.plist")
    file(READ "${CMAKE_CURRENT_SOURCE_DIR}/mac/helper-Info.plist.in" _plist_contents)
    string(REPLACE "\${EXECUTABLE_NAME}" "${_helper_output_name}" _plist_contents "${_plist_contents}")
    string(REPLACE "\${PRODUCT_NAME}" "${_helper_output_name}" _plist_contents "${_plist_contents}")
    string(REPLACE "\${BUNDLE_ID_SUFFIX}" "${_plist_suffix}" _plist_contents "${_plist_contents}")
    file(WRITE ${_helper_info_plist} "${_plist_contents}")

    add_executable(${_helper_target} MACOSX_BUNDLE ${CEFSUB_SRCS})
    SET_EXECUTABLE_TARGET_PROPERTIES(${_helper_target})
    add_dependencies(${_helper_target} cefwrapper)
    add_dependencies(${_helper_target} libcef_dll_wrapper)
    target_link_libraries(${_helper_target} cefwrapper libcef_dll_wrapper ${CEF_STANDARD_LIBS})
    set_target_properties(${_helper_target} PROPERTIES
      MACOSX_BUNDLE_INFO_PLIST ${_helper_info_plist}
      OUTPUT_NAME ${_helper_output_name}
      RUNTIME_OUTPUT_DIRECTORY ${CEF_TARGET_OUT_DIR}
      )
    list(APPEND CEFSUB_MAC_APPS ${_helper_target})
  endforeach()

  # A single target for tools/prepare.py to wait for.
  add_custom_target(${CEF_TARGET} ALL)
  add_dependencies(${CEF_TARGET} ${CEFSUB_MAC_APPS})
  configure_file(${CMAKE_CURRENT_SOURCE_DIR}/mac/Info.plist
                 ${CEF_TARGET_OUT_DIR}/cefsubprocess-Info.plist COPYONLY)
endif()
