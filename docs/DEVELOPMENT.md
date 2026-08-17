# Development guide

## Product lines

The release product is `pm3-qml-client/`: a PySide6/Qt Quick application backed
by the PM3 Easy compatibility client. `src/` and `src-tauri/` are an
experimental command-console prototype. They are linted and compiled to prevent
bit rot, but they are not a release substitute and do not inherit the main
client's write transaction guarantees.

No automated check sends commands to a PM3 device. Hardware testing is a
separate, explicit release-checklist step.

## Prerequisites

- Python 3.12
- pnpm 11.19 and Node.js 24 (Node 22.12+ is also compatible with Vite 8)
- Stable Rust with `rustfmt`
- macOS and Xcode command-line tools only when building the production app

Install the pinned Python and frontend dependencies:

```bash
make bootstrap
```

`requirements-macos-build.txt` includes the runtime requirements and the pinned
PyInstaller version. Use a virtual environment for repeatable local work.

The QML client pins `PySide6-Essentials`, not the `PySide6` meta-package. The
application imports only Qt Core/Gui/QML/Quick/Controls/Layout/OpenGL modules;
keeping Addons out prevents unrelated WebEngine, Multimedia, PDF, and 3D
frameworks from entering a future compliance-audit bundle.

## Checks

Run the same check families used by GitHub Actions:

```bash
make check
```

The target runs:

- Python safety regression tests and syntax parsing for engineering tools;
- `prototype:lint` and `prototype:build` for the experimental frontend;
- Rust format, test, and check for the experimental Tauri backend;
- source-data audit, integrity-manifest verification, and compatibility-runtime
  provenance verification.

Individual targets are `python-check`, `frontend-check`, `rust-check`, and
`release-audit`. `make check` expects dependencies to have been installed and
the locally locked compatibility binary to exist. CI permits that generated
binary to be absent in a clean submodule checkout while still verifying its
recorded provenance, patch, and all source-available manifest entries.

Source publication is a separate clean-checkout gate:

```bash
make source-audit
make source-archive SOURCE_VERSION=0.3.1
```

`source-audit` requires the submodule to be unmodified, checks that the locked
patch still applies, reproduces generated Lua modules without writing them, and
rejects local archives or binary artifacts. `source-archive` requires a clean
committed root checkout and emits a deterministic archive with the submodule
expanded and the patch applied.

The GitHub tag workflow publishes only that complete source archive and its
SHA-256 sidecar. Binary App/ZIP/DMG publication is intentionally disabled.

## Main application

Run the production client from source with:

```bash
python3 pm3-qml-client/main.py
```

Runtime data belongs under
`~/Library/Application Support/PM3 Chinese Assistant/`; it must never be copied
into the repository or a release tree. The root `.gitignore` covers known PM3
logs, card dumps, transactions, local key dictionaries, and workspace paths.

## Experimental prototype

Prototype commands are deliberately namespaced:

```bash
pnpm prototype:dev
pnpm prototype:lint
pnpm prototype:build
cargo check --manifest-path src-tauri/Cargo.toml --locked
```

The old `pnpm dev/build/lint` names remain compatibility aliases only. The
prototype bundle is disabled in its Tauri configuration and must not be shipped
as the production client.
