"""Does a real video play? A manual check (it needs the network and a YouTube page), not part of the test suite.

    xvfb-run -a python tests/playback_check.py windowed                      # the default CEF app (a window of its own)
    xvfb-run -a python tests/playback_check.py gtk3 [--venv .venv] [GDK_BACKEND=x11 ...]   # an example's quickstart.py (OSR)

For a toolkit it runs ``examples/<toolkit>/quickstart.py`` unchanged in the environment of that example, with a probe
attached to ``Session.start``: every 3 seconds the page tells (through an exposed function, so that a strict CSP
does not matter) the state of its ``<video>``, and the picture of the view is compared with the earlier ones. The
sound goes to the fake audio sink of Chromium (``disable-audio-output``): nobody hears it. Then the window is closed
like the close button does and the program has to end with the code 0.

It passes if the time of the video goes on about as fast as the clock, the video is not paused, it has data
(``readyState`` 3 or 4), has no error, and (OSR) the picture of the view changes. The page is ``--url``.
"""

import argparse
import atexit
import json
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://www.youtube.com/watch?v=Ds-jo86CZRg&list=RDl1n6eqfNl4Q&index=3"
STATE = """(function () { var v = document.querySelector('video'), p = document.querySelector('.html5-video-player');
 return {t: v ? +v.currentTime.toFixed(2) : null, paused: v ? v.paused : null, ready: v ? v.readyState : null,
         w: v ? v.videoWidth : null, h: v ? v.videoHeight : null, err: v && v.error ? v.error.code : null,
         ad: p ? p.classList.contains('ad-showing') : null, title: document.title.slice(0, 40)}; })()"""
SWITCHES = [("disable-audio-output", ""), ("autoplay-policy", "no-user-gesture-required"), ("ozone-platform", "x11")]


# -- inside: the program that plays ------------------------------------------------------------------------

def inside_toolkit(quickstart, url, seconds, audio, loud=False, no_gpu=False, switches=(), log_file=None, native_audio=False):
    """Run the quickstart of an example with the probe; print the states and PROBE DONE. With ``audio`` the view
    plays the sound through a sink (``audio="auto"``: the sink of the toolkit, else pygame) at volume 0."""
    import cefweaver
    from cefweaver import ui
    probes, views = [], []
    init, start = ui.Session.__init__, ui.Session.start
    if audio:
        view_init = ui.BrowserView.__init__

        def browser_view_init(self, adapter, *args, **options):
            options["audio"] = "auto"
            view_init(self, adapter, *args, **options)
            if self.audio_sink is not None and not loud:
                self.audio_sink.volume = 0.0                    # the whole path runs, nobody hears it
            views.append(self)
            sink = self.audio_sink
            if sink is not None:
                peak, write = [0.0], sink.write

                def measured_write(samples, frames):
                    import array
                    data = array.array("f", samples)
                    peak[0] = max(peak[0], max(map(abs, data[::7])) if len(data) else 0.0)
                    write(samples, frames)
                sink.write, sink.peak = measured_write, peak
        ui.BrowserView.__init__ = browser_view_init

    given = list(switches)                                  # session_init has a parameter of the same name

    def session_init(self, adapter, switches=(), cache_path=None):
        extra = ([("disable-gpu", "")] if no_gpu else []) + given
        base = [s for s in SWITCHES if not (native_audio and s[0] == "disable-audio-output")]
        init(self, adapter, list(switches) + base + extra, cache_path)
        if log_file:
            self.app.settings.log_severity = cefweaver.types.LogSeverity.VERBOSE
            self.app.settings.log_file = log_file
            self.app.add_command_line_switch("v", "1")
        self.bridge.expose("__probe", probes.append)

    def session_start(self, target, url_="about:blank"):
        start(self, target, url_)
        view = ui.session.view_of(target)
        seen, begun = set(), []

        def tick():
            now = time.monotonic()
            begun.append(now) if not begun else None
            elapsed = now - begun[0]
            if view.store.pixels is not None:
                seen.add(zlib.crc32(bytes(view.store.pixels)))
            while probes:
                print("STATE %s" % json.dumps(dict(probes.pop(), clock=round(elapsed, 2), pictures=len(seen)),
                                              ensure_ascii=False), flush=True)
            sink = view.audio_sink
            if audio and sink is not None and hasattr(sink, "stats"):
                print("AUDIO %s" % json.dumps(dict(sink.stats(), sink=type(sink).__name__, clock=round(elapsed, 2),
                                                   peak=round(getattr(sink, "peak", [0])[0], 4))), flush=True)
            if view.browser is not None:
                view.browser.get_main_frame().execute_java_script("if (window.__probe) window.__probe(%s);" % STATE, "", 0)
            if elapsed >= seconds:
                print("PROBE DONE", flush=True)
                return
            self.adapter.call_later(3.0, tick)
        self.adapter.call_later(3.0, tick)

    ui.Session.__init__, ui.Session.start = session_init, session_start
    sys.argv = ["quickstart.py", url]
    runpy.run_path(quickstart, run_name="__main__")


def inside_windowed(url, seconds, switches=()):
    """The default CEF app (windowed): the same states, read through the legacy binding."""
    import cefweaver
    app = cefweaver.CefApp()
    app.set_cache_path(tempfile.mkdtemp(prefix="cefweaver-playback-"))
    for name, value in SWITCHES + list(switches):
        app.add_command_line_switch(name, value)
    states = []
    app.add_javascript_binding("report", lambda *a: states.append(a[0]))
    app.initialize(url)
    begun, last = time.monotonic(), 0.0
    while time.monotonic() - begun < seconds:
        app.do_message_loop_work()
        time.sleep(0.005)
        if time.monotonic() - last > 3.0 and app.is_ready_to_execute_javascript:
            last = time.monotonic()
            app.execute_javascript("report(JSON.stringify(%s))" % STATE)
            until = time.monotonic() + 0.4
            while time.monotonic() < until:
                app.do_message_loop_work()
                time.sleep(0.005)
            while states:
                print("STATE %s" % json.dumps(dict(json.loads(states.pop()), clock=round(time.monotonic() - begun, 2), pictures=0),
                                              ensure_ascii=False), flush=True)
    print("PROBE DONE", flush=True)
    app.shutdown()


# -- outside: starts it, reads it, judges it ------------------------------------------------------------

def judge(states, windowed):
    """The reasons why it did not play (an empty list: it did)."""
    reasons = []
    if len(states) < 3:
        return ["fewer than 3 states came (%d)" % len(states)]
    first, last = states[0], states[-1]
    clock = last["clock"] - first["clock"]
    video = (last["t"] or 0) - (first["t"] or 0)
    if clock <= 0 or video < 0.8 * clock:
        reasons.append("the video went %.1f s in %.1f s of the clock" % (video, clock))
    if any(s["paused"] for s in states[1:]):
        reasons.append("it was paused")
    if (last["ready"] or 0) < 3:
        reasons.append("no data (readyState %s)" % last["ready"])
    if any(s["err"] for s in states):
        reasons.append("the video had an error (%s)" % [s["err"] for s in states if s["err"]][0])
    if not windowed and last["pictures"] < 3:
        reasons.append("the picture of the view hardly changed (%d different)" % last["pictures"])
    return reasons


def judge_sound(sounds):
    """The reasons why the sound did not reach the sink as it should (an empty list: it did). A sound card plays 44100 or
    48000 frames a second; the sink should have been given about that many."""
    if len(sounds) < 3:
        return ["the sink told fewer than 3 times (%d): is there one?" % len(sounds)]
    first, last = sounds[0], sounds[-1]
    seconds = last["clock"] - first["clock"]
    frames = last["written"] - first["written"]
    reasons = []
    if frames < 0.7 * 44100 * seconds:
        reasons.append("the sink was given %d frames in %.1f s (at least %d expected)" % (frames, seconds, 0.7 * 44100 * seconds))
    if last["consumed"] < 0.8 * last["written"]:
        reasons.append("the device took only %d of %d frames" % (last["consumed"], last["written"]))
    if last["underruns"] > 8:
        reasons.append("the sound broke up %d times" % last["underruns"])
    return reasons


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("target", help="windowed, or an example: gtk3, qt, tk, sdl2, wx, kivy")
    parser.add_argument("pins", nargs="*", help="NAME=VALUE environment (GDK_BACKEND=x11, QT_QPA_PLATFORM=xcb, ...)")
    parser.add_argument("--venv", default=".venv", help="the uv environment of the example")
    parser.add_argument("--seconds", type=float, default=24.0)
    parser.add_argument("--url", default=URL)
    parser.add_argument("--audio", action="store_true",
                        help="play the sound through the sink of the toolkit (else pygame) at volume 0 and check it")
    parser.add_argument("--loud", action="store_true", help="with --audio: leave the volume as it is, so that it is heard")
    parser.add_argument("--no-gpu", action="store_true", help="add disable-gpu (a real screen: see the notes on the GPU process)")
    parser.add_argument("--switch", action="append", default=[], metavar="NAME[=VALUE]", help="a Chromium switch (repeatable)")
    parser.add_argument("--stderr-file", metavar="PATH", help="write all that the program printed to stderr (for a log: --switch enable-logging=stderr --switch v=1)")
    parser.add_argument("--log-file", metavar="PATH", help="the verbose log of Chromium (all processes) goes to this file")
    parser.add_argument("--native-audio", action="store_true",
                        help="do not give disable-audio-output: Chromium plays the sound itself too (it can be heard)")
    parser.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        if args.target == "windowed":
            inside_windowed(args.url, args.seconds, [tuple(w.split('=', 1)) if '=' in w else (w, '') for w in args.switch])
        else:
            inside_toolkit(os.path.join(ROOT, "examples", args.target, "quickstart.py"), args.url, args.seconds, args.audio, args.loud, args.no_gpu,
                           [tuple(w.split('=', 1)) if '=' in w else (w, '') for w in args.switch], args.log_file, args.native_audio)
        return 0

    windowed = args.target == "windowed"
    python = sys.executable if windowed else os.path.join(ROOT, "examples", args.target, args.venv, "bin", "python")
    env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "XDG_SESSION_TYPE")}
    env.update(pin.split("=", 1) for pin in args.pins)
    scratch = tempfile.mkdtemp(prefix="cefweaver-playback-")        # CEF makes its cache in the working directory
    atexit.register(shutil.rmtree, scratch, True)                    # the cache of a run is big (tens of MB)
    process = subprocess.Popen([python, os.path.abspath(__file__), args.target, "--inside", "--seconds", str(args.seconds),
                                "--url", args.url] + (["--audio"] if args.audio else []) + (["--loud"] if args.loud else []) + (["--no-gpu"] if args.no_gpu else []) + [a for w in args.switch for a in ("--switch", w)] + (["--log-file", args.log_file] if args.log_file else []) + (["--native-audio"] if args.native_audio else []), cwd=scratch, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lines, errors = [], []
    threading.Thread(target=lambda: [lines.append(l) for l in iter(process.stdout.readline, "")], daemon=True).start()
    threading.Thread(target=lambda: [errors.append(l) for l in iter(process.stderr.readline, "")], daemon=True).start()
    end = time.time() + args.seconds + 90
    while not any("PROBE DONE" in l for l in lines) and process.poll() is None and time.time() < end:
        time.sleep(0.3)
    states = [json.loads(l[len("STATE "):]) for l in lines if l.startswith("STATE ")]
    sounds = [json.loads(l[len("AUDIO "):]) for l in lines if l.startswith("AUDIO ")]
    for s in states:
        print("  T+%5.1fs video %5.1fs paused=%-5s ready=%s %sx%s err=%s ad=%s pictures=%d" % (
            s["clock"], s["t"] or 0, s["paused"], s["ready"], s["w"], s["h"], s["err"], s["ad"], s["pictures"]))
    if states:
        print("  page:", states[-1]["title"])
    if args.audio:
        print("  sound:", ("%s %s" % (sounds[-1]["sink"], {k: v for k, v in sounds[-1].items() if k not in ("sink", "clock")})) if sounds else "no sink")
    code = None
    if process.poll() is None:
        if windowed:
            code = process.wait(timeout=60)                           # it ends by itself
        else:
            sys.path.insert(0, os.path.join(ROOT, "tests"))
            import test_ui
            case = test_ui.Quickstarts("test_each_quickstart_shows_a_page_and_ends_cleanly_when_its_window_is_closed")
            test_ui.send_delete_window(case.window_of(process.pid))      # like the close button
            try:
                code = process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.kill()
                code = "did not end after the window was closed"
    else:
        code = process.returncode
    if args.stderr_file:
        with open(args.stderr_file, "w", encoding="utf-8") as f:
            f.write("".join(errors))
    reasons = judge(states, windowed)
    if args.audio:
        reasons += judge_sound(sounds)
    if code != 0:
        reasons.append("ended with %s" % (code,))
    if any("stack smashing" in l for l in errors):
        reasons.append("stack smashing")
    if reasons:
        print("PLAYBACK FAILED (%s): %s" % (args.target, "; ".join(reasons)))
        print("".join(errors)[-1200:])
        return 1
    print("PLAYBACK OK (%s): the video went %.1f s in %.1f s, the program ended with 0" % (
        args.target, (states[-1]["t"] or 0) - (states[0]["t"] or 0), states[-1]["clock"] - states[0]["clock"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
