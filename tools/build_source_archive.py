#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKOUT = PROJECT_ROOT / "compat-clients/iceman-ice_v3.1.0"
LOCK_PATH = PROJECT_ROOT / "packaging/compat/runtime-lock.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "release/source"


def run(command: list[str], cwd: Path = PROJECT_ROOT, *, capture: bool = False) -> bytes:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=capture,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip() if capture else ""
        raise SystemExit(f"command failed ({result.returncode}): {' '.join(command)}\n{detail}")
    return result.stdout if capture else b""


def load_lock() -> dict[str, object]:
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read {LOCK_PATH}: {error}") from error
    if lock.get("schema") != 1:
        raise SystemExit(f"unsupported runtime lock schema: {lock.get('schema')!r}")
    allowed_lock_keys = {
        "schema",
        "upstream",
        "patch",
        "runtime",
        "generated_assets",
    }
    unexpected = set(lock) - allowed_lock_keys
    if unexpected:
        raise SystemExit(
            "runtime lock contains unsupported fields: " + ", ".join(sorted(unexpected))
        )
    return lock


def require_clean_checkout() -> tuple[str, int]:
    root_commit = run(["git", "rev-parse", "HEAD"], capture=True).decode().strip()
    root_status = run(
        ["git", "status", "--porcelain", "--untracked-files=no"], capture=True
    ).decode()
    if root_status.strip():
        raise SystemExit("source archive requires a clean committed root checkout")
    checkout_status = run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=CHECKOUT,
        capture=True,
    ).decode()
    if checkout_status.strip():
        raise SystemExit("source archive requires a clean compatibility-client submodule")
    run(
        [
            os.environ.get("PYTHON", "python3"),
            str(PROJECT_ROOT / "tools/runtime_provenance.py"),
            "--allow-missing-binary",
            "--source-checkout",
        ]
    )
    epoch = int(run(["git", "show", "-s", "--format=%ct", "HEAD"], capture=True))
    return root_commit, epoch


def extract_git_archive(repository: Path, destination: Path) -> None:
    payload = run(["git", "archive", "--format=tar", "HEAD"], cwd=repository, capture=True)
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive.getmembers():
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise SystemExit(f"unsafe path in git archive: {member.name}")
        archive.extractall(destination, filter="data")


def add_tree(archive: tarfile.TarFile, root: Path, archive_root: str, epoch: int) -> None:
    paths = [root, *sorted(root.rglob("*"), key=lambda item: item.as_posix())]
    for path in paths:
        relative = path.relative_to(root)
        name = archive_root if not relative.parts else f"{archive_root}/{relative.as_posix()}"
        info = archive.gettarinfo(str(path), arcname=name)
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = epoch
        info.pax_headers = {}
        if info.isdir():
            info.mode = 0o755
        elif info.issym():
            info.mode = 0o777
        elif info.isfile():
            info.mode = 0o755 if info.mode & 0o111 else 0o644
        if info.isfile():
            with path.open("rb") as handle:
                archive.addfile(info, handle)
        else:
            archive.addfile(info)


def write_archive(stage: Path, target: Path, archive_root: str, epoch: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{target.name}.", dir=target.parent, delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with temporary_path.open("wb") as raw:
            with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=epoch) as compressed:
                with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    add_tree(archive, stage, archive_root, epoch)
        os.replace(temporary_path, target)
    finally:
        temporary_path.unlink(missing_ok=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_output(output: Path) -> Path:
    raw_candidate = output.expanduser()
    if not raw_candidate.is_absolute():
        raw_candidate = PROJECT_ROOT / raw_candidate
    raw_release_root = PROJECT_ROOT / "release"
    if raw_release_root.is_symlink():
        raise SystemExit(f"source archive root must not be a symlink: {raw_release_root}")
    if raw_candidate.is_symlink():
        raise SystemExit(f"source archive output must not be a symlink: {raw_candidate}")
    candidate = raw_candidate.resolve(strict=False)
    release_root = raw_release_root.resolve(strict=False)
    if candidate == release_root or not candidate.is_relative_to(release_root):
        raise SystemExit(f"source archive output must be below {release_root}: {candidate}")
    if candidate.exists() and (candidate.is_symlink() or not candidate.is_dir()):
        raise SystemExit(f"source archive output must be a real directory: {candidate}")
    return candidate


def build(version: str, output: Path) -> tuple[Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", version):
        raise SystemExit("version must contain only letters, digits, dots, underscores, and dashes")
    lock = load_lock()
    if shutil.which("patch") is None:
        raise SystemExit("the patch command is required to build the complete source archive")
    root_commit, epoch = require_clean_checkout()
    output = validate_output(output)
    base_name = f"pm3-chinese-assistant-{version}-source"
    archive_path = output / f"{base_name}.tar.gz"

    with tempfile.TemporaryDirectory(prefix="pm3-source-archive-") as temporary:
        stage = Path(temporary) / base_name
        extract_git_archive(PROJECT_ROOT, stage)
        submodule_stage = stage / "compat-clients/iceman-ice_v3.1.0"
        shutil.rmtree(submodule_stage, ignore_errors=True)
        extract_git_archive(CHECKOUT, submodule_stage)

        patch = lock["patch"]
        upstream = lock["upstream"]
        assert isinstance(patch, dict) and isinstance(upstream, dict)
        run(
            [
                "patch",
                "--batch",
                "--forward",
                "--silent",
                "-p1",
                "-d",
                str(submodule_stage),
                "-i",
                str(PROJECT_ROOT / str(patch["path"])),
            ]
        )
        provenance = {
            "schema": 1,
            "root_commit": root_commit,
            "source_date_epoch": epoch,
            "compatibility_client": {
                "upstream": upstream,
                "patch": patch,
                "patch_applied_in_archive": True,
            },
            "generated_assets": lock.get("generated_assets", []),
            "binary_artifacts_included": False,
        }
        (stage / "SOURCE_PROVENANCE.json").write_text(
            json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        write_archive(stage, archive_path, base_name, epoch)

    digest = sha256(archive_path)
    sidecar = archive_path.with_name(archive_path.name + ".sha256")
    sidecar.write_text(f"{digest}  {archive_path.name}\n", encoding="utf-8")
    return archive_path, sidecar


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a deterministic source-only archive with the pinned submodule expanded"
    )
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    archive, sidecar = build(args.version, args.output_dir)
    print(archive)
    print(sidecar)


if __name__ == "__main__":
    main()
