# Copyright (c) 2023 The Chromium Embedded Framework Authors. All rights
# reserved. Use of this source code is governed by a BSD-style license that
# can be found in the LICENSE file.

#
# Shared configuration.
#

# For VS2019 and Xcode 12+ support.
cmake_minimum_required(VERSION 3.19)

# Only generate Debug and Release configuration types.
set(CMAKE_CONFIGURATION_TYPES Debug Release)

# Project name.
project(cefweaver)

# Use folders in the resulting project files.
set_property(GLOBAL PROPERTY OS_FOLDERS ON)


#
# CEF configuration.
#

# Specify the CEF distribution version.
if(NOT DEFINED CEF_VERSION)
  set(CEF_VERSION "154.0.34+g14c5a08+chromium-154.0.8037.98")
endif()

# macOS needs the CEF framework loader, helper app bundles and a Cocoa message
# loop integration, none of which are implemented yet.
if("${CMAKE_SYSTEM_NAME}" STREQUAL "Darwin")
  message(FATAL_ERROR "cefweaver does not support macOS yet. "
                      "Supported platforms: Linux, Windows.")
endif()

# Determine the platform.
if("${CMAKE_SYSTEM_NAME}" STREQUAL "Darwin")
  if("${PROJECT_ARCH}" STREQUAL "arm64")
    set(CEF_PLATFORM "macosarm64")
  elseif("${PROJECT_ARCH}" STREQUAL "x86_64")
    set(CEF_PLATFORM "macosx64")
  elseif("${CMAKE_HOST_SYSTEM_PROCESSOR}" STREQUAL "arm64")
    set(PROJECT_ARCH "arm64")
    set(CEF_PLATFORM "macosarm64")
  else()
    set(PROJECT_ARCH "x86_64")
    set(CEF_PLATFORM "macosx64")
  endif()
elseif("${CMAKE_SYSTEM_NAME}" STREQUAL "Linux")
  if(CMAKE_SIZEOF_VOID_P MATCHES 8)
    set(CEF_PLATFORM "linux64")
  else()
    set(CEF_PLATFORM "linux32")
  endif()
elseif("${CMAKE_SYSTEM_NAME}" STREQUAL "Windows")
  if(CMAKE_SIZEOF_VOID_P MATCHES 8)
    set(CEF_PLATFORM "windows64")
  else()
    set(CEF_PLATFORM "windows32")
  endif()
endif()

# Add this project's cmake/ directory to the module path.
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_CURRENT_SOURCE_DIR}/cmake")

# Resolve the CEF binary distribution. Priority:
#   1. -DCEF_ROOT=<path>  (self-built CEF or an already extracted prebuilt)
#   2. CEF_ROOT environment variable
#   3. Download the prebuilt distribution (executes DownloadCEF.cmake).
if(NOT CEF_ROOT AND DEFINED ENV{CEF_ROOT})
  file(TO_CMAKE_PATH "$ENV{CEF_ROOT}" CEF_ROOT)
endif()

if(CEF_ROOT)
  if(NOT EXISTS "${CEF_ROOT}/cmake/FindCEF.cmake")
    message(FATAL_ERROR "CEF_ROOT is not a valid CEF binary distribution "
                        "(cmake/FindCEF.cmake not found): ${CEF_ROOT}")
  endif()
  message(STATUS "Using existing CEF distribution: ${CEF_ROOT}")
else()
  include(DownloadCEF)
  DownloadCEF("${CEF_PLATFORM}" "${CEF_VERSION}" "${CMAKE_SOURCE_DIR}/third_party/cef")
endif()

# Record the resolved location for tools/prepare.py. CEF_ROOT itself is not
# cached, so that a previous run cannot pin an old version.
set(CEFWEAVER_CEF_ROOT "${CEF_ROOT}" CACHE INTERNAL "Resolved CEF distribution")

# Report the CEF version actually in use (it may differ from CEF_VERSION when
# CEF_ROOT is supplied externally).
if(EXISTS "${CEF_ROOT}/include/cef_version.h")
  file(STRINGS "${CEF_ROOT}/include/cef_version.h" CEF_VERSION_LINE
       REGEX "^#define CEF_VERSION \"")
  message(STATUS "CEF version in use: ${CEF_VERSION_LINE}")
endif()

# Add the CEF binary distribution's cmake/ directory to the module path.
set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CEF_ROOT}/cmake")

# Load the CEF configuration (executes FindCEF.cmake).
find_package(CEF REQUIRED)

#
# Python configuration.
#

# Support specification of the Python executable path via the command-line.
if(DEFINED ENV{PYTHON_EXECUTABLE})
  file(TO_CMAKE_PATH "$ENV{PYTHON_EXECUTABLE}" PYTHON_EXECUTABLE)
endif()

if(NOT PYTHON_EXECUTABLE)
  unset(PYTHON_EXECUTABLE)

  # Find the python interpreter.
  find_package(PythonInterp)

  if(NOT ${PYTHONINTERP_FOUND})
    message(FATAL_ERROR "A Python installation is required. Set the "
                        "PYTHON_EXECUTABLE environment variable to explicitly "
                        "specify the Python executable path.")
  endif()
endif()

message(STATUS "Using Python: ${PYTHON_EXECUTABLE}")

#
# Post-configuration actions.
#

# Copy the CEF README.txt file to the cmake build directory for use by the
# make_readme.py script.
file(COPY "${CEF_ROOT}/README.txt" DESTINATION "${CMAKE_BINARY_DIR}")

option(CEFWEAVER_FETCH_CLANG_FORMAT "Download clang-format from Google Storage" OFF)
if(CEFWEAVER_FETCH_CLANG_FORMAT)
  # Download clang-format from Google Storage.
  if(OS_WINDOWS)
    set(GS_PLATFORM "win32")
    set(GS_HASHPATH "win/clang-format.exe.sha1")
    set(GS_OUTPATH "win/clang-format.exe")
  elseif(OS_MACOSX)
    set(GS_PLATFORM "darwin")
    if("${CMAKE_HOST_SYSTEM_PROCESSOR}" STREQUAL "arm64")
      set(GS_HASHPATH "mac/clang-format.arm64.sha1")
    else()
      set(GS_HASHPATH "mac/clang-format.x64.sha1")
    endif()
    set(GS_OUTPATH "mac/clang-format")
  elseif(OS_LINUX)
    set(GS_PLATFORM "linux*")
    set(GS_HASHPATH "linux64/clang-format.sha1")
    set(GS_OUTPATH "linux64/clang-format")
  endif()

  message(STATUS "Downloading clang-format from Google Storage...")
  execute_process(
    COMMAND "${PYTHON_EXECUTABLE}"
            "tools/buildtools/download_from_google_storage.py"
            "--no_resume"
            "--platform=${GS_PLATFORM}"
            "--no_auth"
            "--bucket" "chromium-clang-format"
            "-s" "tools/buildtools/${GS_HASHPATH}"
            "-o" "tools/buildtools/${GS_OUTPATH}"
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    RESULT_VARIABLE EXECUTE_RV
    )
  if(NOT EXECUTE_RV STREQUAL "0")
    message(FATAL_ERROR "Execution failed with unexpected result: ${EXECUTE_RV}")
  endif()
endif()


#
# Include target subdirectories.
#

add_subdirectory(${CEF_LIBCEF_DLL_WRAPPER_PATH} libcef_dll_wrapper)
#add_subdirectory(native)

add_subdirectory(native/cefwrapper)
add_subdirectory(native/cefsubprocess)

#if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/src/cefwrappertest")
#  add_subdirectory(src/cefwrappertest)
#endif()


#
# Display configuration settings.
#

PRINT_CEF_CONFIG()

message(STATUS "*** CEFWEAVER CONFIGURATION SETTINGS ***")
message(STATUS "Python executable:            ${PYTHON_EXECUTABLE}")
