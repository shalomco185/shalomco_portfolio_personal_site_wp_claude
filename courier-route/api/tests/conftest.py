import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATA_DIR", _tmp)
os.environ.setdefault("APP_PASSWORD", "test-pass")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("OSRM_URL", "http://127.0.0.1:9")  # לא זמין: בודק את מצב הגיבוי
