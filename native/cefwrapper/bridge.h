#ifndef CEF_WRAPPER_BRIDGE_H_
#define CEF_WRAPPER_BRIDGE_H_

// The JavaScript side of cefweaver.JavascriptBridge (cefweaver/bridge.py): the names that
// Python exposes are passed to the renderer processes as a switch, and the renderer defines
// `window.<name>` in every context with a fixed piece of JavaScript. The calls go through the
// message router (window.cefQuery) as JSON; the renderer runs no Python.

#include <string>

// A JSON array of the exposed names, e.g. ["add","describe"] (empty: nothing is exposed).
inline std::string& BridgeNames() {
  static std::string names;
  return names;
}

inline const char kBridgeSwitch[] = "cefweaver-bridge";
// The renderer sends its events (JavaScript errors, the focused node, contexts) to the browser process as
// process messages named kRendererEventMessage; the browser process turns that on with this switch.
inline const char kRendererEventsSwitch[] = "cefweaver-renderer-events";
inline const char kRendererEventMessage[] = "cefweaver-renderer-event";

// A function expression, called with (names, queryFunctionName).
inline const char kBridgeShim[] = R"JS((function (names, query) {
  if (window.__cefweaverBridge) { return; }
  var callbacks = {}, next = 1;
  function ask(payload) {
    return new Promise(function (resolve, reject) {
      window[query]({
        request: JSON.stringify(payload),
        onSuccess: function (answer) { resolve(answer === "" ? undefined : JSON.parse(answer)); },
        onFailure: function (code, message) { reject(new Error(message)); }
      });
    });
  }
  function encode(value) {
    if (typeof value === "function") {
      var id = String(next++);
      callbacks[id] = value;
      return {"__cb": id};
    }
    return value === undefined ? null : value;
  }
  names.forEach(function (name) {
    window[name] = function () {
      var args = Array.prototype.map.call(arguments, encode);
      return ask({cefweaver: 1, t: "call", n: name, a: args});
    };
  });
  window.__cefweaverBridge = {
    invoke: function (id, args) { var f = callbacks[id]; if (f) { f.apply(null, args); } },
    release: function (id) { delete callbacks[id]; },
    call: function (path, args) {
      var parts = path.split("."), target = window, i;
      for (i = 0; i < parts.length - 1; i++) { target = target[parts[i]]; }
      return target[parts[parts.length - 1]].apply(target, args);
    },
    evaluate: function (id, source) {
      Promise.resolve().then(function () { return (0, eval)(source); }).then(
        function (value) { return ask({cefweaver: 1, t: "result", id: id, ok: true, v: value === undefined ? null : value}); },
        function (error) { return ask({cefweaver: 1, t: "result", id: id, ok: false, e: (error && error.name ? error.name + ": " + error.message : String(error))}); }
      ).catch(function () {});
    }
  };
}))JS";

#endif  // CEF_WRAPPER_BRIDGE_H_
