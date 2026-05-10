#!/usr/bin/env python3
"""Beep.AI.Researcher -- Entry point. Config via config_manager."""
import os
import sys
import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Graceful shutdown (mirrors AI.Server behaviour) ───────────────────────────
def _signal_handler(signum, frame):
    print("\n[Beep.AI.Researcher] Shutting down gracefully...")
    sys.exit(0)

signal.signal(signal.SIGINT, _signal_handler)
if sys.platform != 'win32':
    signal.signal(signal.SIGTERM, _signal_handler)
# ─────────────────────────────────────────────────────────────────────────────

# ── Windows / Python 3.13 platform.machine() deadlock fix ────────────────────
# SQLAlchemy's Cython extension calls platform.machine() at import time.
# On Windows + Python ≥ 3.13, platform.machine() calls subprocess.check_output
# ('ver', shell=True) which hangs inside a Werkzeug reloader subprocess.
# Replace it with a direct env-var lookup that never spawns child processes.
if os.name == 'nt':
    import platform as _platform
    _platform.machine = lambda: os.environ.get('PROCESSOR_ARCHITECTURE', 'AMD64')
# ─────────────────────────────────────────────────────────────────────────────

from startup_dependency_bootstrap import bootstrap_requirements


def auto_update_database(app):
    """Automatically create/update database tables on startup."""

    print("\n" + "=" * 60)
    print("Database Auto-Update")
    print("=" * 60)
    try:
        report = run_startup_database_updates(app)
        print("[OK] Database tables updated successfully")
        print(f"[INFO] Default plan tiers seeded: {report.plan_tiers_seeded}")
    except Exception as e:
        print(f"[ERROR] Database update failed: {e}")
        print("   Please check your database configuration.")
    print("=" * 60 + "\n")


def auto_update_requirements():
    """Verify requirements.txt and optionally install missing packages."""

    if os.getenv('TESTING', '').lower() in ('1', 'true', 'yes'):
        return

    print("\n" + "=" * 60)
    print("Requirements Auto-Update")
    print("=" * 60)
    report = bootstrap_requirements()
    print(f"[INFO] Requirements checked: {report.checked}")
    if report.installed:
        print(f"[OK] Installed: {', '.join(report.installed)}")
    if report.missing and not report.installed:
        print(f"[WARN] Missing packages: {', '.join(report.missing)}")
        print("       Set AUTO_INSTALL_REQUIREMENTS_ON_STARTUP=1 to install automatically.")
    if report.failed:
        print(f"[ERROR] Failed installs: {', '.join(item.requirement for item in report.failed)}")
    if not report.ok:
        print("[ERROR] Startup dependencies are incomplete. Fix requirements.txt/install errors and restart.")
        sys.exit(1)
    print("=" * 60 + "\n")

auto_update_requirements()

from app import create_app  # noqa: E402
from app.config_manager import config_manager  # noqa: E402
from app.services.startup.database_bootstrap import run_startup_database_updates  # noqa: E402

app = create_app()

# Auto-update database on startup
auto_update_database(app)

if __name__ == '__main__':
    host = config_manager.get_with_env('server_host', 'HOST', '127.0.0.1')
    port = int(config_manager.get_with_env('server_port', 'PORT', 5005))
    # Override port from CLI: run.py 5006 or run.py --port 5006
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == '--port' and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])
            break
        if arg.isdigit():
            port = int(arg)
            break
    
    print(f"\n>> Starting Beep.AI.Researcher on http://{host}:{port}")
    print("Press Ctrl+C to stop\n")

    # use_reloader=False: Flask's stat-reloader spawns a subprocess that picks
    # up the system Python 3.13 instead of the venv, causing SQLAlchemy's Cython
    # extension to crash in platform.machine() → subprocess.check_output('ver').
    # Debug mode is still active (error pages, interactive debugger, etc).
    app.run(host=host, port=port, debug=True, use_reloader=False)

