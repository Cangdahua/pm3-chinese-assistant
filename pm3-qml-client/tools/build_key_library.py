#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = PROJECT_ROOT / "compat-clients/iceman-ice_v3.1.0/client/default_keys.dic"
DEFAULT_OUTPUT = PROJECT_ROOT / "pm3-qml-client/data/key_library.sqlite"
SOURCE_LABEL = "compat-clients/iceman-ice_v3.1.0/client/default_keys.dic"
SOURCE_NOTE = "locked submodule deterministic seed"
SEEDED_AT = "deterministic-seed"


def extract_keys(text: str) -> list[str]:
    keys: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line
        for marker in ("#", "//", ";"):
            if marker in line:
                line = line.split(marker, 1)[0]
        line = line.strip()
        if not line:
            continue

        matches = re.findall(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])", line)
        if not matches:
            compact = "".join(ch for ch in line.upper() if ch in "0123456789ABCDEF")
            matches = [compact] if len(compact) == 12 else []
        keys.update(match.upper() for match in matches)
    return sorted(keys)


def build_database(source: Path, output: Path) -> tuple[int, str]:
    keys = extract_keys(source.read_text(encoding="utf-8", errors="strict"))
    if not keys:
        raise ValueError(f"no 12-digit MIFARE keys found in {source}")

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.unlink(missing_ok=True)
    try:
        with sqlite3.connect(temporary) as conn:
            conn.execute("PRAGMA page_size = 4096")
            conn.execute("PRAGMA user_version = 1")
            conn.execute(
                """
                CREATE TABLE key_library (
                    key TEXT PRIMARY KEY,
                    bucket TEXT NOT NULL,
                    sources TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX idx_key_library_bucket ON key_library(bucket)")
            conn.executemany(
                """
                INSERT INTO key_library
                    (key, bucket, sources, note, created_at, updated_at)
                VALUES (?, 'public', ?, ?, ?, ?)
                """,
                [
                    (key, SOURCE_LABEL, SOURCE_NOTE, SEEDED_AT, SEEDED_AT)
                    for key in keys
                ],
            )
            conn.commit()
        os.replace(temporary, output)
        output.chmod(0o644)
    finally:
        temporary.unlink(missing_ok=True)

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return len(keys), digest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the deterministic bundled key library from the locked compat submodule."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    count, digest = build_database(args.source.resolve(), args.output.resolve())
    print(f"keys={count}")
    print(f"sha256={digest}")
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
