"""Export FastAPI OpenAPI schema to openapi.json (and openapi.yaml if pyyaml is available).

Usage (from repo root, with backend deps installed):
    python scripts/export_openapi.py

Writes openapi.json and openapi.yaml next to the repo root.
Does NOT connect to the database — only imports the FastAPI app and calls .openapi().
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("POSTGRES_USER", "emplai")
os.environ.setdefault("POSTGRES_PASSWORD", "placeholder")
os.environ.setdefault("POSTGRES_DB", "emplai")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("JWT_SECRET", "placeholder-jwt-secret-for-spec-export-only")
os.environ.setdefault("REGISTRATION_ENABLED", "true")


def main() -> int:
    from app.main import app  # noqa: PLC0415 — import after env is set

    schema = app.openapi()

    json_path = REPO_ROOT / "openapi.json"
    json_path.write_text(json.dumps(schema, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {json_path.relative_to(REPO_ROOT)} ({json_path.stat().st_size} bytes)")

    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        print("pyyaml not installed — skipping openapi.yaml")
        return 0

    yaml_path = REPO_ROOT / "openapi.yaml"
    yaml_path.write_text(
        yaml.safe_dump(schema, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    print(f"wrote {yaml_path.relative_to(REPO_ROOT)} ({yaml_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
