#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = PROJECT_ROOT / "packaging/compat/runtime-lock.json"
CHECKOUT = PROJECT_ROOT / "compat-clients/iceman-ice_v3.1.0"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(CHECKOUT), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def checkout_available() -> bool:
    if not CHECKOUT.is_dir():
        return False
    result = git("rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def load_lock() -> dict[str, object]:
    try:
        data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read runtime provenance lock: {error}") from error
    if data.get("schema") != 1:
        raise SystemExit(f"unsupported runtime provenance schema: {data.get('schema')!r}")
    return data


def verify_generated_asset(
    entry: dict[str, object], source_checkout: bool, findings: list[str]
) -> None:
    relative_path = str(entry["path"])
    path = PROJECT_ROOT / relative_path
    expected_hash = str(entry["sha256"])

    if path.is_file():
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            findings.append(
                f"generated asset hash mismatch for {relative_path}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
    elif not source_checkout:
        findings.append(f"missing generated asset: {path}")

    if not source_checkout:
        return

    generated_from = entry.get("generated_from")
    if not isinstance(generated_from, list) or not generated_from:
        findings.append(f"generated asset has no source recipe: {relative_path}")
        return
    source_paths = [PROJECT_ROOT / str(item) for item in generated_from]
    missing = [str(item) for item in source_paths if not item.is_file()]
    if missing:
        findings.append(
            f"generated asset sources are missing for {relative_path}: {', '.join(missing)}"
        )
        return
    awk_scripts = [item for item in source_paths if item.suffix == ".awk"]
    inputs = [item for item in source_paths if item.suffix != ".awk"]
    if len(awk_scripts) != 1 or not inputs:
        findings.append(
            f"generated asset recipe is not one AWK script plus input files: {relative_path}"
        )
        return
    result = subprocess.run(
        ["awk", "-f", str(awk_scripts[0]), *(str(item) for item in inputs)],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        findings.append(
            f"cannot reproduce generated asset {relative_path}: "
            + result.stderr.decode(errors="replace").strip()
        )
        return
    generated_hash = sha256_bytes(result.stdout)
    if generated_hash != expected_hash:
        findings.append(
            f"generated asset recipe mismatch for {relative_path}: "
            f"expected {expected_hash}, got {generated_hash}"
        )


def verify(allow_missing_binary: bool, source_checkout: bool = False) -> list[str]:
    lock = load_lock()
    findings: list[str] = []
    has_checkout = checkout_available()

    allowed_lock_keys = {
        "schema",
        "upstream",
        "patch",
        "runtime",
        "generated_assets",
    }
    unexpected_lock_keys = set(lock) - allowed_lock_keys
    if unexpected_lock_keys:
        findings.append(
            "runtime provenance lock has unsupported top-level fields: "
            + ", ".join(sorted(unexpected_lock_keys))
        )

    upstream = lock["upstream"]
    assert isinstance(upstream, dict)
    if not has_checkout:
        findings.append(
            "active compatibility-client submodule is unavailable; run "
            "git submodule update --init --recursive"
        )
    else:
        head = git("rev-parse", "HEAD")
        if head.returncode != 0:
            findings.append(f"cannot read compatibility-client commit: {head.stderr.strip()}")
        elif head.stdout.strip() != upstream["commit"]:
            findings.append(
                f"compatibility-client commit is {head.stdout.strip()}, expected {upstream['commit']}"
            )

        remote = git("remote", "get-url", "origin")
        if remote.returncode != 0:
            findings.append(f"cannot read compatibility-client origin: {remote.stderr.strip()}")
        elif remote.stdout.strip().rstrip("/") != str(upstream["url"]).rstrip("/"):
            findings.append(
                f"compatibility-client origin is {remote.stdout.strip()!r}, "
                f"expected {upstream['url']!r}"
            )

    patch = lock["patch"]
    assert isinstance(patch, dict)
    patch_path = PROJECT_ROOT / str(patch["path"])
    if not patch_path.is_file():
        findings.append(f"missing compatibility patch: {patch_path}")
    else:
        patch_hash = sha256_file(patch_path)
        if patch_hash != patch["sha256"]:
            findings.append(
                f"compatibility patch hash mismatch: expected {patch['sha256']}, got {patch_hash}"
            )
        if has_checkout:
            # Compare HEAD to the complete index+worktree state. Plain `git diff`
            # would miss a staged replacement of a release input.
            # Git's automatic object-id abbreviation length depends on the
            # repository's object database. Pin it to the length used by the
            # recorded patch so a fresh clone produces the same byte stream.
            diff = git(
                "diff",
                "--abbrev=7",
                "HEAD",
                "--no-ext-diff",
                "--binary",
            )
            if diff.returncode != 0:
                findings.append(f"cannot diff compatibility-client checkout: {diff.stderr.strip()}")
            else:
                diff_hash = sha256_bytes(diff.stdout.encode())
                expected_diff_hash = sha256_bytes(b"") if source_checkout else patch["sha256"]
                if diff_hash != expected_diff_hash:
                    checkout_kind = "clean source" if source_checkout else "patched runtime"
                    findings.append(
                        f"active compatibility-client is not the expected {checkout_kind} checkout "
                        f"(got diff {diff_hash})"
                    )
                elif source_checkout:
                    apply_check = git("apply", "--check", str(patch_path))
                    if apply_check.returncode != 0:
                        findings.append(
                            "recorded compatibility patch does not apply to the clean checkout: "
                            + apply_check.stderr.strip()
                        )

    runtime = lock["runtime"]
    assert isinstance(runtime, dict)
    runtime_path = PROJECT_ROOT / str(runtime["path"])
    if not runtime_path.is_file():
        if not (allow_missing_binary or source_checkout):
            findings.append(
                f"missing built compatibility client: {runtime_path}; run tools/bootstrap_compat_client.sh"
            )
    else:
        runtime_hash = sha256_file(runtime_path)
        if runtime_hash != runtime["sha256"]:
            findings.append(
                f"compatibility-client binary hash mismatch: expected {runtime['sha256']}, "
                f"got {runtime_hash}"
            )
        if shutil.which("lipo"):
            result = subprocess.run(
                ["lipo", "-archs", str(runtime_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            expected_arches = set(runtime["architectures"])
            actual_arches = set(result.stdout.strip().split()) if result.returncode == 0 else set()
            if actual_arches != expected_arches:
                findings.append(
                    f"compatibility-client architectures are {sorted(actual_arches)}, "
                    f"expected {sorted(expected_arches)}"
                )

    generated_assets = lock.get("generated_assets", [])
    assert isinstance(generated_assets, list)
    for entry in generated_assets:
        assert isinstance(entry, dict)
        verify_generated_asset(entry, source_checkout, findings)

    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the active PM3 runtime provenance lock")
    parser.add_argument(
        "--allow-missing-binary",
        action="store_true",
        help="permit a clean source checkout before the compatibility client is built",
    )
    parser.add_argument(
        "--source-checkout",
        action="store_true",
        help="require an unmodified submodule, verify patch applicability, and reproduce generated assets",
    )
    args = parser.parse_args()
    findings = verify(args.allow_missing_binary, args.source_checkout)
    if findings:
        print("\n".join(findings))
        raise SystemExit(1)
    print("runtime provenance verified")


if __name__ == "__main__":
    main()
