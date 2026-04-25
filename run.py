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

from app import create_app
from app.config_manager import config_manager

def auto_update_database():
    """Automatically create/update database tables on startup"""
    from app.database import db
    
    print("\n" + "="*60)
    print("Database Auto-Update")
    print("="*60)
    
    with app.app_context():
        try:
            # Import all models to ensure they're registered
            from app.models.core import User, Role, AuditLog
            
            # Try importing AI models (may not exist yet)
            try:
                from app.models.researcher.ai_templates import (
                    AITemplate, AIWorkflowExecution, AIWorkbook, WorkbookDocument
                )
            except ImportError:
                print("[WARN] AI template models not found (skipping)")
            
            try:
                from app.models.researcher.transcriptions import (
                    AudioTranscription, TranscriptionSegment, TranscriptionAnnotation
                )
            except ImportError:
                print("[WARN] Transcription models not found (skipping)")
            
            try:
                from app.models.researcher.user_preferences import UserPreferences
            except ImportError:
                print("[WARN] User preferences model not found (skipping)")
            
            # Create all tables
            print("Creating/updating database tables...")
            db.create_all()
            print("[OK] Database tables updated successfully")
            
            # Check if AI templates need seeding
            try:
                from app.models.researcher.ai_templates import AITemplate
                template_count = AITemplate.query.filter_by(is_system=True).count()
                if template_count == 0:
                    print("\nSeeding AI templates...")
                    try:
                        # Import and run seed script
                        import subprocess
                        result = subprocess.run(
                            [sys.executable, 'seed_ai_templates.py'],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            print("[OK] AI templates seeded successfully")
                        else:
                            print(f"[WARN] Seed script warning: {result.stderr}")
                    except Exception as e:
                        print(f"[WARN] Could not seed templates: {e}")
                        print("   Run 'python seed_ai_templates.py' manually")
                else:
                    print(f"[INFO] Found {template_count} existing AI templates")
            except ImportError:
                print("[INFO] AI templates not available yet")
            
        except Exception as e:
            print(f"[ERROR] Database update failed: {e}")
            print("   Please check your database configuration.")
    
    print("="*60 + "\n")

app = create_app()

# Auto-update database on startup
auto_update_database()

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

