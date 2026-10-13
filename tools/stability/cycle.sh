#!/bin/bash
# Start CEF, call Python from a page and shut down, N times (default 30), each in a new process, and report
# failures and leftover cefsubprocess processes. Run it where no other CEF program runs.
# Usage: tools/stability/cycle.sh [N]   (needs xvfb-run and the cefweaver wheel installed)
err=$(mktemp); fail=0; total=${1:-30}
for i in $(seq 1 $total); do
  out=$(env -u WAYLAND_DISPLAY PYTHONPATH="$(dirname "$0")" timeout 60 xvfb-run -a python -P "$(dirname "$0")/cycle.py" 2>"$err"); rc=$?
  if [ $rc -ne 0 ] || [ "$out" != "ok" ] || grep -qi "stack smashing\|segmentation\|Traceback\|FATAL" "$err"; then fail=$((fail+1)); echo "run $i rc=$rc out=$out"; head -5 "$err"; fi
  left=$(pgrep -xc cefsubprocess || true)
  [ "$left" != "0" ] && echo "run $i leftover cefsubprocess=$left"
done
echo "cycles=$total failures=$fail"
rm -f "$err"
