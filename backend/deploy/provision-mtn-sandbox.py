"""Operator-only, explicit sandbox API-user provisioning. Never prints keys.

Run with the remote virtualenv, NOT through an HTTP endpoint. Does not collect
money, migrate the database or alter users/meters. Requires a Collections
sandbox subscription from the official MTN portal.
"""
import argparse
import getpass
import json
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
recovery = target.with_name(".mtn-sandbox-provisioning.json")
if recovery.exists() or recovery.is_symlink():
    raise SystemExit("Unresolved provisioning recovery record exists in the private directory. "
                     "Inspect it privately and resolve remote state using the runbook before retrying; no calls made.")
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
# Persist the reference BEFORE any request: a lost response can still mean success.
# Never print this API-user identifier, subscription, key, or exception text.
def save_recovery(state, *, initial=False):
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if initial else os.O_TRUNC) | os.O_NOFOLLOW
    fd = os.open(recovery, flags, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump({"api_user_reference": reference, "state": state}, output)
        output.flush()
        os.fsync(output.fileno())


# Exact membership only: no messages, descriptions, headers, or arbitrary codes.
# MTN's official Common Error Codes; unknown codes are deliberately withheld.
ERROR_CODES = frozenset({"RESOURCE_ALREADY_EXIST", "INVALID_CALLBACK_URL_HOST",
                         "INVALID_CURRENCY", "SERVICE_UNAVAILABLE"})


def provider_code(response):
    try:
        body = response.json()
    except ValueError:
        return "withheld_or_unavailable"
    if isinstance(body, dict):
        for field in ("code", "errorCode"):
            code = body.get(field)
            if isinstance(code, str) and code in ERROR_CODES:
                return code
    return "withheld_or_unavailable"


def fail(kind, response=None):
    status = str(response.status_code) if response is not None else "unavailable"
    code = provider_code(response) if response is not None else "unavailable"
    remote = ("API user creation was confirmed; API key may have been created."
              if stage == "API-key creation" else
              "Remote API user creation is unconfirmed; a user may still have been created.")
    raise SystemExit(
        f"Sandbox provisioning failed: stage={stage}; category={kind}; "
        f"HTTP status={status}; provider code={code}. No private environment file was changed. "
        f"{remote} Recovery reference retained in the private directory. "
        "Resolve remote state via the runbook/official MTN support before retrying. "
        "Credentials, headers and response bodies withheld."
    ) from None


try:
    save_recovery("API-user creation outcome unknown", initial=True)
except OSError:
    raise SystemExit("Cannot create private recovery record; no calls made.") from None
stage = "API-user creation"
try:
    created = requests.post(base + "/v1_0/apiuser", headers={"X-Reference-Id": reference,
        "Ocp-Apim-Subscription-Key": subscription, "Content-Type": "application/json"},
        json={"providerCallbackHost": "shanonsimon.alwaysdata.net"}, timeout=(3, 7), allow_redirects=False)
    if created.status_code != 201:
        fail("HTTP rejection", created)
    stage = "API-key creation"
    save_recovery("API user confirmed; API-key creation outcome unknown")
    keyed = requests.post(base + f"/v1_0/apiuser/{reference}/apikey",
        headers={"Ocp-Apim-Subscription-Key": subscription}, timeout=(3, 7), allow_redirects=False)
    if keyed.status_code != 201:
        fail("HTTP rejection", keyed)
    try:
        data = keyed.json()
    except ValueError:
        fail("invalid success response", keyed)
    secret = data.get("apiKey") if isinstance(data, dict) else None
    if not isinstance(secret, str) or not secret or any(char in secret for char in "\r\n'\\"):
        fail("invalid success response", keyed)
except requests.exceptions.SSLError:
    fail("TLS error")
except requests.exceptions.Timeout:
    fail("network timeout")
except requests.exceptions.ConnectionError:
    fail("network connection error")
except requests.RequestException:
    fail("network/request error")
except OSError:
    fail("private recovery record write error")
# Exclusive temporary file and atomic rename, both inside the private directory.
tmp = target.with_name(".backend.env.sandbox-" + uuid.uuid4().hex)
try:
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(previous.rstrip() + "\n" + "\n".join(f"{name}='{value}'" for name, value in zip(names, (subscription, reference, secret))) + "\n")
        output.flush()
        os.fsync(output.fileno())
    os.replace(tmp, target)
except OSError:
    raise SystemExit("Private environment save failed after remote user/key creation. "
                     "Recovery record retained; a private temporary file may contain keys. "
                     "Inspect files privately and resolve remote state before retrying; no secrets printed.") from None
try:
    recovery.unlink()
except OSError:
    raise SystemExit("Sandbox keys stored privately, but recovery record cleanup failed. "
                     "Inspect privately; do not reprovision.") from None
print("Dedicated sandbox keys stored privately. No payment made. Configure the opt-in WSGI profile and reconciliation schedule next.")
