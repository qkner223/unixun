#!/usr/bin/env python3
"""Pull the stock SoC DTB out of a cas boot image.

`scripts/cas_bootimg.py --stock-dtb` wants the SoC DTB that the stock boot.img
carries in its header-v2 dtb area, index 2. This reads that area out of a
`dd`-ed /dev/block/by-name/boot, splits the concatenated DTBs and writes the
requested index.

    ./scripts/extract-stock-dtb.py boot.img --index 2 -o cas-stock.dtb
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

FDT_MAGIC = 0xD00DFEED
BOOT_MAGIC = b'ANDROID!'


def dtbs(blob: bytes) -> list[bytes]:
    """Every FDT in a concatenated blob, in order."""
    out, offset = [], 0
    while offset + 8 <= len(blob):
        magic, size = struct.unpack_from('>II', blob, offset)
        if magic != FDT_MAGIC:
            break
        if size == 0 or offset + size > len(blob):
            raise SystemExit(f'extract-stock-dtb: bogus FDT size {size} at {offset:#x}')
        out.append(blob[offset:offset + size])
        offset += size
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('boot', type=Path, help='boot.img (header v2)')
    ap.add_argument('--index', type=int, default=2, help='DTB index, default 2')
    ap.add_argument('-o', '--out', type=Path, required=True, help='output .dtb')
    args = ap.parse_args()

    data = args.boot.read_bytes()
    if data[:8] != BOOT_MAGIC:
        raise SystemExit('extract-stock-dtb: not an Android boot image')
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr,
     second_size, second_addr, tags_addr, page_size,
     header_version, os_version) = struct.unpack_from('<10I', data, 8)
    if page_size not in (2048, 4096, 8192):
        raise SystemExit(f'extract-stock-dtb: implausible page size {page_size}')
    if header_version < 2:
        raise SystemExit(f'extract-stock-dtb: header v{header_version} has no dtb area')

    # v1 block: recovery_dtbo_size, recovery_dtbo_offset, header_size; v2 adds
    # dtb_size and dtb_addr.
    base = 8 + 10 * 4 + 16 + 512 + 32 + 1024
    dtb_size, dtb_addr = struct.unpack_from('<IQ', data, base + 4 + 4 + 8 + 4)
    if dtb_size == 0:
        raise SystemExit('extract-stock-dtb: dtb_size is 0')

    pages = (kernel_size + ramdisk_size + second_size + page_size - 1) // page_size
    dtb_start = page_size + pages * page_size
    blob = data[dtb_start:dtb_start + dtb_size]
    found = dtbs(blob)
    if not found:
        raise SystemExit(f'extract-stock-dtb: no FDT at {dtb_start:#x}')
    print(f'extract-stock-dtb: {len(found)} DTB(s) in the area, sizes '
          + ', '.join(str(len(d)) for d in found))
    if args.index >= len(found):
        raise SystemExit(f'extract-stock-dtb: index {args.index} out of range')
    chosen = found[args.index]
    args.out.write_bytes(chosen)
    print(f'extract-stock-dtb: wrote {args.out} ({len(chosen)} bytes, index {args.index})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
