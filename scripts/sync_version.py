#!/usr/bin/env python3
"""Sync version from VERSION file to all files that embed the version string.

Run from any directory. Only rewrites files that are out of date.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
VERSION = ROOT.joinpath("VERSION").read_text().strip()

if not VERSION:
    print("ERROR: VERSION file is empty", file=sys.stderr)
    sys.exit(1)


def patch(path, pattern, replacement):
    text = path.read_text()
    new_text = re.sub(pattern, replacement, text)
    if new_text == text:
        print(f"  {path.relative_to(ROOT)}: already {VERSION}")
    else:
        path.write_text(new_text)
        print(f"  {path.relative_to(ROOT)}: -> {VERSION}")


print(f"sync_version: {VERSION}")

# firmware/src/main.cpp: Serial.println("version=X.Y.Z")
patch(
    ROOT / "firmware/src/main.cpp",
    r'(Serial\.println\("version=)[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# service/linapse/state.py: service_version = "X.Y.Z"
patch(
    ROOT / "service/linapse/state.py",
    r'(service_version\s*=\s*")[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# installer.iss: AppVersion=X.Y.Z
patch(
    ROOT / "installer.iss",
    r'(?m)^(AppVersion=).*',
    rf'\g<1>{VERSION}',
)

# configurator/package.json: "version": "X.Y.Z"
patch(
    ROOT / "configurator/package.json",
    r'("version"\s*:\s*")[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# extension/package.json: "version": "X.Y.Z"
patch(
    ROOT / "extension/package.json",
    r'("version"\s*:\s*")[^"]+(")',
    rf'\g<1>{VERSION}\g<2>',
)

# fedora/linapse-cad-mouse.spec: Version:        X.Y.Z
patch(
    ROOT / "fedora/linapse-cad-mouse.spec",
    r'(?m)^(Version:\s*).*',
    rf'\g<1>{VERSION}',
)

# debian/changelog needs a written entry, so do not make one here. The PPA
# release builds the version from the first entry, and it fails if that
# version is not the same as VERSION.
deb_first = ROOT.joinpath("debian/changelog").read_text().splitlines()[0]
deb_match = re.match(r'\S+ \(([^)-]+)', deb_first)
if not deb_match or deb_match.group(1) != VERSION:
    found = deb_match.group(1) if deb_match else "none"
    print(f"  WARNING: debian/changelog starts with {found}, not {VERSION}. "
          "Add a debian/changelog entry for this version.", file=sys.stderr)

print("done")
