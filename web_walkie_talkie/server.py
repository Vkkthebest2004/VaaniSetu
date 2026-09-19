#!/usr/bin/env python3
"""
Backward Compatibility Entrypoint for VaaniSetu Walkie-Talkie Web Server.
Delegates to the canonical backend server at backend/server/server.py.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Re-export everything from backend.server.server for full backward compatibility
from backend.server.server import *

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"[TACTICAL-SERVER] Starting VaaniSetu Transceiver via delegation wrapper on http://localhost:{port}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
