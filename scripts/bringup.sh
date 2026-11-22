#!/bin/sh
# Boot a built cas image and collect the first evidence.
#
#   ./scripts/bringup.sh /path/to/boot.img
#
# Needs a host with a USB controller the kernel exposes (/dev/bus/usb) and the
# Android platform-tools. Run it from the UniXNU checkout, or pass an absolute
# image path from anywhere.
set -eu
IMG=${1:?usage: bringup.sh /path/to/boot.img}
OUT=${2:-logs/bringup-$(date +%Y%m%d-%H%M%S)}
mkdir -p "$OUT"

say() { printf '== %s\n' "$*"; }

say "host"
{ uname -a; lsusb; } > "$OUT/host.txt" 2>&1 || true

say "fastboot"
if ! fastboot devices | grep -q .; then
  echo "bringup: no fastboot device." >&2
  echo "  cas: power + volume-down, or 'adb reboot bootloader' from a rooted boot." >&2
  echo "  host: /dev/bus/usb must exist and the user must be in plugdev." >&2
  exit 1
fi
fastboot devices | tee "$OUT/fastboot-devices.txt"
fastboot getvar all > "$OUT/fastboot-getvar.txt" 2>&1 || true

say "boot (temporary; nothing is written to flash)"
fastboot boot "$IMG" 2>&1 | tee "$OUT/fastboot-boot.txt"

say "waiting for the device to come back"
# Two outcomes: UniXNU/XNU hangs (device stays in fastboot or reboots to nothing),
# or the payload exits and Android boots again, where pstore holds the kernel log.
for i in $(seq 1 60); do
  sleep 5
  if adb devices | grep -qw device; then
    echo "android is back after ~$((i*5))s"
    "$(dirname "$0")/grab-logs.sh" "$OUT/adb" || true
    break
  fi
  if fastboot devices | grep -q .; then
    echo "still in fastboot after ~$((i*5))s"
  fi
done

say "result"
ls -l "$OUT"
echo "bringup: saved to $OUT"
