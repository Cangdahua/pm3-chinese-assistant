#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import py_compile
import re
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_COMPAT_CHECKOUT = PROJECT_ROOT / "compat-clients/iceman-ice_v3.1.0"
APP_VERSION = "0.3.1"
APP_BUILD = "2026.08.17-safety-v3"

MANIFEST_TARGETS = (
    "pm3-qml-client/main.py",
    "pm3-qml-client/Main.qml",
    "pm3-qml-client/data/key_library.sqlite",
    "compat-clients/iceman-ice_v3.1.0/client/proxmark3",
    "compat-clients/iceman-ice_v3.1.0/client/default_keys.dic",
    "compat-clients/iceman-ice_v3.1.0/client/default_pwd.dic",
    "compat-clients/iceman-ice_v3.1.0/client/hardnested/bf_bench_data.bin",
    "compat-clients/iceman-ice_v3.1.0/client/lib/libreadline.8.dylib",
)

STAGED_TARGETS = (
    "pm3-qml-client/Main.qml",
    "pm3-qml-client/main.py",
    "pm3-qml-client/data/key_library.sqlite",
)

RUNTIME_TARGETS = (
    "compat-clients/iceman-ice_v3.1.0/LICENSE.txt",
    "compat-clients/iceman-ice_v3.1.0/client/proxmark3",
    "compat-clients/iceman-ice_v3.1.0/client/default_keys.dic",
    "compat-clients/iceman-ice_v3.1.0/client/default_pwd.dic",
    "compat-clients/iceman-ice_v3.1.0/client/scripts",
    "compat-clients/iceman-ice_v3.1.0/client/lualibs",
    "compat-clients/iceman-ice_v3.1.0/client/hardnested/tables",
    "compat-clients/iceman-ice_v3.1.0/client/hardnested/bf_bench_data.bin",
)

RELEASE_DOCUMENTS = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "docs/COMPAT_CLIENT_PROVENANCE.md",
)

SUPPORTED_MACOS_ARCHES = ("arm64", "x86_64", "universal2")
MAX_RUNTIME_MIN_MACOS = os.environ.get("PM3_RUNTIME_MAX_MIN_MACOS", "12.0")

OPTIONAL_SOURCE_RUNTIME_TARGETS = {
    "compat-clients/iceman-ice_v3.1.0/client/proxmark3",
    "compat-clients/iceman-ice_v3.1.0/client/lib/libreadline.8.dylib",
}

PUBLISHED_RUNTIME_DIRECTORIES = (
    "client/scripts",
    "client/lualibs",
    "client/hardnested/tables",
)

GENERATED_RUNTIME_PATHS = {
    "compat-clients/iceman-ice_v3.1.0/client/lualibs/mf_default_keys.lua",
    "compat-clients/iceman-ice_v3.1.0/client/lualibs/usb_cmd.lua",
}

FORBIDDEN_NAMES = {
    ".DS_Store",
    "dumpdata.bin",
    "dumpkeys.bin",
    "dumpdata.json",
    "selected_data.bin",
    "pending_write_data.bin",
    "nonces.bin",
    "trace.bin",
    "pm3.log",
    "proxmark3.log",
    ".history",
    "dumpkeys-status.json",
    "selected_data.eml",
    "selected_data_magic_target.bin",
    "selected_data_smart_target.bin",
    "pending_write_data.bin",
    "pm3_my_key_library.dic",
}

FORBIDDEN_SUFFIXES = (
    ".log",
    ".trace",
    ".tmp",
    ".bak",
)

FORBIDDEN_PARTS = {
    "__pycache__",
    ".pytest_cache",
    "build",
    "dist",
    ".git",
}

FORBIDDEN_PREFIXES = (
    "pm3_localdict_",
    "before_magic_write_",
    "before_ordinary_write_",
    "before_blank_reset_",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_one(relative_path: str, output_root: Path) -> None:
    source = PROJECT_ROOT / relative_path
    target = output_root / relative_path
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def validate_prepare_output(output_root: Path) -> Path:
    """Confine destructive release staging to project-owned generated folders."""
    candidate = output_root.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.exists() and candidate.is_symlink():
        raise SystemExit(f"release output must not be a symlink: {candidate}")
    resolved = candidate.resolve(strict=False)
    raw_allowed_roots = (PROJECT_ROOT / "build", PROJECT_ROOT / "release")
    symlink_roots = [root for root in raw_allowed_roots if root.is_symlink()]
    if symlink_roots:
        raise SystemExit(
            "generated-output roots must not be symlinks: "
            + ", ".join(str(path) for path in symlink_roots)
        )
    allowed_roots = tuple(root.resolve() for root in raw_allowed_roots)
    if not any(resolved != root and resolved.is_relative_to(root) for root in allowed_roots):
        raise SystemExit(
            "release output must be a child of "
            f"{PROJECT_ROOT / 'build'} or {PROJECT_ROOT / 'release'}: {resolved}"
        )
    if resolved.exists() and not resolved.is_dir():
        raise SystemExit(f"release output exists but is not a directory: {resolved}")
    return resolved


def verify_runtime_provenance(
    allow_missing_binary: bool = False, source_checkout: bool = False
) -> None:
    command = [sys.executable, str(PROJECT_ROOT / "tools/runtime_provenance.py")]
    if allow_missing_binary:
        command.append("--allow-missing-binary")
    if source_checkout:
        command.append("--source-checkout")
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = (result.stdout + result.stderr).strip()
        raise SystemExit(f"runtime provenance verification failed:\n{detail}")


def validate_runtime_source_tree() -> None:
    """Reject untracked files from recursively copied release directories."""
    git_check = subprocess.run(
        ["git", "-C", str(ACTIVE_COMPAT_CHECKOUT), "rev-parse", "--is-inside-work-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if git_check.returncode != 0 or git_check.stdout.strip() != "true":
        raise SystemExit(
            "active compatibility-client submodule is unavailable; run "
            "git submodule update --init --recursive"
        )
    tracked_result = subprocess.run(
        [
            "git",
            "-C",
            str(ACTIVE_COMPAT_CHECKOUT),
            "ls-files",
            "--",
            *PUBLISHED_RUNTIME_DIRECTORIES,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if tracked_result.returncode != 0:
        raise SystemExit(f"cannot enumerate tracked runtime inputs: {tracked_result.stderr.strip()}")

    prefix = "compat-clients/iceman-ice_v3.1.0/"
    tracked_expected = {prefix + line for line in tracked_result.stdout.splitlines() if line}
    expected = set(tracked_expected)
    expected.update(GENERATED_RUNTIME_PATHS)
    actual: set[str] = set()
    for relative_directory in PUBLISHED_RUNTIME_DIRECTORIES:
        directory = ACTIVE_COMPAT_CHECKOUT / relative_directory
        if not directory.is_dir():
            raise SystemExit(f"missing runtime directory: {directory}")
        for path in directory.rglob("*"):
            if path.is_symlink():
                raise SystemExit(f"runtime input must not be a symlink: {path}")
            if path.is_file():
                actual.add(str(path.relative_to(PROJECT_ROOT)))

    missing_generated = GENERATED_RUNTIME_PATHS - actual
    if missing_generated:
        raise SystemExit(
            "missing deterministic generated runtime inputs: "
            + ", ".join(sorted(missing_generated))
        )
    missing_tracked = tracked_expected - actual
    if missing_tracked:
        raise SystemExit(
            "tracked runtime inputs are missing: " + ", ".join(sorted(missing_tracked))
        )
    unexpected = actual - expected
    if unexpected:
        raise SystemExit(
            "untracked files are not permitted in published runtime directories: "
            + ", ".join(sorted(unexpected))
        )


def macho_architectures(path: Path) -> set[str]:
    """Return Mach-O slices reported by lipo, with a useful failure message."""
    if not path.exists():
        raise SystemExit(f"missing Mach-O file: {path}")
    if not shutil.which("lipo"):
        raise SystemExit("lipo is required for macOS release architecture checks")
    result = subprocess.run(
        ["lipo", "-archs", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"cannot inspect Mach-O architectures for {path}: {detail}")
    return set(result.stdout.strip().split())


def required_architectures(target_arch: str) -> set[str]:
    if target_arch == "universal2":
        return {"arm64", "x86_64"}
    if target_arch not in SUPPORTED_MACOS_ARCHES:
        raise SystemExit(
            f"unsupported target architecture {target_arch!r}; "
            f"choose one of {', '.join(SUPPORTED_MACOS_ARCHES)}"
        )
    return {target_arch}


def validate_macho_architectures(path: Path, target_arch: str, label: str) -> set[str]:
    actual = macho_architectures(path)
    missing = required_architectures(target_arch) - actual
    if missing:
        raise SystemExit(
            f"{label} cannot satisfy {target_arch}: {path} contains "
            f"{', '.join(sorted(actual)) or 'no Mach-O slices'}; missing "
            f"{', '.join(sorted(missing))}"
        )
    return actual


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in value.split("."))
    except ValueError as error:
        raise SystemExit(f"invalid macOS version {value!r}") from error


def macho_minimum_versions(path: Path) -> dict[str, str]:
    if not shutil.which("vtool"):
        raise SystemExit("vtool is required for macOS deployment-target checks")
    result = subprocess.run(
        ["vtool", "-show-build", str(path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise SystemExit(f"cannot inspect macOS deployment target for {path}: {detail}")
    architectures = macho_architectures(path)
    current_arch = next(iter(architectures)) if len(architectures) == 1 else ""
    versions: dict[str, str] = {}
    for raw_line in result.stdout.splitlines():
        architecture_match = re.search(r"\(architecture ([^)]+)\):$", raw_line)
        if architecture_match:
            current_arch = architecture_match.group(1)
            continue
        version_match = re.match(r"\s+(?:minos|version)\s+([0-9]+(?:\.[0-9]+)*)\s*$", raw_line)
        if current_arch and version_match and current_arch not in versions:
            versions[current_arch] = version_match.group(1)
    return versions


def validate_macos_minimum_version(
    path: Path,
    target_arch: str,
    label: str,
    maximum: str = MAX_RUNTIME_MIN_MACOS,
) -> dict[str, str]:
    versions = macho_minimum_versions(path)
    maximum_tuple = _version_tuple(maximum)
    for arch in sorted(required_architectures(target_arch)):
        version = versions.get(arch)
        if version is None:
            raise SystemExit(f"cannot determine {label} minimum macOS for {arch}: {path}")
        if _version_tuple(version) > maximum_tuple:
            raise SystemExit(
                f"{label} {arch} slice requires macOS {version}, above the reviewed "
                f"runtime baseline {maximum}: {path}"
            )
    return versions


MACHO_MAGICS = {
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
    b"\xbe\xba\xfe\xca",
    b"\xca\xfe\xba\xbf",
    b"\xbf\xba\xfe\xca",
}


def is_macho(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(4) in MACHO_MAGICS
    except OSError:
        return False


def audit_macho_tree(root: Path, target_arch: str, maximum: str) -> int:
    if not root.is_dir():
        raise SystemExit(f"missing app tree for Mach-O audit: {root}")
    count = 0
    findings: list[str] = []
    for path in root.rglob("*"):
        if path.suffix == ".a" or not path.is_file() or path.is_symlink() or not is_macho(path):
            continue
        count += 1
        try:
            validate_macho_architectures(path, target_arch, "packaged Mach-O")
            validate_macos_minimum_version(path, target_arch, "packaged Mach-O", maximum)
            unreviewed = [
                dependency
                for dependency in _dynamic_dependencies(path)
                if dependency.startswith(("/opt/homebrew/", "/usr/local/opt/"))
            ]
            if unreviewed:
                raise SystemExit(
                    f"packaged Mach-O has an unreviewed Homebrew dependency: {path}: "
                    + ", ".join(unreviewed)
                )
        except SystemExit as error:
            findings.append(str(error))
    if not count:
        findings.append(f"no Mach-O files found under {root}")
    if findings:
        raise SystemExit("Mach-O tree audit failed:\n" + "\n".join(findings))
    return count


def _readline_candidates(arch: str) -> list[Path]:
    candidates: list[Path] = []
    per_arch = os.environ.get(f"PM3_READLINE_{arch.upper()}_DYLIB")
    shared = os.environ.get("PM3_READLINE_DYLIB")
    if per_arch:
        candidates.append(Path(per_arch).expanduser())
    if shared:
        candidates.append(Path(shared).expanduser())

    if arch == "arm64":
        candidates.append(Path("/opt/homebrew/opt/readline/lib/libreadline.8.dylib"))
    else:
        candidates.append(Path("/usr/local/opt/readline/lib/libreadline.8.dylib"))

    brew = shutil.which("brew")
    if brew:
        result = subprocess.run(
            [brew, "--prefix", "readline"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            candidates.append(Path(result.stdout.strip()) / "lib/libreadline.8.dylib")
    return list(dict.fromkeys(candidates))


def find_readline(arch: str) -> Path:
    attempted: list[str] = []
    for candidate in _readline_candidates(arch):
        attempted.append(str(candidate))
        if not candidate.exists():
            continue
        try:
            if arch in macho_architectures(candidate):
                return candidate
        except SystemExit:
            continue
    env_name = f"PM3_READLINE_{arch.upper()}_DYLIB"
    raise SystemExit(
        f"missing {arch} readline dylib; install Homebrew readline or set {env_name}. "
        f"Checked: {', '.join(attempted) or '(no candidates)'}"
    )


def copy_readline_license(source: Path, output_root: Path, label: str) -> None:
    resolved = source.resolve()
    candidates = [resolved.parent.parent / "COPYING", resolved.parent.parent / "LICENSE"]
    license_source = next((candidate for candidate in candidates if candidate.is_file()), None)
    if license_source is None:
        raise SystemExit(
            f"readline license text was not found next to {resolved}; refusing to package the dylib"
        )
    target = output_root / f"licenses/readline/{label}-{license_source.name}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_source, target)


def collect_python_distribution_metadata(output_root: Path) -> None:
    """Retain exact installed-wheel metadata and any supplied license files."""
    names = ("PySide6-Essentials", "shiboken6", "pyserial")
    for name in names:
        try:
            distribution = importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError as error:
            raise SystemExit(f"missing pinned Python runtime dependency: {name}") from error
        normalized = f"{distribution.metadata['Name']}-{distribution.version}"
        destination = output_root / "licenses/python" / normalized
        destination.mkdir(parents=True, exist_ok=True)
        metadata_text = distribution.read_text("METADATA")
        if not metadata_text:
            raise SystemExit(f"installed distribution has no METADATA: {normalized}")
        (destination / "METADATA").write_text(metadata_text, encoding="utf-8")
        for relative in distribution.files or ():
            basename = Path(str(relative)).name.lower()
            if not any(token in basename for token in ("license", "copying", "notice")):
                continue
            source = Path(distribution.locate_file(relative))
            if source.is_file():
                shutil.copy2(source, destination / Path(str(relative)).name)


def _dynamic_dependencies(binary: Path) -> list[str]:
    result = subprocess.run(
        ["otool", "-L", str(binary)],
        check=True,
        capture_output=True,
        text=True,
    )
    dependencies: list[str] = []
    for raw_line in result.stdout.splitlines():
        stripped = raw_line.strip()
        if " (compatibility version " in stripped:
            dependencies.append(stripped.split(" (", 1)[0])
    return list(dict.fromkeys(dependencies))


def _readline_dependencies(binary: Path) -> list[str]:
    return [dependency for dependency in _dynamic_dependencies(binary) if "libreadline" in dependency]


def bundle_console_dependency(output_root: Path, target_arch: str) -> str:
    binary = output_root / "compat-clients/iceman-ice_v3.1.0/client/proxmark3"
    validate_macho_architectures(binary, target_arch, "PM3 compatibility client")
    validate_macos_minimum_version(binary, target_arch, "PM3 compatibility client")
    dependencies = _dynamic_dependencies(binary)
    readline_dependencies = [dependency for dependency in dependencies if "libreadline" in dependency]
    if not readline_dependencies:
        if any(dependency == "/usr/lib/libedit.3.dylib" for dependency in dependencies):
            return "system-libedit"
        raise SystemExit(
            f"PM3 compatibility client uses neither bundled Readline nor system libedit: {binary}"
        )

    target = binary.parent / "lib/libreadline.8.dylib"
    target.parent.mkdir(parents=True, exist_ok=True)

    if target_arch == "universal2":
        arm64_readline = find_readline("arm64")
        x86_readline = find_readline("x86_64")
        copy_readline_license(arm64_readline, output_root, "arm64")
        copy_readline_license(x86_readline, output_root, "x86_64")
        if arm64_readline.resolve() == x86_readline.resolve():
            shutil.copy2(arm64_readline, target)
        else:
            subprocess.run(
                ["lipo", "-create", str(arm64_readline), str(x86_readline), "-output", str(target)],
                check=True,
            )
    else:
        readline = find_readline(target_arch)
        copy_readline_license(readline, output_root, target_arch)
        shutil.copy2(readline, target)

    validate_macho_architectures(target, target_arch, "bundled readline")
    validate_macos_minimum_version(target, target_arch, "bundled readline")
    subprocess.run(
        ["install_name_tool", "-id", "@loader_path/libreadline.8.dylib", str(target)],
        check=True,
    )
    for dependency in readline_dependencies:
        if dependency != "@loader_path/lib/libreadline.8.dylib":
            subprocess.run(
                [
                    "install_name_tool",
                    "-change",
                    dependency,
                    "@loader_path/lib/libreadline.8.dylib",
                    str(binary),
                ],
                check=True,
            )
    subprocess.run(["codesign", "--force", "--sign", "-", str(target)], check=True)
    subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=True)
    return "bundled-readline"


def sanitize_key_library(path: Path) -> None:
    if not path.exists():
        return
    with sqlite3.connect(path) as conn:
        conn.execute("DELETE FROM key_library WHERE bucket != 'public'")
        conn.commit()


def minify_qml(path: Path) -> None:
    lines = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.rstrip()
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith("//"):
            continue
        lines.append(stripped)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_tree(root: Path, source_tree: bool = False) -> list[str]:
    findings: list[str] = []
    if not root.exists():
        return [f"missing: {root}"]
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        parts = set(relative.parts)
        if parts & FORBIDDEN_PARTS:
            if source_tree:
                continue
            findings.append(f"forbidden path part: {relative}")
            continue
        if path.name in FORBIDDEN_NAMES:
            findings.append(f"forbidden file: {relative}")
            continue
        if path.is_file() and path.name.startswith(FORBIDDEN_PREFIXES):
            findings.append(f"forbidden generated file: {relative}")
            continue
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            findings.append(f"forbidden suffix: {relative}")
    return findings


def build_timestamp() -> str:
    """Use SOURCE_DATE_EPOCH when supplied so release metadata can be reproduced."""
    source_date_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if source_date_epoch:
        try:
            timestamp = int(source_date_epoch)
        except ValueError as error:
            raise SystemExit("SOURCE_DATE_EPOCH must be an integer Unix timestamp") from error
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def expected_manifest_targets(root: Path) -> set[str]:
    targets = {relative_path for relative_path in MANIFEST_TARGETS if (root / relative_path).is_file()}
    runtime_root = root / "compat-clients/iceman-ice_v3.1.0/client"
    for directory_name in ("scripts", "lualibs", "hardnested/tables"):
        directory = runtime_root / directory_name
        if directory.exists():
            targets.update(str(path.relative_to(root)) for path in directory.rglob("*") if path.is_file())
    return targets


def write_manifest(root: Path) -> Path:
    files: dict[str, str] = {}
    targets = expected_manifest_targets(root)
    for relative_path in sorted(targets):
        path = root / relative_path
        files[relative_path] = sha256_file(path)

    manifest = {
        "app": "PM3 Chinese Assistant",
        "version": APP_VERSION,
        "build": APP_BUILD,
        "created_at": build_timestamp(),
        "files": files,
    }
    target = root / "pm3-qml-client/data/integrity_manifest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def verify_manifest(root: Path, allow_missing_runtime: bool = False) -> list[str]:
    manifest_path = root / "pm3-qml-client/data/integrity_manifest.json"
    if not manifest_path.exists():
        return [f"missing integrity manifest: {manifest_path}"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"invalid integrity manifest: {error}"]

    findings: list[str] = []
    if manifest.get("version") != APP_VERSION:
        findings.append(
            f"manifest version is {manifest.get('version')!r}; expected {APP_VERSION!r}"
        )
    if manifest.get("build") != APP_BUILD:
        findings.append(f"manifest build is {manifest.get('build')!r}; expected {APP_BUILD!r}")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        return findings + ["integrity manifest contains no files"]
    expected_targets = expected_manifest_targets(root)
    recorded_targets = {str(path) for path in files}
    allowed_missing = OPTIONAL_SOURCE_RUNTIME_TARGETS if allow_missing_runtime else set()
    for relative_path in sorted(expected_targets - recorded_targets):
        findings.append(f"manifest target not recorded: {relative_path}")
    for relative_path in sorted(recorded_targets - expected_targets - allowed_missing):
        findings.append(f"manifest records unexpected target: {relative_path}")
    for relative_path, expected_hash in sorted(files.items()):
        path = root / str(relative_path)
        if not path.is_file():
            if allow_missing_runtime and relative_path in OPTIONAL_SOURCE_RUNTIME_TARGETS:
                continue
            findings.append(f"manifest target missing: {relative_path}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != str(expected_hash).lower():
            findings.append(
                f"manifest hash mismatch: {relative_path} "
                f"(expected {expected_hash}, got {actual_hash})"
            )
    return findings


def write_sha256_sidecar(path: Path) -> Path:
    digest = sha256_file(path)
    target = path.with_name(path.name + ".sha256")
    target.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    return target


def source_release_findings() -> list[str]:
    """Audit the source-only publication boundary without building binaries."""
    findings: list[str] = []
    lock_path = PROJECT_ROOT / "packaging/compat/runtime-lock.json"
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"cannot read runtime provenance lock: {error}"]
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
            "runtime lock contains unsupported fields: "
            + ", ".join(sorted(unexpected_lock_keys))
        )

    forbidden_roots = ("build", "release", "artifacts")
    forbidden_suffixes = (
        ".dmg",
        ".app.zip",
        ".p12",
        ".pfx",
        ".mobileprovision",
    )
    revision = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--verify", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if revision.returncode == 0:
        listed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "ls-files", "-z"],
            check=True,
            capture_output=True,
        ).stdout
        published_paths = [Path(item.decode()) for item in listed.split(b"\0") if item]
    else:
        excluded_parts = {
            ".git",
            "compat-clients",
            "node_modules",
            "target",
            "build",
            "release",
        }
        published_paths = [
            path.relative_to(PROJECT_ROOT)
            for path in PROJECT_ROOT.rglob("*")
            if path.is_file() and not (set(path.relative_to(PROJECT_ROOT).parts) & excluded_parts)
        ]
    for path in published_paths:
        value = path.as_posix()
        if path.parts and path.parts[0] in forbidden_roots:
            findings.append(f"source publication contains forbidden local root: {value}")
        if value.endswith(forbidden_suffixes):
            findings.append(f"source publication contains a binary/signing artifact: {value}")

    runtime_binary = ACTIVE_COMPAT_CHECKOUT / "client/proxmark3"
    if runtime_binary.exists():
        findings.append(f"clean source checkout contains a generated runtime binary: {runtime_binary}")

    source_workflow = PROJECT_ROOT / ".github/workflows/source-release.yml"
    if not source_workflow.is_file():
        findings.append("missing source-only GitHub release workflow")
    else:
        workflow_text = source_workflow.read_text(encoding="utf-8")
        for required in ("audit-source-release", "build_source_archive.py", "gh release create"):
            if required not in workflow_text:
                findings.append(f"source release workflow is missing required gate: {required}")
    for workflow in (PROJECT_ROOT / ".github/workflows").glob("*.yml"):
        workflow_text = workflow.read_text(encoding="utf-8")
        if "gh release" in workflow_text and any(
            command in workflow_text for command in ("build_macos_app.sh", "make macos-app")
        ):
            findings.append(f"GitHub release workflow invokes binary packaging: {workflow}")
    return findings


def prepare(output_root: Path, target_arch: str = "arm64") -> None:
    output_root = validate_prepare_output(output_root)
    verify_runtime_provenance()
    validate_runtime_source_tree()
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    for relative_path in STAGED_TARGETS:
        copy_one(relative_path, output_root)
    for relative_path in RUNTIME_TARGETS:
        copy_one(relative_path, output_root)
    for relative_path in RELEASE_DOCUMENTS:
        source = PROJECT_ROOT / relative_path
        if source.exists():
            copy_one(relative_path, output_root)

    sanitize_key_library(output_root / "pm3-qml-client/data/key_library.sqlite")
    console_dependency = bundle_console_dependency(output_root, target_arch)
    collect_python_distribution_metadata(output_root)

    qml_path = output_root / "pm3-qml-client/Main.qml"
    if qml_path.exists():
        minify_qml(qml_path)

    source_path = output_root / "pm3-qml-client/main.py"
    if source_path.exists():
        compiled_path = output_root / "pm3-qml-client/__compiled__/main.pyc"
        compiled_path.parent.mkdir(parents=True, exist_ok=True)
        py_compile.compile(str(source_path), cfile=str(compiled_path), doraise=True)

    write_manifest(output_root)

    findings = audit_tree(output_root)
    report = {
        "created_at": build_timestamp(),
        "output_root": str(output_root),
        "target_arch": target_arch,
        "console_dependency": console_dependency,
        "audit_passed": not findings,
        "findings": findings,
        "notes": [
            "This directory is a temporary release-prep output.",
            "It is not a signed or packaged app.",
            "QML is whitespace/comment-minified in this temporary copy.",
            "Python bytecode is generated in __compiled__ for release tooling.",
            "The PM3 client and its console-library strategy were validated for architecture and deployment target.",
        ],
    }
    (output_root / "release_safety_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if findings:
        raise SystemExit("release safety audit found issues; see release_safety_report.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="PM3 release safety helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    manifest_parser = subparsers.add_parser("manifest", help="write source integrity manifest")
    manifest_parser.add_argument("--root", type=Path, default=PROJECT_ROOT)

    verify_parser = subparsers.add_parser(
        "verify-manifest", help="verify every file recorded by the integrity manifest"
    )
    verify_parser.add_argument("--root", type=Path, default=PROJECT_ROOT)
    verify_parser.add_argument(
        "--allow-missing-runtime",
        action="store_true",
        help="permit clean submodule checkouts without generated PM3 runtime artifacts",
    )

    sha_parser = subparsers.add_parser("sha256", help="write SHA256 sidecar for a file")
    sha_parser.add_argument("path", type=Path)

    audit_parser = subparsers.add_parser("audit", help="audit a directory for temporary data")
    audit_parser.add_argument("path", type=Path)
    audit_parser.add_argument(
        "--source-tree",
        action="store_true",
        help="ignore standard build/cache directories that are excluded by Git",
    )

    prepare_parser = subparsers.add_parser("prepare", help="create a temporary release-prep tree")
    prepare_parser.add_argument("output", type=Path)
    prepare_parser.add_argument(
        "--target-arch",
        choices=SUPPORTED_MACOS_ARCHES,
        default="arm64",
        help="required architecture for the PM3 runtime and any bundled dependency",
    )

    preflight_parser = subparsers.add_parser(
        "preflight-macos", help="check runtime architecture, deployment target, and console library"
    )
    preflight_parser.add_argument(
        "--target-arch", choices=SUPPORTED_MACOS_ARCHES, default="arm64"
    )

    runtime_parser = subparsers.add_parser(
        "audit-runtime", help="verify runtime provenance and recursive-copy allowlist"
    )
    runtime_parser.add_argument(
        "--allow-missing-binary",
        action="store_true",
        help="permit a clean source checkout before the compatibility client is built",
    )

    subparsers.add_parser(
        "audit-source-release",
        help="verify the clean submodule and source-only publication boundary",
    )

    output_parser = subparsers.add_parser(
        "validate-output", help="validate a generated build/release output path without deleting it"
    )
    output_parser.add_argument("path", type=Path)

    macho_parser = subparsers.add_parser(
        "audit-macho-tree", help="verify architecture and minimum macOS for every Mach-O file"
    )
    macho_parser.add_argument("path", type=Path)
    macho_parser.add_argument(
        "--target-arch", choices=SUPPORTED_MACOS_ARCHES, default="arm64"
    )
    macho_parser.add_argument("--max-min-macos", default="13.0")

    args = parser.parse_args()
    if args.command == "manifest":
        print(write_manifest(args.root))
    elif args.command == "verify-manifest":
        findings = verify_manifest(args.root, args.allow_missing_runtime)
        if findings:
            print("\n".join(findings))
            raise SystemExit(1)
        print("integrity manifest verified")
    elif args.command == "sha256":
        print(write_sha256_sidecar(args.path))
    elif args.command == "audit":
        findings = audit_tree(args.path, args.source_tree)
        if findings:
            print("\n".join(findings))
            raise SystemExit(1)
        print("audit passed")
    elif args.command == "prepare":
        prepare(args.output, args.target_arch)
        print(args.output)
    elif args.command == "preflight-macos":
        binary = PROJECT_ROOT / "compat-clients/iceman-ice_v3.1.0/client/proxmark3"
        actual = validate_macho_architectures(binary, args.target_arch, "PM3 compatibility client")
        minimum_versions = validate_macos_minimum_version(
            binary, args.target_arch, "PM3 compatibility client"
        )
        dependencies = _dynamic_dependencies(binary)
        if any("libreadline" in dependency for dependency in dependencies):
            for arch in sorted(required_architectures(args.target_arch)):
                readline = find_readline(arch)
                validate_macos_minimum_version(readline, arch, "readline")
                print(f"readline[{arch}]={readline}")
        elif any(dependency == "/usr/lib/libedit.3.dylib" for dependency in dependencies):
            print("console_dependency=system-libedit")
        else:
            raise SystemExit("PM3 compatibility client has no reviewed console-library dependency")
        print(f"proxmark3_arches={','.join(sorted(actual))}")
        print(
            "proxmark3_min_macos="
            + ",".join(f"{arch}:{minimum_versions[arch]}" for arch in sorted(minimum_versions))
        )
    elif args.command == "audit-runtime":
        verify_runtime_provenance(args.allow_missing_binary)
        validate_runtime_source_tree()
        print("runtime input audit passed")
    elif args.command == "audit-source-release":
        findings = source_release_findings()
        try:
            verify_runtime_provenance(allow_missing_binary=True, source_checkout=True)
        except SystemExit as error:
            findings.append(str(error))
        if findings:
            print("\n".join(findings))
            raise SystemExit(1)
        print("source-only release audit passed")
    elif args.command == "validate-output":
        print(validate_prepare_output(args.path))
    elif args.command == "audit-macho-tree":
        count = audit_macho_tree(args.path, args.target_arch, args.max_min_macos)
        print(f"Mach-O tree audit passed ({count} files)")


if __name__ == "__main__":
    main()
