#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import struct
import tempfile
from pathlib import Path


MH_MAGIC_64 = 0xFEEDFACF
LC_UUID = 0x1B


def normalize_uuid(path: Path) -> str:
    payload = bytearray(path.read_bytes())
    if len(payload) < 32 or struct.unpack_from("<I", payload, 0)[0] != MH_MAGIC_64:
        raise SystemExit(f"expected a thin little-endian 64-bit Mach-O: {path}")
    command_count = struct.unpack_from("<I", payload, 16)[0]
    offset = 32
    uuid_offset: int | None = None
    for _ in range(command_count):
        command, command_size = struct.unpack_from("<II", payload, offset)
        if command_size < 8 or offset + command_size > len(payload):
            raise SystemExit(f"invalid Mach-O load command in {path}")
        if command == LC_UUID:
            if command_size != 24 or uuid_offset is not None:
                raise SystemExit(f"unexpected LC_UUID layout in {path}")
            uuid_offset = offset + 8
        offset += command_size
    if uuid_offset is None:
        raise SystemExit(f"Mach-O has no LC_UUID: {path}")

    payload[uuid_offset : uuid_offset + 16] = b"\0" * 16
    value = bytearray(hashlib.sha256(payload).digest()[:16])
    value[6] = (value[6] & 0x0F) | 0x50
    value[8] = (value[8] & 0x3F) | 0x80
    payload[uuid_offset : uuid_offset + 16] = value

    mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
    os.chmod(temporary, mode)
    os.replace(temporary, path)
    return value.hex()


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive a stable LC_UUID for a thin Mach-O")
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    print(normalize_uuid(args.path))


if __name__ == "__main__":
    main()
