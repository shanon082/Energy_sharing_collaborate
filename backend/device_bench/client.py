"""SOFTWARE DEVICE ONLY. Durable SQLite journal; no GPIO, radio, PIN or hardware.

Run with the backend virtualenv. Credentials come only from BENCH_DEVICE_TOKEN.
Numeric keypad tokens are prompted without echo; never CLI arguments/log output.
"""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import uuid
from urllib.parse import urlsplit


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class DurableDevice:
    def __init__(self, path, device_id, *, initialize=False):
        path = Path(path)
        exists = path.exists()
        if not exists and not initialize:
            raise ValueError("Journal missing. Do not recreate it after device use; reconcile or provision a new binding.")
        if exists and initialize:
            raise ValueError("Journal already exists; initialize is allowed only for a new unused binding.")
        self.db = sqlite3.connect(path, isolation_level=None)
        os.chmod(path, 0o600)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS state (id INTEGER PRIMARY KEY CHECK(id=1), device TEXT, storage TEXT, counter INTEGER, applied INTEGER, remaining INTEGER, consumed INTEGER)")
        self.db.execute("CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, payload TEXT, receipt TEXT, acked INTEGER DEFAULT 0)")
        if not exists:
            self.db.execute("INSERT INTO state VALUES (1, ?, ?, 0, 0, 0, 0)", (str(device_id), str(uuid.uuid4())))
        if self.db.execute("SELECT device FROM state WHERE id=1").fetchone()[0] != str(device_id):
            raise ValueError("Device identity does not match persistent journal.")
        self.device_id = str(device_id)
        self.initializing = not exists

    def handshake(self):
        storage, counter = self.db.execute("SELECT storage,counter FROM state WHERE id=1").fetchone()
        return {"contract_version": 1, "storage_id": storage, "initialize": self.initializing, "application_counter": counter}

    def apply(self, command):
        value = dict(command)
        supplied = value.pop("payload_digest", None)
        storage = self.db.execute("SELECT storage FROM state WHERE id=1").fetchone()[0]
        if (supplied != hashlib.sha256(canonical(value).encode()).hexdigest()
                or command.get("bench_only") is not True or command.get("type") != "BENCH_CREDIT"
                or command.get("contract_version") != 1 or command.get("device_id") != self.device_id
                or command.get("storage_id") != storage or type(command.get("credit_wh")) is not int
                or not 0 < command["credit_wh"] <= 2**63-1 or command["credit_wh"] % 10
                or command.get("environment") not in {"CORE", "SANDBOX", "UGX_DEMO"}
                or not re.fullmatch(r"[0-9]{11}", str(command.get("meter_number")))):
            raise ValueError("Invalid or misbound software-bench command.")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            prior = self.db.execute("SELECT payload,receipt FROM commands WHERE id=?", (command["command_id"],)).fetchone()
            if prior:
                if prior[0] != canonical(command):
                    raise ValueError("Command ID reused with changed content.")
                receipt = json.loads(prior[1])
            else:
                counter, applied = self.db.execute("SELECT counter,applied FROM state WHERE id=1").fetchone()
                if applied + command["credit_wh"] > 2**63-1:
                    raise ValueError("Device counter range exceeded.")
                receipt = {key: command[key] for key in ("contract_version", "device_id", "command_id", "delivery_id", "allocation_id", "binding_epoch", "environment", "storage_id", "credit_wh", "payload_digest")}
                receipt.update(type="BENCH_APPLIED", receipt_id=str(uuid.uuid4()), application_counter=counter+1,
                               applied_at=datetime.now(timezone.utc).isoformat())
                self.db.execute("UPDATE state SET counter=counter+1,applied=applied+?,remaining=remaining+? WHERE id=1", (command["credit_wh"], command["credit_wh"]))
                self.db.execute("INSERT INTO commands (id,payload,receipt) VALUES (?,?,?)", (command["command_id"], canonical(command), canonical(receipt)))
            # Credit + receipt commit together before returning/acknowledging.
            self.db.execute("COMMIT")
            return receipt
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def pending_receipts(self):
        return [json.loads(row[0]) for row in self.db.execute("SELECT receipt FROM commands WHERE acked=0 ORDER BY rowid")]

    def mark_acknowledged(self, command_id):
        self.db.execute("UPDATE commands SET acked=1 WHERE id=?", (command_id,))

    def consume(self, wh):
        if type(wh) is not int or wh <= 0:
            raise ValueError("Use positive whole Wh.")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT remaining FROM state WHERE id=1").fetchone()[0] < wh:
                raise ValueError("Software relay open: insufficient locally applied credit.")
            self.db.execute("UPDATE state SET remaining=remaining-?,consumed=consumed+? WHERE id=1", (wh, wh))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        self.db.close()


def main():
    import requests
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="http://127.0.0.1:8001/api/v1")
    parser.add_argument("--device-id", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--recover", action="store_true")
    parser.add_argument("--drop-ack", action="store_true")
    parser.add_argument("--consume-wh", type=int)
    args = parser.parse_args()
    url = urlsplit(args.server)
    if (url.scheme not in {"http", "https"} or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.query or url.fragment or url.path.rstrip("/") != "/api/v1"):
        parser.error("Software bench transport is restricted to loopback /api/v1; no hosted or physical endpoints.")
    device = DurableDevice(args.state, str(uuid.UUID(args.device_id)), initialize=args.initialize)
    try:
        if args.consume_wh is not None:
            device.consume(args.consume_wh)
            print("SOFTWARE_BENCH: stored credit consumed locally; no network or physical relay.")
            return
        credential = os.environ.get("BENCH_DEVICE_TOKEN", "")
        if len(credential) < 32:
            raise ValueError("Set private BENCH_DEVICE_TOKEN.")
        http = requests.Session(); http.trust_env = False
        def post(endpoint, payload):
            response = http.post(args.server.rstrip("/") + "/bench-device/v1/" + endpoint + "/", json=payload,
                headers={"X-Bench-Device-Id": device.device_id, "X-Bench-Device-Token": credential},
                timeout=(3, 10), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError(f"Bench request rejected HTTP {response.status_code}; no success inferred. Retain journal.")
            return response.json()
        post("session", device.handshake())
        if not args.recover:
            value = getpass.getpass("15-digit SOFTWARE BENCH keypad token (hidden): ")
            if not re.fullmatch(r"[0-9]{15}", value):
                raise ValueError("Enter exactly15 ASCII digits.")
            device.apply(post("redeem", {"contract_version": 1, "token": value})["command"])
        if not args.drop_ack:
            for receipt in device.pending_receipts():
                response = post("ack", receipt)
                if response.get("state") != "APPLIED" or response.get("application_environment") != "SOFTWARE_BENCH":
                    raise ValueError("No readable server acknowledgement; retain pending receipt.")
                device.mark_acknowledged(receipt["command_id"])
        print("SOFTWARE_BENCH completed; no household electricity or physical acknowledgement.")
    except (ValueError, requests.RequestException):
        # Never print provider bodies, token input, headers or exception URLs.
        print("SOFTWARE_BENCH not confirmed. Retain journal and retry/reconcile; no physical action.")
        raise SystemExit(1) from None
    finally:
        device.close()


if __name__ == "__main__":
    main()
