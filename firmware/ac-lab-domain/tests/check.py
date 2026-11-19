"""Compile/run public core/contract tests only; no networking or device calls."""
import argparse
from pathlib import Path
import subprocess
import tempfile
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('--arduinojson', type=Path, default=Path(
    '/mnt/c/Users/USER/OneDrive/Documents/Arduino/libraries/ArduinoJson/src'))
parser.add_argument('--sketch', type=Path, help='Existing sketch public headers; read only')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
if not (args.arduinojson / 'ArduinoJson.h').is_file():
    raise SystemExit('Provide existing ArduinoJson headers with --arduinojson')
with tempfile.TemporaryDirectory(prefix='gpawa-domain-cpp-') as directory:
    target = Path(directory)
    source = root
    if args.sketch:
        source = target / 'source'
        (source / 'tests').mkdir(parents=True)
        (source / 'GpawaAC').mkdir()
        for name in ('Protocol.h', 'MeterCore.h', 'PzemFrame.h', 'HardwareConfig.h'):
            shutil.copyfile(args.sketch / name, source / 'GpawaAC' / name)
        for name in ('recovery.cpp', 'domain_protocol.cpp', 'credit_only.cpp', 'protocol-vectors.h'):
            shutil.copyfile(root / 'tests' / name, source / 'tests' / name)
    for name in ('recovery', 'domain_protocol', 'credit_only'):
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-I', str(args.arduinojson), str(source / 'tests' / (name + '.cpp')),
                        '-o', str(target / name)], check=True)
        subprocess.run([str(target / name)], check=True)
    fixture = target / 'output_guard.cpp'
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\n'
                       'static_assert(GPAWA_USB_EXERCISE == 0);\nint main() {}\n')
    command = ['g++', '-std=c++17', '-I', str(source / 'GpawaAC'), str(fixture), '-o', str(target / 'guard')]
    subprocess.run(command, check=True)
    for flags, expected in [(['-DGPAWA_COMMISSIONED_OUTPUT=1'], 'Physical relay output is forbidden'),
                            (['-DGPAWA_USB_EXERCISE=1'], 'Authenticated credit-only mode cannot enable'),
                            (['-DGPAWA_WIFI_TEST=1'], 'Authenticated credit-only mode cannot enable')]:
        result = subprocess.run(command + flags, text=True, capture_output=True)
        if result.returncode == 0 or expected not in result.stderr:
            raise SystemExit('FAIL: unsafe mode was not rejected')
    subprocess.run(command + ['-DGPAWA_AUTH_CREDIT_ONLY=0', '-DGPAWA_WIFI_TEST=1'], check=True)
print('PASS: authenticated/diagnostic mode separation and compile-time relay prohibition')
