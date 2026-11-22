#!/usr/bin/env python3
"""Drop ArmCpu's board sleep hook, which cas has no provider for.

Upstream ArmCpu (5f37026 and later) declares

    extern "C" void (*arm64_platform_sleep_hook)(boolean_t) __attribute__((weak_import));

defines `static void armcpuPlatformSleep(boolean_t)`, and installs the pointer
from `start()`. The symbol is supplied by the SM8550 platform power patch
(`sheng-platform-power.patch`). cas runs SM8250, whose SoC series is empty, so
nothing defines it and the kernel link fails with

    Undefined symbols for architecture arm64:
      "_arm64_platform_sleep_hook", referenced from ArmCpu::start

ld64 from cctools-port does not honour weak_import through a -force_load
archive here, so the reference has to go; the now-unused static function then
trips -Werror,-Wunused-function and has to go with it. Only board-level suspend
is lost, which cas does not have yet.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

tree = Path(__file__).resolve().parents[1]
source = tree / 'drivers/ArmCpu/ArmCpu.cpp'
if not source.is_file():
    raise SystemExit(f'cas-armcpu-sleep-hook: {source} missing; run "unixnu tree" first')

text = source.read_text()
original = text

# 1. the weak import
text = re.sub(r'(?m)^\s*extern "C" void \(\*arm64_platform_sleep_hook\).*\n', '', text)

# 2. the install site inside start()
text = re.sub(
    r'(?ms)^\s*if \(sleep == 1 && &arm64_platform_sleep_hook && !skipGic && psciConduit \(&gSleepHvc\)\) \{.*?^\s*\}\n',
    '\t/* cas: no board sleep hook on SM8250; platform suspend stays disabled. */\n',
    text)

# 3. the statics that only the install site used: mark them unused instead of
#    deleting them, so forward declarations and definitions stay consistent and
#    -Werror,-Wunused-function is satisfied.
text = re.sub(
    r'(?m)^(\s*static void )(armcpuPlatformSleep|sleepCoreOff|sleepBootWait)(\b)',
    r'\1__attribute__((unused)) \2\3',
    text)

if text == original:
    print('cas-armcpu-sleep-hook: nothing to change (already patched?)')
else:
    source.write_text(text)
    print(f'cas-armcpu-sleep-hook: removed the sleep hook from {source}')

code_uses = [line.strip() for line in source.read_text().splitlines()
             if 'arm64_platform_sleep_hook' in line
             and not line.lstrip().startswith(('//', '*', '/*'))]
if code_uses:
    sys.exit('cas-armcpu-sleep-hook: still used: ' + '; '.join(code_uses))
print('cas-armcpu-sleep-hook: no code reference left')
