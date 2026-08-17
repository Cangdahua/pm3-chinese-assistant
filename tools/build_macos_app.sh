#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TARGET_ARCH="${TARGET_ARCH:-arm64}"
APP_VERSION="${APP_VERSION:-0.3.1}"
APP_BUILD_NUMBER="${APP_BUILD_NUMBER:-20260817.1}"
APP_MAX_MIN_MACOS="${APP_MAX_MIN_MACOS:-15.0}"
APP_BASENAME="PM3 Chinese Assistant"
BUNDLE_ID="${MACOS_BUNDLE_ID:-com.pm3chineseassistant.app}"
SIGNING_IDENTITY="${MACOS_CODESIGN_IDENTITY:-}"
ENTITLEMENTS_FILE="${MACOS_ENTITLEMENTS_FILE:-}"
REQUIRE_SIGNING="${REQUIRE_SIGNING:-0}"
NOTARIZE="${NOTARIZE:-0}"
if [[ -z "$SIGNING_IDENTITY" ]]; then
  ARTIFACT_QUALIFIER="local-adhoc"
  APP_DISPLAY_NAME="PM3 中文助手（本地 Ad Hoc）"
elif [[ "$NOTARIZE" == "1" ]]; then
  ARTIFACT_QUALIFIER="notarized"
  APP_DISPLAY_NAME="PM3 中文助手"
else
  ARTIFACT_QUALIFIER="developer-id"
  APP_DISPLAY_NAME="PM3 中文助手（未公证）"
fi
BUILD_ROOT="${BUILD_ROOT:-$ROOT_DIR/build/macos/$TARGET_ARCH}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/release/$APP_VERSION/$TARGET_ARCH}"
STAGE_DIR="$BUILD_ROOT/stage"
WORK_DIR="$BUILD_ROOT/pyinstaller-work"
SPEC_DIR="$BUILD_ROOT/spec"
DIST_DIR="$BUILD_ROOT/dist"
APP_BUNDLE="$DIST_DIR/$APP_BASENAME.app"
FINAL_APP="$OUTPUT_DIR/$APP_BASENAME-$ARTIFACT_QUALIFIER.app"
ZIP_PATH="$OUTPUT_DIR/$APP_BASENAME-$APP_VERSION-$TARGET_ARCH-$ARTIFACT_QUALIFIER.app.zip"
DMG_PATH="$OUTPUT_DIR/$APP_BASENAME-$APP_VERSION-$TARGET_ARCH-$ARTIFACT_QUALIFIER.dmg"
UPLOAD_ZIP="$BUILD_ROOT/notary-upload.zip"
DMG_STAGE="$BUILD_ROOT/dmg-stage"
DMG_MOUNT="$BUILD_ROOT/dmg-mount"

fail() {
  echo "error: $*" >&2
  exit 1
}

if [[ "${ALLOW_UNPUBLISHED_BINARY_BUILD:-0}" != "1" ]]; then
  fail "binary packaging is disabled for the source-only public baseline; set ALLOW_UNPUBLISHED_BINARY_BUILD=1 only for local compliance research, never for publication"
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  fail "macOS packaging must run on macOS"
fi
case "$TARGET_ARCH" in
  arm64|x86_64|universal2) ;;
  *) fail "TARGET_ARCH must be arm64, x86_64, or universal2" ;;
esac
case "$BUILD_ROOT" in
  "$ROOT_DIR"/build/*) ;;
  *) fail "BUILD_ROOT must stay under $ROOT_DIR/build" ;;
esac
case "$OUTPUT_DIR" in
  "$ROOT_DIR"/release/*) ;;
  *) fail "OUTPUT_DIR must stay under $ROOT_DIR/release" ;;
esac
if [[ "$REQUIRE_SIGNING" == "1" && -z "$SIGNING_IDENTITY" ]]; then
  fail "REQUIRE_SIGNING=1 but MACOS_CODESIGN_IDENTITY is empty"
fi
if [[ "$NOTARIZE" == "1" && -z "$SIGNING_IDENTITY" ]]; then
  fail "NOTARIZE=1 requires a Developer ID Application identity"
fi
if [[ -n "$ENTITLEMENTS_FILE" && ! -f "$ENTITLEMENTS_FILE" ]]; then
  fail "MACOS_ENTITLEMENTS_FILE does not exist: $ENTITLEMENTS_FILE"
fi
for command in lipo otool install_name_tool codesign hdiutil ditto; do
  command -v "$command" >/dev/null 2>&1 || fail "missing required command: $command"
done
"$PYTHON_BIN" -c 'import PyInstaller, PySide6, serial' >/dev/null 2>&1 ||
  fail "missing build dependencies; run: $PYTHON_BIN -m pip install -r requirements-macos-build.txt"

"$PYTHON_BIN" "$ROOT_DIR/tools/runtime_provenance.py"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" preflight-macos --target-arch "$TARGET_ARCH"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" validate-output "$BUILD_ROOT" >/dev/null
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" validate-output "$OUTPUT_DIR" >/dev/null

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT" "$OUTPUT_DIR" "$SPEC_DIR" "$WORK_DIR" "$DIST_DIR"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" prepare \
  "$STAGE_DIR" --target-arch "$TARGET_ARCH"

pyinstaller_args=(
  --noconfirm
  --clean
  --windowed
  --name "$APP_BASENAME"
  --osx-bundle-identifier "$BUNDLE_ID"
  --target-architecture "$TARGET_ARCH"
  --distpath "$DIST_DIR"
  --workpath "$WORK_DIR"
  --specpath "$SPEC_DIR"
  --hidden-import PySide6.QtQuick
  --hidden-import PySide6.QtQuickControls2
  --hidden-import PySide6.QtOpenGL
  --add-data "$STAGE_DIR/pm3-qml-client/Main.qml:pm3-qml-client"
  --add-data "$STAGE_DIR/pm3-qml-client/data:pm3-qml-client/data"
  --add-data "$STAGE_DIR/compat-clients:compat-clients"
  --add-data "$STAGE_DIR/licenses:licenses"
)
for document in LICENSE THIRD_PARTY_NOTICES.md docs/COMPAT_CLIENT_PROVENANCE.md; do
  if [[ -f "$STAGE_DIR/$document" ]]; then
    pyinstaller_args+=(--add-data "$STAGE_DIR/$document:$(dirname "$document")")
  fi
done
if [[ -f "$ROOT_DIR/src-tauri/icons/icon.icns" ]]; then
  pyinstaller_args+=(--icon "$ROOT_DIR/src-tauri/icons/icon.icns")
fi
if [[ -n "$SIGNING_IDENTITY" ]]; then
  pyinstaller_args+=(--codesign-identity "$SIGNING_IDENTITY")
fi
if [[ -n "$ENTITLEMENTS_FILE" ]]; then
  pyinstaller_args+=(--osx-entitlements-file "$ENTITLEMENTS_FILE")
fi
pyinstaller_args+=("$STAGE_DIR/pm3-qml-client/main.py")

"$PYTHON_BIN" -m PyInstaller "${pyinstaller_args[@]}"
[[ -d "$APP_BUNDLE" ]] || fail "PyInstaller did not create $APP_BUNDLE"

set_plist_value() {
  local key="$1"
  local type="$2"
  local value="$3"
  local plist="$APP_BUNDLE/Contents/Info.plist"
  if /usr/libexec/PlistBuddy -c "Print :$key" "$plist" >/dev/null 2>&1; then
    /usr/libexec/PlistBuddy -c "Set :$key $value" "$plist"
  else
    /usr/libexec/PlistBuddy -c "Add :$key $type $value" "$plist"
  fi
}
set_plist_value CFBundleDisplayName string "$APP_DISPLAY_NAME"
set_plist_value CFBundleShortVersionString string "$APP_VERSION"
set_plist_value CFBundleVersion string "$APP_BUILD_NUMBER"
set_plist_value PM3BuildChannel string "$ARTIFACT_QUALIFIER"
set_plist_value LSMinimumSystemVersion string "$APP_MAX_MIN_MACOS"

app_executable="$APP_BUNDLE/Contents/MacOS/$APP_BASENAME"
resource_root="$APP_BUNDLE/Contents/Frameworks"
runtime_binary="$resource_root/compat-clients/iceman-ice_v3.1.0/client/proxmark3"
runtime_readline=""
if [[ -f "$resource_root/compat-clients/iceman-ice_v3.1.0/client/lib/libreadline.8.dylib" ]]; then
  runtime_readline="$resource_root/compat-clients/iceman-ice_v3.1.0/client/lib/libreadline.8.dylib"
fi
[[ -f "$runtime_binary" ]] || fail "packaged compatibility client is missing"

required_arches=("$TARGET_ARCH")
if [[ "$TARGET_ARCH" == "universal2" ]]; then
  required_arches=(arm64 x86_64)
fi
architecture_paths=("$app_executable" "$runtime_binary")
if [[ -n "$runtime_readline" ]]; then
  architecture_paths+=("$runtime_readline")
fi
for path in "${architecture_paths[@]}"; do
  actual_arches="$(lipo -archs "$path")"
  for arch in "${required_arches[@]}"; do
    [[ " $actual_arches " == *" $arch "* ]] ||
      fail "$path is missing required $arch slice (contains: $actual_arches)"
  done
done
if otool -L "$runtime_binary" | grep -E '/opt/homebrew|/usr/local/opt' >/dev/null; then
  fail "packaged compatibility client still contains a Homebrew dependency"
fi
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" audit-macho-tree \
  "$APP_BUNDLE" --target-arch "$TARGET_ARCH" --max-min-macos "$APP_MAX_MIN_MACOS"

if [[ -n "$SIGNING_IDENTITY" ]]; then
  sign_args=(--force --timestamp --options runtime --sign "$SIGNING_IDENTITY")
  if [[ -n "$runtime_readline" ]]; then
    codesign "${sign_args[@]}" "$runtime_readline"
  fi
  codesign "${sign_args[@]}" "$runtime_binary"
  app_sign_args=("${sign_args[@]}")
  if [[ -n "$ENTITLEMENTS_FILE" ]]; then
    app_sign_args+=(--entitlements "$ENTITLEMENTS_FILE")
  fi
  codesign --deep "${app_sign_args[@]}" "$APP_BUNDLE"
else
  echo "No MACOS_CODESIGN_IDENTITY supplied; producing a local ad-hoc build."
  echo "Set REQUIRE_SIGNING=1 in release automation to forbid unsigned artifacts."
  codesign --deep --force --sign - "$APP_BUNDLE"
fi

# Nested signing changes the PM3 Mach-O hash. Rebuild the manifest against the
# physical PyInstaller resource root, then re-sign only the outer app seal so
# startup verification observes the final nested bytes.
[[ -d "$resource_root/pm3-qml-client" && -d "$resource_root/compat-clients" ]] ||
  fail "cannot locate PyInstaller resource root for final integrity manifest"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" manifest --root "$resource_root" >/dev/null
if [[ -n "$SIGNING_IDENTITY" ]]; then
  outer_sign_args=(--force --timestamp --options runtime --sign "$SIGNING_IDENTITY")
  if [[ -n "$ENTITLEMENTS_FILE" ]]; then
    outer_sign_args+=(--entitlements "$ENTITLEMENTS_FILE")
  fi
  codesign "${outer_sign_args[@]}" "$APP_BUNDLE"
else
  codesign --force --sign - "$APP_BUNDLE"
fi
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" verify-manifest --root "$resource_root"

rm -rf "$FINAL_APP"
ditto "$APP_BUNDLE" "$FINAL_APP"

notary_credentials=()
if [[ -n "${MACOS_NOTARY_KEYCHAIN_PROFILE:-}" ]]; then
  notary_credentials+=(--keychain-profile "$MACOS_NOTARY_KEYCHAIN_PROFILE")
elif [[ -n "${APPLE_API_KEY_PATH:-}" && -n "${APPLE_API_KEY_ID:-}" && -n "${APPLE_API_ISSUER:-}" ]]; then
  notary_credentials+=(--key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY_ID" --issuer "$APPLE_API_ISSUER")
elif [[ -n "${APPLE_ID:-}" && -n "${APPLE_TEAM_ID:-}" && -n "${APPLE_APP_SPECIFIC_PASSWORD:-}" ]]; then
  notary_credentials+=(--apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_SPECIFIC_PASSWORD")
elif [[ "$NOTARIZE" == "1" ]]; then
  fail "NOTARIZE=1 but no notary credentials are configured; see docs/MACOS_RELEASE.md"
fi

rm -f "$ZIP_PATH" "$DMG_PATH" "$ZIP_PATH.sha256" "$DMG_PATH.sha256" "$UPLOAD_ZIP"
if [[ "$NOTARIZE" == "1" ]]; then
  ditto -c -k --sequesterRsrc --keepParent "$FINAL_APP" "$UPLOAD_ZIP"
  xcrun notarytool submit "$UPLOAD_ZIP" --wait "${notary_credentials[@]}"
  xcrun stapler staple "$FINAL_APP"
  xcrun stapler validate "$FINAL_APP"
fi

ditto -c -k --sequesterRsrc --keepParent "$FINAL_APP" "$ZIP_PATH"
mkdir -p "$DMG_STAGE" "$DMG_MOUNT"
ditto "$FINAL_APP" "$DMG_STAGE/$(basename "$FINAL_APP")"
hdiutil create -quiet -fs HFS+ -format UDZO \
  -volname "PM3 中文助手 $ARTIFACT_QUALIFIER" \
  -srcfolder "$DMG_STAGE" "$DMG_PATH"
if [[ -n "$SIGNING_IDENTITY" ]]; then
  codesign --force --timestamp --sign "$SIGNING_IDENTITY" "$DMG_PATH"
fi
hdiutil attach -quiet -nobrowse -readonly -mountpoint "$DMG_MOUNT" "$DMG_PATH"
if [[ ! -d "$DMG_MOUNT/$(basename "$FINAL_APP")" ]]; then
  hdiutil detach -quiet "$DMG_MOUNT" || true
  fail "DMG root does not contain the expected .app bundle"
fi
hdiutil detach -quiet "$DMG_MOUNT"
if [[ "$NOTARIZE" == "1" ]]; then
  xcrun notarytool submit "$DMG_PATH" --wait "${notary_credentials[@]}"
  xcrun stapler staple "$DMG_PATH"
  xcrun stapler validate "$DMG_PATH"
  spctl --assess --type execute --verbose=2 "$FINAL_APP"
  spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG_PATH"
fi

"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" sha256 "$ZIP_PATH"
"$PYTHON_BIN" "$ROOT_DIR/tools/release_safety.py" sha256 "$DMG_PATH"
echo "App: $FINAL_APP"
echo "ZIP: $ZIP_PATH"
echo "DMG: $DMG_PATH"
