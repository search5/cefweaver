# Copyright (c) 2016 The Chromium Embedded Framework Authors. All rights
# reserved. Use of this source code is governed by a BSD-style license that
# can be found in the LICENSE file.

# Download the CEF binary distribution for |platform| and |version| to
# |download_dir|. The |CEF_ROOT| variable will be set in global scope pointing
# to the extracted location.
# Visit https://cef-builds.spotifycdn.com/index.html for the list of
# supported platforms and versions.
#
# Changed from CEF's file (cefweaver): the archive is only ever used after its SHA1 matches the published one, and it
# is unpacked by tools/safe_extract.py, which refuses a member that would write outside the destination.
#  - The archive is downloaded to a ".part" file, checked, and only then moved into place. A file that did not match is
#    deleted, so a second run cannot find it and skip the check (file(DOWNLOAD ... EXPECTED_HASH) leaves the
#    mismatching file behind).
#  - An archive that is already there is checked again against its .sha1 file; if it does not match, it is
#    downloaded again.
#  - The distribution is unpacked into a temporary directory and moved to |CEF_ROOT| as a whole, so an interrupted
#    unpacking is not taken for a finished one.
#  - |platform| and |version| become file names and a URL: only letters, digits and ".+_-" are accepted.
#  - |CEF_DOWNLOAD_BASE_URL| (default: the Spotify CDN of CEF) can be set, e.g. to a mirror or, in the tests, to a
#    file: URL.

set(_CEFWEAVER_DOWNLOAD_CEF_DIR "${CMAKE_CURRENT_LIST_DIR}")

# The SHA1 of |path| as lower case hex in |out|.
function(_cefweaver_sha1 path out)
  file(SHA1 "${path}" _hash)
  string(TOLOWER "${_hash}" _hash)
  set(${out} "${_hash}" PARENT_SCOPE)
endfunction()

# The 40 hex digits in the file |path| (leading and trailing white space allowed) in |out|, or empty if it holds
# anything else.
function(_cefweaver_read_sha1 path out)
  set(_value "")
  if(EXISTS "${path}")
    file(READ "${path}" _text LIMIT 4096)
    string(STRIP "${_text}" _text)
    if(_text MATCHES "^[0-9a-fA-F]+$")
      string(LENGTH "${_text}" _length)
      if(_length EQUAL 40)
        string(TOLOWER "${_text}" _value)
      endif()
    endif()
  endif()
  set(${out} "${_value}" PARENT_SCOPE)
endfunction()

# Download |url| to |path| through a ".part" file; stops with an error if it fails.
function(_cefweaver_fetch url path show_progress)
  file(REMOVE "${path}.part")
  if(show_progress)
    file(DOWNLOAD "${url}" "${path}.part" STATUS _status SHOW_PROGRESS)
  else()
    file(DOWNLOAD "${url}" "${path}.part" STATUS _status)
  endif()
  list(GET _status 0 _code)
  if(NOT _code EQUAL 0)
    file(REMOVE "${path}.part")
    list(GET _status 1 _message)
    message(FATAL_ERROR "Could not download ${url}: ${_message}")
  endif()
endfunction()

function(DownloadCEF platform version download_dir)
  if(NOT version MATCHES "^[0-9A-Za-z.+_-]+$" OR version MATCHES "[.][.]")
    message(FATAL_ERROR "Not a CEF version name: '${version}'")
  endif()
  if(NOT platform MATCHES "^[0-9A-Za-z_]+$")
    message(FATAL_ERROR "Not a CEF platform name: '${platform}'")
  endif()
  if(NOT DEFINED CEF_DOWNLOAD_BASE_URL)
    set(CEF_DOWNLOAD_BASE_URL "https://cef-builds.spotifycdn.com")
  endif()

  # Specify the binary distribution type and download directory.
  set(CEF_DISTRIBUTION "cef_binary_${version}_${platform}")
  set(CEF_DOWNLOAD_DIR "${download_dir}")

  # The location where we expect the extracted binary distribution.
  # Deliberately not cached: a cached value could not be told apart from a
  # user-supplied CEF_ROOT and would pin an old version on later runs.
  set(CEF_ROOT "${CEF_DOWNLOAD_DIR}/${CEF_DISTRIBUTION}")
  set(CEF_ROOT "${CEF_ROOT}" PARENT_SCOPE)

  # Download and/or extract the binary distribution if necessary.
  if(NOT IS_DIRECTORY "${CEF_ROOT}")
    set(CEF_DOWNLOAD_FILENAME "${CEF_DISTRIBUTION}.tar.bz2")
    set(CEF_DOWNLOAD_PATH "${CEF_DOWNLOAD_DIR}/${CEF_DOWNLOAD_FILENAME}")
    set(CEF_SHA1_PATH "${CEF_DOWNLOAD_PATH}.sha1")

    # The Python that runs tools/safe_extract.py: the one of the build if it is known.
    set(_python "")
    foreach(_candidate IN ITEMS "${Python_EXECUTABLE}" "${Python3_EXECUTABLE}" "$ENV{PYTHON_EXECUTABLE}")
      if(NOT _python AND _candidate)
        set(_python "${_candidate}")
      endif()
    endforeach()
    if(NOT _python)
      find_program(CEFWEAVER_EXTRACT_PYTHON NAMES python3 python)
      set(_python "${CEFWEAVER_EXTRACT_PYTHON}")
    endif()
    if(NOT _python)
      message(FATAL_ERROR "A Python interpreter is needed to unpack the CEF archive safely "
                          "(set Python_EXECUTABLE or PYTHON_EXECUTABLE).")
    endif()

    # An archive that is there from an earlier run is used only if it matches its .sha1 file.
    set(_ready FALSE)
    if(EXISTS "${CEF_DOWNLOAD_PATH}")
      _cefweaver_read_sha1("${CEF_SHA1_PATH}" _expected)
      _cefweaver_sha1("${CEF_DOWNLOAD_PATH}" _actual)
      if(_expected AND _expected STREQUAL _actual)
        set(_ready TRUE)
      else()
        message(WARNING "${CEF_DOWNLOAD_PATH} does not match its SHA1; downloading it again.")
        file(REMOVE "${CEF_DOWNLOAD_PATH}" "${CEF_SHA1_PATH}")
      endif()
    endif()

    if(NOT _ready)
      set(CEF_DOWNLOAD_URL "${CEF_DOWNLOAD_BASE_URL}/${CEF_DOWNLOAD_FILENAME}")
      string(REPLACE "+" "%2B" CEF_DOWNLOAD_URL_ESCAPED "${CEF_DOWNLOAD_URL}")

      # Download the SHA1 hash for the binary distribution.
      message(STATUS "Downloading ${CEF_SHA1_PATH} from ${CEF_DOWNLOAD_URL_ESCAPED}.sha1...")
      _cefweaver_fetch("${CEF_DOWNLOAD_URL_ESCAPED}.sha1" "${CEF_SHA1_PATH}" FALSE)
      _cefweaver_read_sha1("${CEF_SHA1_PATH}.part" _expected)
      if(NOT _expected)
        file(REMOVE "${CEF_SHA1_PATH}.part")
        message(FATAL_ERROR "${CEF_DOWNLOAD_URL_ESCAPED}.sha1 does not hold a SHA1 hash (40 hex digits).")
      endif()

      # Download the binary distribution and verify the hash. The file gets its name only if the hash matches.
      message(STATUS "Downloading ${CEF_DOWNLOAD_PATH}...")
      _cefweaver_fetch("${CEF_DOWNLOAD_URL_ESCAPED}" "${CEF_DOWNLOAD_PATH}" TRUE)
      _cefweaver_sha1("${CEF_DOWNLOAD_PATH}.part" _actual)
      if(NOT _actual STREQUAL _expected)
        file(REMOVE "${CEF_DOWNLOAD_PATH}.part" "${CEF_SHA1_PATH}.part")
        message(FATAL_ERROR "SHA1 mismatch for ${CEF_DOWNLOAD_URL_ESCAPED}\n"
                            "  expected: ${_expected}\n  actual:   ${_actual}\n"
                            "The downloaded file was deleted.")
      endif()
      file(RENAME "${CEF_DOWNLOAD_PATH}.part" "${CEF_DOWNLOAD_PATH}")
      file(RENAME "${CEF_SHA1_PATH}.part" "${CEF_SHA1_PATH}")
    endif()

    # Extract the binary distribution into a directory of its own and move it into place as a whole.
    message(STATUS "Extracting ${CEF_DOWNLOAD_PATH}...")
    set(_unpack "${CEF_DOWNLOAD_DIR}/.unpack-${CEF_DISTRIBUTION}")
    file(REMOVE_RECURSE "${_unpack}")
    execute_process(
      COMMAND "${_python}" "${_CEFWEAVER_DOWNLOAD_CEF_DIR}/../tools/safe_extract.py"
              "${CEF_DOWNLOAD_PATH}" "${_unpack}"
      RESULT_VARIABLE _result
      )
    if(NOT _result EQUAL 0)
      file(REMOVE_RECURSE "${_unpack}")
      message(FATAL_ERROR "Could not unpack ${CEF_DOWNLOAD_PATH} (tools/safe_extract.py exited with ${_result}).")
    endif()
    if(NOT IS_DIRECTORY "${_unpack}/${CEF_DISTRIBUTION}")
      file(REMOVE_RECURSE "${_unpack}")
      message(FATAL_ERROR "${CEF_DOWNLOAD_PATH} does not contain the directory ${CEF_DISTRIBUTION}.")
    endif()
    file(RENAME "${_unpack}/${CEF_DISTRIBUTION}" "${CEF_ROOT}")
    file(REMOVE_RECURSE "${_unpack}")
  endif()
endfunction()
