# PM3 compatibility-client provenance

## Locked upstream

The active runtime checkout is the root Git submodule
`compat-clients/iceman-ice_v3.1.0`:

- Upstream: `https://github.com/iceman1001/proxmark3.git`
- Commit: `2954e1d0401e2b9588f9333d9ab931b7ddb37447`
- Commit subject: `fix: forgot some parentheses`
- Local tracked-file patch:
  `packaging/compat/iceman-2954e1d-pm3-easy.patch`
- Patch SHA-256:
  `c7ac2bf0acfb76ba27f8edb8f3bc27fe525c1f0eff1b0f5bf13ef5f43d31b5a7`

The patch is the exact `git diff --abbrev=7 HEAD --no-ext-diff --binary` of three modified
tracked files in the validated checkout: `client/proxmark3.c`, `client/ui.c`,
and `uart/uart_posix.c`. It adds the PM3 Easy short-frame receive path,
serial settings, and a compatibility guard for the system libedit Readline API.

`packaging/compat/runtime-lock.json` is the machine-readable source of truth.
Run:

```bash
python3 tools/runtime_provenance.py
```

The reviewed local binary has SHA-256
`3b9edcfb907f05e9e536aa2fd7badc485110be8d4aba983013026a9e1042ea3d` and
contains only an `arm64` Mach-O slice. It has minimum macOS `11.0` and links
only `/usr/lib/libedit.3.dylib`, `libSystem`, and `libc++`. The bootstrap strips
non-release debug data, derives a stable content-based Mach-O UUID, and ad-hoc
signs the result; two consecutive clean rebuilds produced the same hash.

## Rebuilding

After a clean root checkout:

```bash
git submodule update --init --recursive
tools/bootstrap_compat_client.sh
```

The bootstrap script verifies the upstream commit and patch hash, applies the
patch only to a clean submodule, builds against the macOS SDK's system libedit, then
atomically regenerates `client/lualibs/mf_default_keys.lua` from the tracked
`default_keys.dic` and `default_keys_dic2lua.awk`, and `client/lualibs/usb_cmd.lua`
from `include/usb_cmd.h` plus `client/usb_cmd_h2lua.awk`. Both expected hashes
are recorded in `runtime-lock.json`.

A compiler/toolchain change can produce a different binary hash. Do not update
the lock automatically: inspect architecture, dynamic dependencies, license
inputs, and PM3 Easy hardware behavior before accepting a new hash.

## Clean source policy

- `client/lualibs/mf_default_keys.lua` is a deterministic build output, not a
  hand-maintained source file. It is regenerated and hash-checked.
- `client/lualibs/usb_cmd.lua` is likewise generated from pinned tracked inputs
  and must match its locked hash.
- No optional script, copied archive, local capture, or untracked file is a
  provenance input. Runtime preparation rejects unexpected files in recursively
  published directories.
- `python3 tools/runtime_provenance.py --source-checkout` requires an unmodified
  submodule, verifies that the locked patch applies, and reproduces both
  generated Lua assets in memory.

## Source-only publication

Only the pinned submodule gitlink, exact patch, provenance lock, generated-asset
recipes, and project source belong to the public repository. Generated PM3
binaries are never source-release inputs.

GitHub's automatic source archives do not expand submodules. Tagged releases
therefore attach the archive built by `tools/build_source_archive.py`; it
expands the locked upstream commit, applies the exact patch, records
`SOURCE_PROVENANCE.json`, and refuses binary artifacts. Use that attached
`*-source.tar.gz`, not the automatic archive, when a self-contained source copy
is required.

The public baseline is source-only. App, ZIP, and DMG publication remains
disabled until the separate binary licensing and compliance review is complete.

An x86_64 research build (SHA-256
`7f75d8a6796dfd0bdb23c51a8eca967babb929909da69b9b879d6c17bc395a71`)
and a two-slice libedit smoke artifact (SHA-256
`d6e8fd6b8fecf04dccae7b08963d351bb9f1cd63193b125796ed150d8bcabfe5`)
both passed help startup under Rosetta. They are evidence, not release inputs:
Intel and universal2 stay blocked until PM3 Easy behavior is validated on real
Intel hardware and the approved runtime lock is deliberately changed.
