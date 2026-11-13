import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE = ROOT / "code"
RUNTIME = CODE / "runtime"


def load_env():
    path = ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep:
                os.environ.setdefault(key.strip(), value.strip().strip("\"").strip("'"))


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)

