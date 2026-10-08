"""The demo page and the Python functions it calls, the same in every toolkit example.

``install(runtime_bridge, remember)`` exposes ``add`` and ``appReady`` (cefweaver.JavascriptBridge);
``remember(info)`` is called with what the page tells Python when it is ready.
"""

import platform

DEMO_URL = "http://demo.test/"
DEMO_PAGE = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>cefweaver demo</title>
<style>
 body { font: 16px/1.4 sans-serif; margin: 16px; background: #fafafa; }
 #log { white-space: pre; background: #eef; padding: 8px; min-height: 3em; }
 .tall { height: 1400px; background: linear-gradient(#fff, #cde); margin-top: 16px; padding: 8px; }
</style></head><body>
<h1>cefweaver in a GUI toolkit</h1>
<p><input id="text" placeholder="type here (한글 입력도)" size="30">
 <button id="add" onclick="calc()">2 + 3 in Python</button>
 <select id="fruit"><option>apple</option><option>banana</option><option>cherry</option></select>
 <a id="link" href="http://demo.test/other">a link</a></p>
<div id="log">waiting for Python...</div>
<p id="para">Selectable paragraph text</p>
<p><textarea id="area" rows="2" cols="28" placeholder="paste here"></textarea>
 <span id="src" draggable="true" style="display:inline-block;padding:6px;background:#fe9;border:1px solid #cb5">drag me</span>
 <span id="zone" style="display:inline-block;padding:6px 20px;background:#9fe;border:1px solid #5cb">drop zone</span></p>
<div class="tall">scroll me (device pixel ratio: <b id="dpr"></b>)</div>
<script>
 function log(text) { document.getElementById("log").textContent += text + "\\n"; }
 function calc() { add(2, 3).then(function (sum) { log("add(2, 3) = " + sum); }); }
 document.getElementById("dpr").textContent = window.devicePixelRatio;
 appReady({dpr: window.devicePixelRatio, width: innerWidth, agent: navigator.userAgent})
   .then(function (answer) { document.getElementById("log").textContent = answer + "\\n"; });
 window.fromPython = function (message) { log("from Python: " + message); return message.length; };
 window.drops = [];
 document.getElementById("src").addEventListener("dragstart", function (e) { e.dataTransfer.setData("text/plain", "dragged-from-page"); });
 var zone = document.getElementById("zone");
 // a drop zone cancels dragenter as well as dragover (the HTML drag and drop rules)
 ["dragenter", "dragover"].forEach(function (name) { zone.addEventListener(name, function (e) { e.preventDefault(); }); });
 zone.addEventListener("drop", function (e) {
   e.preventDefault();
   window.drops.push({text: e.dataTransfer.getData("text/plain"), files: Array.prototype.map.call(e.dataTransfer.files, function (f) { return f.name; })});
 });
 window.compositions = [];
 ["compositionstart", "compositionupdate", "compositionend"].forEach(function (name) {
   document.getElementById("text").addEventListener(name, function (e) { window.compositions.push(name + ":" + e.data); });
 });
</script></body></html>"""


def install(bridge, remember):
    def add(a, b):
        return a + b

    def app_ready(info):
        remember(info)
        return "Python %s on %s: the page is %d px wide at %sx" % (
            platform.python_version(), platform.system(), info["width"], info["dpr"])

    bridge.expose("add", add)
    bridge.expose("appReady", app_ready)
