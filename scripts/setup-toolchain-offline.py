#!/usr/bin/env python3
"""Run UniXNU's setup-toolchain.py while sourcing every GitHub tree from codeload.

`git fetch --depth 1 <url> <ref>` through the proxy in front of github.com stalls
on the large and the long-lived repositories (llvm-project, libdispatch); the
codeload tarball of the same commit or tag arrives in seconds. Everything else --
patches, cmake flags, the cctools/mig/iig/lzfse steps and the shims -- stays the
upstream script's own code.
"""
import importlib.util
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / 'UnixNU'
SCRIPT = HERE / 'scripts/linux/setup-toolchain.py'
CACHE = Path('/var/tmp/tarballs')

spec = importlib.util.spec_from_file_location('setup_toolchain', SCRIPT)
mod = importlib.util.module_from_spec(spec)
sys.modules['setup_toolchain'] = mod
spec.loader.exec_module(mod)

orig_git_checkout = mod.git_checkout


def fetch_tarball(url, ref):
    """Return a tarball path for github.com/<owner>/<repo> at <ref>, or None."""
    match = re.search(r'github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?$', url)
    if not match:
        return None
    owner, repo = match.group(1), match.group(2)
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f'{repo}-{ref}.tar.gz'
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    for candidate in (ref, f'refs/tags/{ref}'):
        tarball = f'https://codeload.github.com/{owner}/{repo}/tar.gz/{candidate}'
        print(f'+ codeload {tarball}', flush=True)
        tmp = dest.with_suffix('.part')
        try:
            with urllib.request.urlopen(tarball, timeout=900) as response, tmp.open('wb') as out:
                shutil.copyfileobj(response, out)
        except Exception as error:                     # noqa: BLE001 - try the tag form next
            print(f'  {error}', flush=True)
            tmp.unlink(missing_ok=True)
            continue
        tmp.rename(dest)
        return dest
    return None


def git_checkout(directory, url, ref):
    tarball = fetch_tarball(url, ref)
    if tarball is None:
        return orig_git_checkout(directory, url, ref)
    dest = Path(directory)
    dest.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(dir='/var/tmp', prefix='unixnu-src-'))
    try:
        with tarfile.open(tarball) as tar:
            tar.extractall(work, filter='data')
        inner = next(work.iterdir())
        for item in inner.iterdir():
            shutil.move(str(item), str(dest / item.name))
    finally:
        shutil.rmtree(work, ignore_errors=True)
    # `git -C <src> apply <patch>` and cctools' own scripts expect a work tree.
    mod.run(['git', 'init', '-q', dest])
    mod.run(['git', '-C', dest, 'add', '-A'])
    mod.run(['git', '-C', dest, '-c', 'user.email=unixnu@localhost', '-c', 'user.name=unixnu',
             'commit', '-qm', f'{ref} from codeload'])
    print(f'+ staged {dest.name} at {ref} from {tarball.name}', flush=True)


mod.git_checkout = git_checkout
sys.argv = ['setup-toolchain.py', *sys.argv[1:]]
raise SystemExit(mod.main())
