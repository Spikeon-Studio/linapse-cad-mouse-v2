#!/usr/bin/env bash
# Build a Safari Web Extension Xcode project from the Chrome build output.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Safari Web Extension builds require macOS and Xcode."
  exit 1
fi

command -v xcrun >/dev/null || { echo "Xcode command line tools are required."; exit 1; }

npm --prefix "$EXT_DIR" run build

CHROME_DIR="$EXT_DIR/dist/chrome"
OUT_DIR="$EXT_DIR/dist/safari-xcode"

rm -rf "$OUT_DIR"
xcrun safari-web-extension-converter "$CHROME_DIR" \
  --project-location "$OUT_DIR" \
  --app-name "Linapse Browser Connector" \
  --bundle-identifier "com.linapse.browser-connector" \
  --copy-resources

echo "Safari Xcode project created at: $OUT_DIR"
echo "Open the project in Xcode, sign with your Apple Developer team, then archive for distribution."
