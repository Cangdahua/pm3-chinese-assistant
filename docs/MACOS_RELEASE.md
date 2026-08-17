# macOS packaging research — binary publication disabled

The public repository currently publishes source only. App, ZIP, and DMG files
must not be attached to GitHub Releases. This document preserves the local
Apple Silicon packaging and compliance-audit path so it can be completed before
binary distribution is reconsidered. The React/Tauri prototype remains outside
this process.

## Architecture support

| Target | Status | Requirement |
|---|---|---|
| `arm64` | Local research only | Locked arm64 PM3 client using macOS system libedit |
| `x86_64` | Blocked | Real Intel PM3 Easy hardware validation and an approved runtime-lock change |
| `universal2` | Blocked | Both slices approved after real Intel hardware validation |

`tools/release_safety.py preflight-macos` inspects every required Mach-O slice,
the deployment target, and console-library dependency. The approved arm64 PM3
runtime has `minos 11.0` and links system `/usr/lib/libedit.3.dylib`; Homebrew
paths are rejected. The pinned PySide6 Essentials 6.11.1 binding libraries require macOS
15, so the finished application's supported baseline is macOS 15 even though
the PM3 sidecar itself can run on macOS 11.

## Local build

Use Python 3.12 on an arm64 Mac with Xcode command-line tools:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-macos-build.txt
make macos-preflight
ALLOW_UNPUBLISHED_BINARY_BUILD=1 make macos-app
```

The environment variable acknowledges that the resulting artifacts are local
compliance-research outputs. It does not authorize distribution. Without it the
packaging script fails closed.

The build performs these gates:

1. validates PM3 runtime provenance, architecture, minimum macOS, and system-libedit dependency;
2. creates a sanitized temporary release tree;
3. rejects Homebrew or unreviewed dynamic-library dependencies;
4. captures exact third-party license/metadata evidence;
5. builds the `.app` with pinned PyInstaller and required Qt modules;
6. verifies every packaged Mach-O architecture and deployment target;
7. refuses any remaining `/opt/homebrew` or `/usr/local/opt` runtime link;
8. optionally signs and notarizes;
9. emits `.app`, `.app.zip`, `.dmg`, and SHA-256 sidecars under
   `release/<version>/<architecture>/`.

Set `SOURCE_DATE_EPOCH` to a fixed Unix timestamp when reproducible manifest
timestamps are required. Apple signatures, notarization tickets, compressed
DMGs, and ZIP metadata are not guaranteed bit-for-bit identical between runs;
their inputs and checks are reproducible and recorded.

## Signing

For a Developer ID build:

```bash
MACOS_CODESIGN_IDENTITY='Developer ID Application: Example (TEAMID)' \
REQUIRE_SIGNING=1 \
make macos-app
```

With no identity, the script clearly labels the result as a local ad-hoc build.
Any future binary release automation must set `REQUIRE_SIGNING=1`. If special
entitlements are reviewed and required, pass an existing plist through
`MACOS_ENTITLEMENTS_FILE`; the default intentionally grants no extra
entitlements.

## Notarization

Set `NOTARIZE=1`, a signing identity, and exactly one credential method:

- keychain profile: `MACOS_NOTARY_KEYCHAIN_PROFILE`;
- App Store Connect API key: `APPLE_API_KEY_PATH`, `APPLE_API_KEY_ID`, and
  `APPLE_API_ISSUER`;
- Apple ID: `APPLE_ID`, `APPLE_TEAM_ID`, and
  `APPLE_APP_SPECIFIC_PASSWORD`.

Example using a profile previously created with `notarytool store-credentials`:

```bash
MACOS_CODESIGN_IDENTITY='Developer ID Application: Example (TEAMID)' \
MACOS_NOTARY_KEYCHAIN_PROFILE='pm3-notary' \
REQUIRE_SIGNING=1 NOTARIZE=1 \
make macos-app
```

The app ZIP is submitted first and the accepted ticket is stapled to the app.
The resulting DMG is then signed, submitted, stapled, and assessed with
Gatekeeper. Missing credentials, failed notarization, or failed assessment is a
hard error.

Never commit certificates, `.p8` keys, passwords, or keychain exports. The root
ignore rules cover common signing-secret file types.

## Release blockers outside the repository

- Binary publication is disabled until the exact Python/Qt/runtime license
  bundle and corresponding-source process pass review.
- An Apple Developer ID certificate and notarization credentials are external.
- Intel/universal2 research binaries pass Rosetta startup, but remain blocked
  until PM3 Easy behavior is validated on real Intel hardware.
- The root project's original-code license still requires an owner decision.
- Public distribution requires a release-specific review of Proxmark3,
  PySide6/Qt, pyserial, and corresponding-source obligations.
- Final validation requires an authorized PM3 Easy device and test cards; CI
  deliberately performs no hardware operations.
