# Release checklist

## Public source release

- [ ] `make source-audit` passes in a clean checkout with an unmodified pinned
      submodule.
- [ ] `make source-archive SOURCE_VERSION=<version>` produces only
      `*-source.tar.gz` and its SHA-256 sidecar.
- [ ] The attached source archive contains `SOURCE_PROVENANCE.json`, the full
      expanded compatibility-client source, its license, and the exact patch.
- [ ] No App, ZIP, DMG, generated PM3 binary, local archive, capture, sample, or
      signing credential is attached to the GitHub Release.
- [ ] Consumers are directed to the attached complete source archive rather
      than GitHub's automatic archive, which does not expand submodules.

The sections below are future binary-release gates. They do not authorize a
binary release while the repository is source-only.

## Source and safety

- [ ] Version/build values agree in the application and release helper.
- [ ] `make check` passes from a dependency-locked environment.
- [ ] `python3 tools/runtime_provenance.py` matches the pinned upstream, patch,
      generated assets, binary hash, and architecture.
- [ ] The integrity manifest is regenerated only after final source/runtime
      changes, then `make release-audit` passes.
- [ ] No personal card dumps, keys, workspaces, logs, HTML captures, samples, or
      signing credentials appear in the staged tree.

## Licensing and provenance

- [ ] The project owner has selected and recorded the original-code license.
- [ ] The active Proxmark3 `LICENSE.txt`, exact patched source, and corresponding
      source delivery plan have been reviewed.
- [ ] The runtime links only the reviewed macOS system `libedit`; exact Python
      distribution metadata is present and reviewed.
- [ ] `THIRD_PARTY_NOTICES.md` matches the exact artifacts being shipped.

## macOS artifact

- [ ] Build runs on the intended architecture; no architecture gate is bypassed.
- [ ] Release automation sets `REQUIRE_SIGNING=1` and uses the intended Developer
      ID identity.
- [ ] App ZIP and DMG notarization both complete; tickets staple and validate.
- [ ] `codesign --verify`, `spctl --assess`, and SHA-256 sidecars pass.
- [ ] A clean Mac without Homebrew launches the app and the PM3 client reports
      only system `libedit`, `libSystem`, and `libc++` dependencies.

## Authorized hardware test

- [ ] Device detection and firmware identification pass on a PM3 Easy device.
- [ ] Read-only card identification and full-card read pass.
- [ ] With expendable authorized media, write preflight, backup, minimal write,
      full readback, and recovery/resume behavior pass.
- [ ] Dangerous commands remain blocked until the explicit dangerous-operation
      capability is enabled.

Record tester, device/firmware identity, macOS version, artifact SHA-256, and
result outside the public repository; do not attach card data or keys.
