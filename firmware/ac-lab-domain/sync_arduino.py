"""Stage canonical public source and an inhibited Arduino IDE profile."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import shutil
import tempfile

from build_profile import profile_flags


PUBLIC = (
    'BuzzerCore.h', 'DeviceConfig.example.h', 'DeviceDomain.h', 'Firmware.cpp',
    'GpawaAC.ino', 'HardwareConfig.h', 'MeterCore.h', 'NetworkConfig.example.h',
    'Protocol.h', 'PzemFrame.h', 'RecoveryCore.h', 'SafeDiagnostics.h', 'WifiCheck.cpp',
)
SOURCE_SUFFIXES = {'.c', '.cc', '.cpp', '.cxx', '.s', '.ino', '.pde'}


def digest(path):
    return sha256(path.read_bytes()).digest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    destination = args.destination.resolve()
    source = Path(__file__).resolve().parent / 'GpawaAC'
    if destination.name != 'GpawaAC' or destination == source or not (destination / 'GpawaAC.ino').is_file():
        parser.error('Choose the existing external GpawaAC sketch folder.')
    active = [*destination.iterdir(), *(destination / 'src').rglob('*')]
    stale = [p.relative_to(destination) for p in active
             if p.is_file() and p.suffix.lower() in SOURCE_SUFFIXES
             and (p.parent != destination or p.name not in PUBLIC)]
    if stale:
        parser.error('Unexpected active source files require review: ' + ', '.join(map(str, stale)))
    payloads = {name: (source / name).read_bytes() for name in PUBLIC}
    payloads['build_opt.h'] = ('\n'.join(profile_flags('metered').split()) + '\n').encode()
    private = {p: digest(p) for p in active if p.is_file() and p.name not in payloads}
    changes = {name: content for name, content in payloads.items()
               if not (destination / name).is_file() or (destination / name).read_bytes() != content}
    for name in sorted(changes):
        print(('Backup and replace' if (destination / name).exists() else 'Add') + f' {name}')
    print('IDE profile:', profile_flags('metered'))
    if not args.apply or not changes:
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path(tempfile.mkdtemp(prefix=f'GpawaAC-public-backup-{stamp}-', dir=destination.parent))
    for name in changes:
        existing = destination / name
        if existing.is_file():
            shutil.copy2(existing, backup / name)
    print('Public backup:', backup)
    for name, content in changes.items():
        target = destination / name
        with tempfile.NamedTemporaryFile(prefix='.gpawa-public-', dir=destination, delete=False) as staged:
            staged.write(content)
        Path(staged.name).replace(target)
    if any((destination / name).read_bytes() != content for name, content in payloads.items()):
        raise SystemExit('Public copy verification failed.')
    if any(digest(path) != saved for path, saved in private.items()):
        raise SystemExit('A preserved file changed while staging.')
    print('Verified canonical public source, inhibited IDE options, and byte-identical preserved files.')


if __name__ == '__main__':
    main()
