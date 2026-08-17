# License archive

The root `LICENSE` applies to original PM3 Chinese Assistant code,
documentation, and project artwork. Third-party work keeps its own license.

## Locked Proxmark3 source

The active compatibility client is pinned to upstream commit
`2954e1d0401e2b9588f9333d9ab931b7ddb37447`.

- `Proxmark3-GPL-2.0.txt` is an exact copy of the submodule's `LICENSE.txt`.
- `uart-posix-BSD-3-Clause.txt` preserves the complete notice embedded in
  `uart/uart_posix.c`.
- `hardnested-crypto1-bs-MIT.txt` preserves the complete MIT notice embedded in
  `client/hardnested/hardnested_bf_core.c`.

The original files and surrounding source remain in the locked submodule. See
`../THIRD_PARTY_NOTICES.md` and `../docs/COMPAT_CLIENT_PROVENANCE.md` for the
patch, hashes, and corresponding-source procedure.

## Project artwork

`public/app-icon.svg` is original project artwork under the root MIT license.
The files in `src-tauri/icons/` are generated derivatives of that SVG and use
the same license.

## Other dependencies

Python, Qt, npm, and Cargo packages are resolved from the project manifests and
are not vendored into this source tree. Their license texts must be collected
from the exact resolved artifacts before any binary distribution. This folder
is not an artifact-specific dependency notice bundle.
