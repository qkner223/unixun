#!/bin/sh
# Install the device-provided OS profile into the UniXNU checkout.
#
# board.os_profile names a directory under UniXNU/profiles/os/. Upstream UniXNU
# ships ipados-17.7.11-21H461 only, so the ios-16.5-20F66 profile travels with
# this repository and is copied in before any resolve step.
#
#   ./scripts/install-profile.sh /path/to/UniXNU
#
# Re-run after editing os-profiles/. The copy is replaced, never merged.
set -eu

UNIXNU=${1:-../UniXNU}
DEV=$(cd "$(dirname "$0")/.." && pwd)

test -d "$UNIXNU" || { echo "install-profile: $UNIXNU is not a directory" >&2; exit 1; }
test -f "$UNIXNU/unixnu" || { echo "install-profile: $UNIXNU/unixnu missing" >&2; exit 1; }

profile=$(python3 -c "import tomllib;print(tomllib.load(open('$DEV/board.toml','rb'))['board']['os_profile'])")
src="$DEV/os-profiles/$profile"
test -f "$src/profile.toml" || { echo "install-profile: $src/profile.toml missing" >&2; exit 1; }

mkdir -p "$UNIXNU/profiles/os"
rm -rf "$UNIXNU/profiles/os/$profile"
cp -R "$src" "$UNIXNU/profiles/os/$profile"
test -f "$UNIXNU/profiles/os/$profile/profile.toml"

echo "install-profile: installed $profile into $UNIXNU/profiles/os/$profile"
