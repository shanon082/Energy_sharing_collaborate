"""Operator-only, explicit sandbox API-user provisioning. Never prints keys.

Run with the remote virtualenv, NOT through an HTTP endpoint. Does not collect
money, migrate the database or alter users/meters. Requires a Collections
sandbox subscription from the official MTN portal.
"""
import argparse
import getpass
import os
from pathlib import Path
import stat
import uuid
import requests

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--env-file", required=True)
parser.add_argument("--provision", action="store_true")
args = parser.parse_args()
target = Path(args.env_file).expanduser()
if not args.provision:
    raise SystemExit("No calls made. Add --provision to provision ONLY MTN sandbox keys.")
if target.is_symlink() or not target.is_file() or target.resolve().is_relative_to(Path(__file__).resolve().parents[1]):
    raise SystemExit("Use the existing private environment file outside the uploaded backend.")
info = target.stat()
if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
    raise SystemExit("Private environment file must be owned by you with mode 0600.")
previous = target.read_text()
names = ("MTN_SANDBOX_SUBSCRIPTION_KEY", "MTN_SANDBOX_API_USER_ID", "MTN_SANDBOX_API_KEY")
if any(line.split("=", 1)[0].strip() in names for line in previous.splitlines() if "=" in line):
    raise SystemExit("Dedicated sandbox entries already exist. Review them privately before reprovisioning; no calls made.")
if input("Type SANDBOX to confirm a Collections TEST subscription (no production keys): ") != "SANDBOX":
    raise SystemExit("Cancelled; no calls made.")
subscription = getpass.getpass("MTN Collections sandbox subscription key (hidden): ")
if not subscription or any(char in subscription for char in "\r\n'\\"):
    raise SystemExit("Unsupported key format; no calls made.")
reference = str(uuid.uuid4())
base = "https://sandbox.momodeveloper.mtn.com"
try:
    created = requests.post(base + "/v1_0/apiuser", headers={"X-Reference-Id": reference,
        "Ocp-Apim-Subscription-Key": subscription, "Content-Type": "application/json"},
        json={"providerCallbackHost": "shanonsimon.alwaysdata.net"}, timeout=(3, 7), allow_redirects=False)
    if created.status_code != 201:
        raise ValueError
    keyed = requests.post(base + f"/v1_0/apiuser/{reference}/apikey",
        headers={"Ocp-Apim-Subscription-Key": subscription}, timeout=(3, 7), allow_redirects=False)
    data = keyed.json() if keyed.status_code == 201 else {}
    secret = data.get("apiKey") if isinstance(data, dict) else None
    if not isinstance(secret, str) or not secret or any(char in secret for char in "\r\n'\\"):
        raise ValueError
except (requests.RequestException, ValueError):
    raise SystemExit("Sandbox provisioning failed. No private file was changed. Inspect official portal/subscription; response/key bodies withheld.") from None
# Exclusive temporary file and atomic rename, both inside the private directory.
tmp = target.with_name(".backend.env.sandbox-" + uuid.uuid4().hex)
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as output:
    output.write(previous.rstrip() + "\n" + "\n".join(f"{name}='{value}'" for name, value in zip(names, (subscription, reference, secret))) + "\n")
os.replace(tmp, target)
print("Dedicated sandbox keys stored privately. No payment made. Configure the opt-in WSGI profile and reconciliation schedule next.")
