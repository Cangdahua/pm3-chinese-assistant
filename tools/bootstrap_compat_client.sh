#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKOUT="$ROOT_DIR/compat-clients/iceman-ice_v3.1.0"
PATCH_FILE="$ROOT_DIR/packaging/compat/iceman-2954e1d-pm3-easy.patch"
EXPECTED_COMMIT="2954e1d0401e2b9588f9333d9ab931b7ddb37447"
EXPECTED_PATCH_SHA="c7ac2bf0acfb76ba27f8edb8f3bc27fe525c1f0eff1b0f5bf13ef5f43d31b5a7"
EXPECTED_GENERATED_KEYS_SHA="b007cdf128507177c695c085663005045ee9d2e185b353b8d7e2ab3682900c60"
EXPECTED_GENERATED_USB_SHA="b3cb81d2d655efa5e8c1facc6641bbd3f38c25cf97814c1c307c0ef643c76530"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "The locked compatibility client currently builds only on macOS arm64." >&2
  exit 1
fi
if [[ "$(uname -m)" != "arm64" ]]; then
  echo "No reviewed Intel compatibility-client build exists; refusing an unverified build." >&2
  exit 1
fi
if ! git -C "$CHECKOUT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Missing active submodule. Run: git submodule update --init --recursive" >&2
  exit 1
fi

actual_commit="$(git -C "$CHECKOUT" rev-parse HEAD)"
if [[ "$actual_commit" != "$EXPECTED_COMMIT" ]]; then
  echo "Compatibility-client commit mismatch: $actual_commit (expected $EXPECTED_COMMIT)" >&2
  exit 1
fi
actual_patch_sha="$(shasum -a 256 "$PATCH_FILE" | awk '{print $1}')"
if [[ "$actual_patch_sha" != "$EXPECTED_PATCH_SHA" ]]; then
  echo "Compatibility patch checksum mismatch: $actual_patch_sha" >&2
  exit 1
fi

current_diff_sha="$(git -C "$CHECKOUT" diff HEAD --no-ext-diff --binary | shasum -a 256 | awk '{print $1}')"
empty_sha="$(printf '' | shasum -a 256 | awk '{print $1}')"
if [[ "$current_diff_sha" == "$empty_sha" ]]; then
  git -C "$CHECKOUT" apply --check "$PATCH_FILE"
  git -C "$CHECKOUT" apply "$PATCH_FILE"
elif [[ "$current_diff_sha" != "$EXPECTED_PATCH_SHA" ]]; then
  echo "The active submodule contains changes other than the recorded compatibility patch." >&2
  exit 1
fi

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"
COMMON_FLAGS="-arch arm64 -mmacosx-version-min=$MACOSX_DEPLOYMENT_TARGET"

make -C "$CHECKOUT/client" clean
make -C "$CHECKOUT/client" lua_build proxmark3 \
  CC=clang \
  CXX=clang++ \
  LD=clang++ \
  "COMMON_FLAGS=$COMMON_FLAGS" \
  "LDFLAGS=$COMMON_FLAGS"

# Debug line tables contain build-time paths and mtimes. Release binaries do
# not ship them; stripping in place before ad-hoc signing makes the locked
# runtime reproducible across clean rebuilds.
strip -S "$CHECKOUT/client/proxmark3"
codesign --remove-signature "$CHECKOUT/client/proxmark3" 2>/dev/null || true
python3 "$ROOT_DIR/tools/normalize_macho_uuid.py" "$CHECKOUT/client/proxmark3" >/dev/null
codesign --force --sign - "$CHECKOUT/client/proxmark3"

generated_usb="$CHECKOUT/client/lualibs/usb_cmd.lua"
generated_usb_tmp="$(mktemp "$CHECKOUT/client/lualibs/.usb_cmd.XXXXXX")"
trap 'rm -f "$generated_usb_tmp"' EXIT
awk -f "$CHECKOUT/client/usb_cmd_h2lua.awk" \
  "$CHECKOUT/include/usb_cmd.h" > "$generated_usb_tmp"
generated_usb_sha="$(shasum -a 256 "$generated_usb_tmp" | awk '{print $1}')"
if [[ "$generated_usb_sha" != "$EXPECTED_GENERATED_USB_SHA" ]]; then
  echo "Generated USB command module hash mismatch: $generated_usb_sha" >&2
  exit 1
fi
mv "$generated_usb_tmp" "$generated_usb"
trap - EXIT

generated_keys="$CHECKOUT/client/lualibs/mf_default_keys.lua"
generated_keys_tmp="$(mktemp "$CHECKOUT/client/lualibs/.mf_default_keys.XXXXXX")"
trap 'rm -f "$generated_keys_tmp"' EXIT
awk -f "$CHECKOUT/client/default_keys_dic2lua.awk" \
  "$CHECKOUT/client/default_keys.dic" > "$generated_keys_tmp"
generated_keys_sha="$(shasum -a 256 "$generated_keys_tmp" | awk '{print $1}')"
if [[ "$generated_keys_sha" != "$EXPECTED_GENERATED_KEYS_SHA" ]]; then
  echo "Generated default-key module hash mismatch: $generated_keys_sha" >&2
  exit 1
fi
mv "$generated_keys_tmp" "$generated_keys"
trap - EXIT

echo "Built $CHECKOUT/client/proxmark3"
echo "Review and update packaging/compat/runtime-lock.json if the compiler changes the binary hash."
python3 "$ROOT_DIR/tools/runtime_provenance.py"
