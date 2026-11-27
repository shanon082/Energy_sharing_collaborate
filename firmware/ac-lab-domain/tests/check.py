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
firmware = (args.sketch or root / 'GpawaAC') / 'Firmware.cpp'
key_handler = firmware.read_text().split('void handleKey() {', 1)[1]
assert key_handler.lstrip().startswith("char k = keypad.getKey();\n  if (!k || k == 'D') return;"), 'D must exit before any keypad side effects'
if not (args.arduinojson / 'ArduinoJson.h').is_file():
    raise SystemExit('Provide existing ArduinoJson headers with --arduinojson')
with tempfile.TemporaryDirectory(prefix='gpawa-domain-cpp-') as directory:
    target = Path(directory)
    source = root
    if args.sketch:
        source = target / 'source'
        (source / 'tests').mkdir(parents=True)
        (source / 'GpawaAC').mkdir()
        for name in ('Protocol.h', 'MeterCore.h', 'PzemFrame.h', 'HardwareConfig.h', 'SafeDiagnostics.h', 'BuzzerCore.h', 'RecoveryCore.h'):
            shutil.copyfile(args.sketch / name, source / 'GpawaAC' / name)
        for name in ('recovery.cpp', 'domain_protocol.cpp', 'credit_only.cpp', 'diagnostics.cpp', 'buzzer.cpp', 'protocol-vectors.h'):
            shutil.copyfile(root / 'tests' / name, source / 'tests' / name)
    for name in ('recovery', 'domain_protocol', 'credit_only', 'diagnostics', 'buzzer'):
        subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-I', str(args.arduinojson), '-I', str(source / 'GpawaAC'),
                        str(source / 'tests' / (name + '.cpp')),
                        '-o', str(target / name)], check=True)
        subprocess.run([str(target / name)], check=True)
    fixture = target / 'output_guard.cpp'
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\n'
                       'static_assert(GPAWA_USB_EXERCISE == 0);\n'
                       'static_assert(hw::PZEM_ADDR == 0x01);\n'
                       'static_assert(hw::EMPTY_ALARM_MS == 120000);\nint main() {}\n')
    command = ['g++', '-std=c++17', '-I', str(source / 'GpawaAC'), str(fixture), '-o', str(target / 'guard')]
    subprocess.run(command, check=True)
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_PZEM_DIAGNOSTIC == 0);\n'
                       'static_assert(GPAWA_AUTH_CREDIT_ONLY == 0);\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\nint main() {}\n')
    subprocess.run(command + ['-DGPAWA_PZEM_DIAGNOSTIC=0'], check=True)
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_RELAY_DIAGNOSTIC == 0);\n'
                       'static_assert(GPAWA_PZEM_DIAGNOSTIC == 1);\n'
                       'static_assert(GPAWA_AUTH_CREDIT_ONLY == 0);\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\nint main() {}\n')
    subprocess.run(command, check=True)
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_RELAY_DIAGNOSTIC == 1);\n'
                       'static_assert(GPAWA_PZEM_DIAGNOSTIC == 0);\n'
                       'static_assert(GPAWA_AUTH_CREDIT_ONLY == 0);\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\nint main() {}\n')
    subprocess.run(command + ['-DGPAWA_RELAY_DIAGNOSTIC=1', '-DGPAWA_PZEM_DIAGNOSTIC=0',
                              '-DGPAWA_AUTH_CREDIT_ONLY=0'], check=True)
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 0);\n'
                       'static_assert(GPAWA_USB_EXERCISE == 0);\nint main() {}\n')
    relay_flags = ['-DGPAWA_RELAY_DIAGNOSTIC=1', '-DGPAWA_PZEM_DIAGNOSTIC=0',
                   '-DGPAWA_AUTH_CREDIT_ONLY=0']
    for flags, expected in [(['-DGPAWA_COMMISSIONED_OUTPUT=1'], 'Physical output requires an explicitly measured relay active level'),
                            (relay_flags + ['-DGPAWA_USB_EXERCISE=1'], 'Relay diagnostics require a separate'),
                            (relay_flags + ['-DGPAWA_WIFI_TEST=1'], 'Relay diagnostics require a separate'),
                            (relay_flags + ['-DGPAWA_AUTH_CREDIT_ONLY=1'], 'Relay diagnostics cannot run'),
                            (['-DGPAWA_RELAY_DIAGNOSTIC=0', '-DGPAWA_PZEM_DIAGNOSTIC=1',
                              '-DGPAWA_AUTH_CREDIT_ONLY=1'], 'PZEM diagnostics require a separate')]:
        result = subprocess.run(command + flags, text=True, capture_output=True)
        if result.returncode == 0 or expected not in result.stderr:
            raise SystemExit('FAIL: unsafe mode was not rejected')
    subprocess.run(command + ['-DGPAWA_AUTH_CREDIT_ONLY=1', '-DGPAWA_RELAY_DIAGNOSTIC=0',
                              '-DGPAWA_PZEM_DIAGNOSTIC=0'], check=True)
    subprocess.run(command + ['-DGPAWA_AUTH_CREDIT_ONLY=0', '-DGPAWA_RELAY_DIAGNOSTIC=0',
                              '-DGPAWA_PZEM_DIAGNOSTIC=0', '-DGPAWA_WIFI_TEST=1'], check=True)
    for level in ('0', '1'):
        subprocess.run(command + ['-DGPAWA_RELAY_DIAGNOSTIC=0', '-DGPAWA_RELAY_ACTIVE_LEVEL=' + level], check=True)
    fixture.write_text('#include "HardwareConfig.h"\n'
                       'static_assert(GPAWA_COMMISSIONED_OUTPUT == 1);\n'
                       'static_assert(GPAWA_AUTH_CREDIT_ONLY == 0);\n'
                       'static_assert(GPAWA_PZEM_DIAGNOSTIC == 0);\nint main() {}\n')
    for level in ('0', '1'):
        subprocess.run(command + ['-DGPAWA_COMMISSIONED_OUTPUT=1', '-DGPAWA_AUTH_CREDIT_ONLY=0',
                                  '-DGPAWA_PZEM_DIAGNOSTIC=0', '-DGPAWA_RELAY_ACTIVE_LEVEL=' + level,
                                  '-DGPAWA_RELAY_COMMISSIONING_APPROVED=1'], check=True)
    result = subprocess.run(command + ['-DGPAWA_COMMISSIONED_OUTPUT=1', '-DGPAWA_AUTH_CREDIT_ONLY=0',
                                       '-DGPAWA_PZEM_DIAGNOSTIC=0', '-DGPAWA_RELAY_ACTIVE_LEVEL=0'],
                            text=True, capture_output=True)
    if result.returncode == 0 or 'Physical output requires an explicit commissioning approval flag' not in result.stderr:
        raise SystemExit('FAIL: output was accepted without explicit commissioning approval')
    result = subprocess.run(command + ['-DGPAWA_COMMISSIONED_OUTPUT=1', '-DGPAWA_AUTH_CREDIT_ONLY=1',
                                       '-DGPAWA_RELAY_ACTIVE_LEVEL=0'], text=True, capture_output=True)
    if result.returncode == 0 or 'Authenticated credit-only mode cannot enable' not in result.stderr:
        raise SystemExit('FAIL: output was not blocked in credit-only mode')
    result = subprocess.run(command + ['-DGPAWA_RELAY_ACTIVE_LEVEL=2'], text=True, capture_output=True)
    if result.returncode == 0 or 'GPAWA_RELAY_ACTIVE_LEVEL must be 0' not in result.stderr:
        raise SystemExit('FAIL: invalid relay polarity was accepted')
print('PASS: authenticated/diagnostic isolation, explicit relay polarity validation and disabled-by-default output gates')
