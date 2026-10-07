"""Скрипт для экспорта актуальной OpenAPI спецификации в docs/."""

import os
import sys
from pathlib import Path

import yaml  # type: ignore[import-untyped]

# Use test container defaults if not explicitly set
os.environ.setdefault("POSTGRES__HOST", "localhost")
os.environ.setdefault("POSTGRES__PORT", "5433")
os.environ.setdefault("POSTGRES__DB", "nosql_store_test")
os.environ.setdefault("RIAK__BASE_URL", "http://localhost:8099")

backend_dir = Path(__file__).resolve().parent.parent
src_dir = backend_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from infrastructure.persistence.postgres.connection import (
    close_postgres_pool,
)
from infrastructure.persistence.riak.client import close_riak_client
from main import app


def export_openapi() -> None:
    try:
        schema = app.openapi()

        # Export to backend/docs/
        backend_docs_dir = backend_dir / "docs"
        backend_docs_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = backend_docs_dir / "openapi.yaml"
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(schema, f, sort_keys=False, allow_unicode=True)

        # Also export to root docs/ if present
        root_docs_dir = backend_dir.parent / "docs"
        if root_docs_dir.exists():
            root_yaml_path = root_docs_dir / "openapi.yaml"
            with open(root_yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(schema, f, sort_keys=False, allow_unicode=True)

        print(f"OpenAPI spec successfully exported to:\n  - {yaml_path}")
        if root_docs_dir.exists():
            print(f"  - {root_docs_dir / 'openapi.yaml'}")
    finally:
        close_postgres_pool()
        close_riak_client()


if __name__ == "__main__":
    export_openapi()
