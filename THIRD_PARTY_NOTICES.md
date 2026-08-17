# Third-party notices

This document identifies third-party material known to the source repository.
It does not relicense upstream work and is not a substitute for an
artifact-specific software bill of materials or legal review.

The repository currently publishes source only. No DMG, app bundle, ZIP, or
other precompiled release is approved for public distribution.

## Original project material

Original PM3 Chinese Assistant code, documentation, and project artwork are
licensed under the root MIT license, with copyright:

> Copyright (c) 2026 PM3 Chinese Assistant contributors

The scope of that license does not include the third-party components listed
below.

## Proxmark3 compatibility client

The active compatibility client is the Git submodule
`compat-clients/iceman-ice_v3.1.0`, derived from `iceman1001/proxmark3` at
commit `2954e1d0401e2b9588f9333d9ab931b7ddb37447`.

- Upstream: <https://github.com/iceman1001/proxmark3>
- Upstream license: GNU General Public License version 2; individual source
  headers may permit version 2 or later.
- Archived license: `LICENSES/Proxmark3-GPL-2.0.txt`
- Original retained license: `compat-clients/iceman-ice_v3.1.0/LICENSE.txt`
- Local patch: `packaging/compat/iceman-2954e1d-pm3-easy.patch`
- Reproducibility lock: `packaging/compat/runtime-lock.json`

The patch is a derivative modification of GPL-covered source and is conveyed
under the applicable upstream GPL terms. A distributor of a compiled
compatibility client must provide the exact complete corresponding source,
including the locked upstream revision, local patch, generated-source inputs,
and build instructions, or another GPL-compliant source offer. A GitHub
auto-generated archive does not embed submodule contents by itself.

Two embedded third-party notices from the locked source are archived separately:

- `LICENSES/uart-posix-BSD-3-Clause.txt`, from `uart/uart_posix.c`.
- `LICENSES/hardnested-crypto1-bs-MIT.txt`, from
  `client/hardnested/hardnested_bf_core.c`.

The bundled SQLite seed is generated from
`compat-clients/iceman-ice_v3.1.0/client/default_keys.dic` at the same locked
commit. Its SHA-256 is
`29c092bcabc31c5542d2fe7cc142933b31dc4460f17361a6e7b39cd8fca0926d` and it is
treated as Proxmark3 project material under the applicable project license.

## Python application dependencies

`pm3-qml-client/requirements.txt` pins:

- `PySide6-Essentials==6.11.1`, which depends on the matching
  `shiboken6==6.11.1` binding runtime. Installed package metadata declares
  `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`; the Qt libraries also have
  module-specific and third-party licenses.
- `pyserial==3.5`, licensed under the BSD 3-Clause license.

`requirements-macos-build.txt` additionally pins PyInstaller. PyInstaller is a
build tool licensed under GPL-2.0-or-later with its Bootloader Exception, while
some embedded runtime hooks are Apache-2.0.

These packages are not vendored in this source repository. The current build is
intentionally limited to PySide6 Essentials and excludes unused Qt modules,
including WebEngine, Multimedia, and PDF. Anyone producing a binary must still
inspect the exact files in that binary, include the full applicable license and
copyright texts, satisfy LGPL replacement/relinking and source-availability
requirements, and remove or properly license any GPL-only Qt module collected
by the packaging tool. Wheel `METADATA` alone is not a complete
binary-distribution notice set, and no binary is approved until this review,
Developer ID signing, and Apple notarization are complete.

## Experimental React/Tauri dependencies

The experimental frontend and backend use the exact versions recorded in
`pnpm-lock.yaml` and `src-tauri/Cargo.lock`. Those dependencies are not
vendored here.

- The current npm graph is primarily MIT, ISC, BSD, and Apache-2.0/MIT. Its
  build graph includes MPL-2.0 `lightningcss` packages.
- The current macOS arm64 Cargo graph contains permissively licensed crates and
  five MPL-2.0 crates: `cssparser`, `cssparser-macros`, `dtoa-short`,
  `option-ext`, and `selectors`.

If the prototype is ever distributed, generate a target- and artifact-specific
notice bundle from the exact lockfiles. MPL-covered source must remain
available under MPL-2.0; MIT, BSD, Apache, Unicode, Zlib, and other notice
requirements must also be retained.

## Bundled key-library seed

`pm3-qml-client/data/key_library.sqlite` contains 406 public default-key records
derived solely from
`compat-clients/iceman-ice_v3.1.0/client/default_keys.dic`. Every row retains
that source label. The source file is fixed at Proxmark3 commit
`2954e1d0401e2b9588f9333d9ab931b7ddb37447`, has SHA-256
`29c092bcabc31c5542d2fe7cc142933b31dc4460f17361a6e7b39cd8fca0926d`, and is
treated as Proxmark3 project material under the applicable project license.
The committed SQLite seed has SHA-256
`84b8e438c6658175a63b9e410013d9b2ad484d70e323fafdf2b716e610007a97`.

User-imported key data is local runtime data and is not part of this source
repository.

## Artwork and community documents

- `public/app-icon.svg` is original project artwork under the root MIT license.
- Platform-specific files in `src-tauri/icons/` are generated derivatives of
  `public/app-icon.svg` and use the same MIT license.
- `CODE_OF_CONDUCT.md` is adapted from Contributor Covenant 2.1, licensed under
  Creative Commons Attribution 4.0; attribution is included in that file.

Unused template logos, a third-party favicon, generic hero artwork, and social
brand glyphs have intentionally been removed from the public source tree.
