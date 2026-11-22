#!/bin/sh
# Pull every log this port can leave behind, from a rooted cas over adb.
#
#   ./scripts/grab-logs.sh [OUTDIR] [SERIAL]
#
# Works over USB or over `adb connect IP:5555`; nothing here needs fastboot.
set -eu
OUT=${1:-logs/$(date +%Y%m%d-%H%M%S)}
SERIAL=${2:-}
A="adb"
[ -n "$SERIAL" ] && A="adb -s $SERIAL"
mkdir -p "$OUT"

say() { printf '== %s\n' "$*"; }

say "device"
$A shell getprop ro.product.device > "$OUT/getprop.device" 2>&1 || true
$A shell getprop ro.build.fingerprint > "$OUT/getprop.fingerprint" 2>&1 || true
$A shell uname -a > "$OUT/uname.txt" 2>&1 || true
$A shell cat /proc/cmdline > "$OUT/cmdline.txt" 2>&1 || true

say "root"
$A root >/dev/null 2>&1 || true
sleep 2
$A wait-for-device 2>/dev/null || true

say "dmesg (current boot)"
$A shell dmesg > "$OUT/dmesg.txt" 2>&1 || true

say "pstore / ramoops (previous crashes)"
$A shell 'ls -l /sys/fs/pstore' > "$OUT/pstore-list.txt" 2>&1 || true
$A shell 'for f in /sys/fs/pstore/*; do echo "### $f"; cat "$f"; echo; done' > "$OUT/pstore.txt" 2>&1 || true
$A shell 'cat /proc/last_kmsg' > "$OUT/last_kmsg.txt" 2>&1 || true

say "cas GPT (userdata extents)"
$A shell 'command -v sgdisk >/dev/null && sgdisk -p /dev/block/sda || cat /proc/partitions' > "$OUT/gpt.txt" 2>&1 || true

say "kernel messages from the UniXNU payload mailbox"
# patches/xnu has no reader of its own; the NC mailbox at 0x9f960000 is mapped by
# the firmware, and /dev/mem on a rooted Android can read it while Android runs.
$A shell 'if [ -r /dev/mem ]; then dd if=/dev/mem bs=1 skip=$((0x9f960000)) count=512 2>/dev/null | xxd; fi' \
  > "$OUT/mailbox.txt" 2>&1 || true

say "result"
ls -l "$OUT"
echo "grab-logs: saved to $OUT"
echo "grab-logs: mail any of these back; dmesg.txt + pstore.txt carry the kernel's last words"
