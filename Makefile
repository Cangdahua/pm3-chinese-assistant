PYTHON ?= python3
PNPM ?= pnpm
CARGO ?= cargo
SOURCE_VERSION ?= dev

.PHONY: help bootstrap bootstrap-python bootstrap-frontend check python-check frontend-check rust-check release-audit source-audit source-archive macos-preflight macos-app compat-client

help:
	@echo "PM3 Chinese Assistant engineering commands"
	@echo "  make bootstrap         Install pinned Python and frontend dependencies"
	@echo "  make check             Run all local checks used by CI"
	@echo "  make release-audit     Verify clean data, integrity manifest and runtime provenance"
	@echo "  make source-audit      Verify the clean source-only publication boundary"
	@echo "  make source-archive    Build complete source archive (SOURCE_VERSION=x.y.z)"
	@echo "  make macos-preflight   Check arm64 runtime and packaging prerequisites"
	@echo "  make macos-app         Blocked by default; local compliance research only"
	@echo "  make compat-client     Rebuild the locked PM3 Easy compatibility client"

bootstrap: bootstrap-python bootstrap-frontend

bootstrap-python:
	$(PYTHON) -m pip install -r requirements-macos-build.txt

bootstrap-frontend:
	$(PNPM) install --frozen-lockfile

check: python-check frontend-check rust-check release-audit

python-check:
	PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s pm3-qml-client/tests -p 'test_*.py'
	$(PYTHON) -c "import ast, pathlib; paths = [*pathlib.Path('tools').glob('*.py'), *pathlib.Path('pm3-qml-client/tools').glob('*.py')]; [ast.parse(path.read_text(encoding='utf-8'), filename=str(path)) for path in paths]"

frontend-check:
	$(PNPM) prototype:lint
	$(PNPM) prototype:build

rust-check:
	$(CARGO) fmt --manifest-path src-tauri/Cargo.toml --all -- --check
	$(CARGO) clippy --manifest-path src-tauri/Cargo.toml --locked --all-targets -- -D warnings
	$(CARGO) test --manifest-path src-tauri/Cargo.toml --locked
	$(CARGO) check --manifest-path src-tauri/Cargo.toml --locked

release-audit:
	$(PYTHON) tools/release_safety.py audit pm3-qml-client --source-tree
	$(PYTHON) tools/release_safety.py verify-manifest
	$(PYTHON) tools/release_safety.py audit-runtime

source-audit:
	$(PYTHON) tools/release_safety.py audit-source-release

source-archive: source-audit
	$(PYTHON) tools/build_source_archive.py --version "$(SOURCE_VERSION)"

macos-preflight:
	$(PYTHON) tools/release_safety.py preflight-macos --target-arch "$${TARGET_ARCH:-arm64}"

macos-app:
	tools/build_macos_app.sh

compat-client:
	tools/bootstrap_compat_client.sh
