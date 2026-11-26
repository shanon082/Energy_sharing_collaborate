"""Compile one explicit gPawa profile. The supplied FQBN is never modified."""
import argparse
import subprocess
from pathlib import Path


def profile_flags(profile, polarity=None):
    flags = {
        'GPAWA_WIFI_TEST': 0,
        'GPAWA_RELAY_DIAGNOSTIC': int(profile == 'relay-diagnostic'),
        'GPAWA_PZEM_DIAGNOSTIC': int(profile == 'pzem-diagnostic'),
        'GPAWA_AUTH_CREDIT_ONLY': 0,
        'GPAWA_USB_EXERCISE': 0,
        'GPAWA_COMMISSIONED_OUTPUT': int(profile == 'commissioned'),
        'GPAWA_RELAY_COMMISSIONING_APPROVED': int(profile == 'commissioned'),
    }
    if profile == 'commissioned':
        if polarity not in ('HIGH', 'LOW'):
            raise ValueError('Commissioned builds require the measured active level.')
        flags['GPAWA_RELAY_ACTIVE_LEVEL'] = int(polarity == 'HIGH')
    elif polarity:
        raise ValueError('Only the commissioned profile takes a relay active level.')
    return ' '.join(f'-D{name}={value}' for name, value in flags.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', choices=('pzem-diagnostic', 'relay-diagnostic', 'metered', 'commissioned'))
    parser.add_argument('--relay-active-level', choices=('HIGH', 'LOW'))
    parser.add_argument('--flags-only', action='store_true')
    parser.add_argument('--fqbn')
    parser.add_argument('--cli', default='arduino-cli')
    parser.add_argument('--config-file', type=Path)
    parser.add_argument('--sketch', type=Path, default=Path(__file__).resolve().parent / 'GpawaAC')
    parser.add_argument('--libraries', type=Path)
    parser.add_argument('--build-path', type=Path)
    parser.add_argument('--windows-paths', action='store_true', help='Translate WSL paths for the Windows CLI.')
    args = parser.parse_args()
    try:
        flags = profile_flags(args.profile, args.relay_active_level)
    except ValueError as exc:
        parser.error(str(exc))
    print(f'{args.profile} {flags}', flush=True)
    if args.flags_only:
        return
    if not args.fqbn or not args.build_path:
        parser.error('Compile requires an explicit --fqbn and a scratch --build-path.')
    if not (args.sketch / 'GpawaAC.ino').is_file():
        parser.error('Sketch folder must contain GpawaAC.ino.')

    def tool_path(path):
        resolved = str(path.resolve())
        if args.windows_paths:
            return subprocess.check_output(['wslpath', '-w', resolved], text=True).strip()
        return resolved

    command = [args.cli]
    if args.config_file:
        command += ['--config-file', tool_path(args.config_file)]
    command += ['compile', '--fqbn', args.fqbn, '--jobs', '2', '--build-path', tool_path(args.build_path),
                '--build-property', f'compiler.cpp.extra_flags={flags}']
    if args.libraries:
        command += ['--libraries', tool_path(args.libraries)]
    # Windows compiler recipes spawn cmd.exe, which requires a drive-backed
    # working directory. Use the caller's staged sketch directory in WSL mode.
    result = subprocess.run([*command, tool_path(args.sketch)],
                            cwd=args.sketch.resolve().parent if args.windows_paths else None)
    if result.returncode:
        parser.exit(result.returncode, f'{args.profile} compilation failed.\n')


if __name__ == '__main__':
    main()
