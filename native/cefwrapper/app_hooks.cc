#include "app_hooks.h"

#include <mutex>
#include <sstream>

const char kCustomSchemesSwitch[] = "cefweaver-custom-schemes";

namespace {
std::mutex g_mutex;
std::vector<std::pair<std::string, int>> g_schemes;
}  // namespace

AppHooks& GetAppHooks() {
  static AppHooks hooks;
  return hooks;
}

bool SchemeRegistrarProxy::Add(const std::string& name, int options) {
  if (!registrar_) {
    return false;
  }
  const bool done = registrar_->AddCustomScheme(name, options);
  if (done) {
    std::lock_guard<std::mutex> lock(g_mutex);
    g_schemes.emplace_back(name, options);
  }
  return done;
}

std::string CustomSchemesSwitchValue() {
  std::lock_guard<std::mutex> lock(g_mutex);
  std::ostringstream out;
  for (const auto& entry : g_schemes) {
    out << (out.tellp() > 0 ? ";" : "") << entry.first << ":" << entry.second;
  }
  return out.str();
}

void RegisterCustomSchemesFrom(const std::string& value, CefRawPtr<CefSchemeRegistrar> registrar) {
  std::istringstream in(value);
  std::string item;
  while (std::getline(in, item, ';')) {
    const size_t colon = item.rfind(':');
    if (colon == std::string::npos) {
      continue;
    }
    registrar->AddCustomScheme(item.substr(0, colon), std::stoi(item.substr(colon + 1)));
  }
}
