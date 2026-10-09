#!/bin/sh
# Builds ./CefSwiftUI against the Python of PYROOT (default: the one that uv made for the venv).
set -e
cd "$(dirname "$0")"
PYROOT="${PYROOT:?set PYROOT to the Python the cefweaver wheel is installed for}"
INC=$(ls -d "$PYROOT"/include/python3.*)
VER=$(basename "$INC" | sed 's/python//')
swiftc -O main.swift -import-objc-header Bridge.h -Xcc -I"$INC" \
  -L"$PYROOT/lib" -lpython$VER -Xlinker -rpath -Xlinker "$PYROOT/lib" -o CefSwiftUI
