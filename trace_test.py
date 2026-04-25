import os
os.environ["TESTING"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///pytest_test.db"
os.environ["SKIP_SEED_ROLES"] = "1"

import importlib
cm_mod = importlib.import_module("app.config_manager")
CM = cm_mod.ConfigManager

original_load = CM.load
original_init = CM.__init__

def traced_load(self):
    import traceback
    print("=== LOAD called ===")
    traceback.print_stack(limit=8)
    original_load(self)
    print("=== features after load:", list(self._config.get("features", {}).keys()))

def traced_init(self):
    print("=== INIT called, _initialized =", getattr(self, "_initialized", "N/A"))
    import traceback
    traceback.print_stack(limit=6)
    original_init(self)
    print("=== features after init:", list(self._config.get("features", {}).keys()))

CM.load = traced_load
CM.__init__ = traced_init

print("--- Calling ConfigManager() ---")
inst = CM()
print("FINAL features:", list(inst._config.get("features", {}).keys()))
