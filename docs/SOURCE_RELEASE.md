# Source-only GitHub releases

The public release channel contains source code only. Binary application
bundles, ZIP files, DMGs, generated PM3 executables, signing material, and local
archives are prohibited.

## Local verification

From a clean committed checkout with the submodule initialized but unmodified:

```bash
git submodule update --init --recursive
make source-audit
make source-archive SOURCE_VERSION=0.3.1
```

The audit verifies the locked upstream URL and commit, the patch checksum and
applicability, and deterministic generation of the required Lua modules. It
also rejects legacy local-overlay fields and binary publication artifacts.

The archive is written below `release/source/` with a SHA-256 sidecar. It is
deterministic for a given root commit and contains:

- the committed root source;
- the complete compatibility-client tree at the locked upstream commit;
- the exact compatibility patch applied to that tree;
- the patch and machine-readable runtime lock;
- `SOURCE_PROVENANCE.json` recording both commits and hashes;
- no generated executable or application package.

## GitHub tag workflow

Pushing a `v*` tag runs `.github/workflows/source-release.yml`. The job repeats
the source audit, builds the complete archive, and creates a GitHub Release with
only the archive and checksum.

Configure the `source-release` GitHub Environment with required reviewers and
protect `v*` tags before enabling public releases. The publish job is the only
workflow job granted `contents: write`; checkout credentials are not persisted.

GitHub also displays automatic ZIP and tar archives for every tag. Those
automatic archives do not expand Git submodules, so they are not the complete
source bundle. Use the attached file named
`pm3-chinese-assistant-<version>-source.tar.gz`.

The macOS packaging helper is retained only for local compliance research and
fails unless `ALLOW_UNPUBLISHED_BINARY_BUILD=1` is set. That acknowledgement
does not make its output publishable.
