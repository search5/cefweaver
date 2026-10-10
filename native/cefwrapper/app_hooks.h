#ifndef CEF_WRAPPER_APP_HOOKS_H_
#define CEF_WRAPPER_APP_HOOKS_H_

// The hooks of the application into Python, java-cef's CefAppHandler: the command line of the
// browser process, the custom schemes, the initialized context and a second start of the
// application. The functions are in _cefweaver.pyx (they take the GIL and never raise).

#include <string>
#include <utility>
#include <vector>

#include "include/cef_app.h"
#include "include/cef_command_line.h"

// The registrar CEF gives to OnRegisterCustomSchemes is valid during that call only. The schemes
// are also remembered: the other processes (renderers) need to register the same ones, and CEF
// does not tell them, so they get them as a switch (see CustomSchemesSwitchValue()).
class SchemeRegistrarProxy {
 public:
  explicit SchemeRegistrarProxy(CefRawPtr<CefSchemeRegistrar> registrar) : registrar_(registrar) {}
  bool Add(const std::string& name, int options);

 private:
  CefRawPtr<CefSchemeRegistrar> registrar_;
};

// The registrar CEF gives to OnRegisterCustomPreferences: valid during that call only.
class PreferenceRegistrarProxy {
 public:
  explicit PreferenceRegistrarProxy(CefRawPtr<CefPreferenceRegistrar> registrar) : registrar_(registrar) {}
  bool Add(const std::string& name, CefRefPtr<CefValue> default_value);

 private:
  CefRawPtr<CefPreferenceRegistrar> registrar_;
};

typedef void (*app_command_line_ptr)(void* py, CefRefPtr<CefCommandLine> command_line);
typedef void (*app_schemes_ptr)(void* py, SchemeRegistrarProxy* registrar);
typedef void (*app_child_launch_ptr)(void* py, CefRefPtr<CefCommandLine> command_line);
typedef void (*app_preferences_ptr)(void* py, int type, PreferenceRegistrarProxy* registrar);
typedef void (*app_context_ptr)(void* py);
typedef void (*app_schedule_ptr)(void* py, long long delay_ms);
typedef bool (*app_relaunch_ptr)(void* py, CefRefPtr<CefCommandLine> command_line,
                                 const std::string& current_directory);

struct AppHooks {
  void* py = nullptr;
  app_command_line_ptr command_line = nullptr;
  app_schemes_ptr schemes = nullptr;
  app_context_ptr context = nullptr;
  app_relaunch_ptr relaunch = nullptr;
  app_schedule_ptr schedule = nullptr;  // any thread of the browser process
  app_child_launch_ptr child_launch = nullptr;  // the command line of a child process, before it starts
  app_preferences_ptr preferences = nullptr;    // the custom preferences (global or of a request context)
};

AppHooks& GetAppHooks();

// "name:options;name:options" of the schemes the browser process registered, for the child
// processes' command line, and the registration of such a list in a child process.
extern const char kCustomSchemesSwitch[];
std::string CustomSchemesSwitchValue();
void RegisterCustomSchemesFrom(const std::string& value, CefRawPtr<CefSchemeRegistrar> registrar);

#endif  // CEF_WRAPPER_APP_HOOKS_H_
