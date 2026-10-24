#!/usr/bin/env python3
"""Small optional HTTP tool for an existing mail bot; Python standard library.

The bot owns mail selection and its durable delivery queue. This tool sends one
immutable JSON envelope to the existing Smartplan 0.9 intake. It never reads a
mailbox, changes customers/projects, follows redirects or logs mail/credentials.
"""
import argparse
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.request


ENDPOINT = "https://office.smartplan-hofmann.de/api/v1/intake/gmail"
MAX_ENVELOPE_BYTES = 200_000
MAX_RECEIPT_BYTES = 4096
FIELDS = frozenset(("source_account", "source_id", "subject", "message",
                    "sender_name", "sender_email", "received_at"))
REQUIRED = frozenset(("source_account", "source_id", "subject", "message"))


class DeliveryError(Exception):
    """Only fixed non-sensitive error identifiers may cross the CLI boundary."""

    def __init__(self, code, *, http_status=None):
        super().__init__(code)
        self.code, self.http_status = code, http_status


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DeliveryError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _constant(_value):
    raise DeliveryError("INVALID_JSON")


def _json(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_constant=_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise DeliveryError("INVALID_JSON") from None


def _text(value, maximum, *, required=False, multiline=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise DeliveryError("INVALID_MESSAGE_FIELDS")
    checked = value.replace("\r\n", "\n").replace("\r", "\n") if multiline else value
    if (any(ord(c) < 32 and (not multiline or c not in "\n\t") for c in checked)
            or (required and not checked.strip())):
        raise DeliveryError("INVALID_MESSAGE_FIELDS")
    return value


def _instant(value):
    if not isinstance(value, str) or len(value) > 64:
        raise DeliveryError("INVALID_TIMESTAMP")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise DeliveryError("INVALID_TIMESTAMP") from None


def validate_envelope(value):
    """Validate the published receiver contract without altering the payload."""
    if not isinstance(value, dict) or set(value) - FIELDS or not REQUIRED <= set(value):
        raise DeliveryError("INVALID_MESSAGE_FIELDS")
    account = _text(value["source_account"], 254, required=True)
    if not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", account.strip()):
        raise DeliveryError("INVALID_SOURCE_ACCOUNT")
    if (not isinstance(value["source_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["source_id"])):
        raise DeliveryError("INVALID_SOURCE_ID")
    _text(value["subject"], 300, required=True)
    _text(value["message"], 40_000, required=True, multiline=True)
    if "sender_name" in value:
        _text(value["sender_name"], 200)
    if "sender_email" in value:
        email = _text(value["sender_email"], 254).strip()
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise DeliveryError("INVALID_SENDER_EMAIL")
    if "received_at" in value:
        _instant(value["received_at"])
    try:
        # The server's size guard uses these same JSON defaults.
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, UnicodeError):
        raise DeliveryError("INVALID_JSON") from None
    if len(encoded) > MAX_ENVELOPE_BYTES:
        raise DeliveryError("MESSAGE_TOO_LARGE")
    return encoded


def load_envelope(filename):
    try:
        with Path(filename).open("rb") as stream:
            raw = stream.read(MAX_ENVELOPE_BYTES + 1)
    except OSError:
        raise DeliveryError("INPUT_UNREADABLE") from None
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise DeliveryError("MESSAGE_TOO_LARGE")
    value = _json(raw)
    validate_envelope(value)
    return value


def load_token(filename=None):
    inherited = os.environ.get("SMARTPLAN_INTAKE_TOKEN", "")
    if filename and inherited:
        raise DeliveryError("USE_ONE_CREDENTIAL_SOURCE")
    if filename:
        descriptor = None
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
            if Path(filename).is_symlink():
                raise DeliveryError("UNSAFE_CREDENTIAL_FILE")
            descriptor = os.open(filename, flags)
            info = os.fstat(descriptor)
            if (not stat.S_ISREG(info.st_mode)
                    or (os.name == "posix" and (info.st_mode & 0o077
                                               or info.st_uid != os.geteuid()))):
                raise DeliveryError("UNSAFE_CREDENTIAL_FILE")
            with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
                descriptor = None
                inherited = stream.read(201)
            if len(inherited) > 200:
                raise DeliveryError("INVALID_CREDENTIAL")
        except (OSError, UnicodeError):
            raise DeliveryError("CREDENTIAL_UNREADABLE") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
    return header_credential(inherited.strip())


def header_credential(value):
    """A vault may expose an opaque gateway handle instead of the real key.

    Validate header safety here, not the hidden key's format. An authenticated
    platform HTTP tool/proxy must supply the real credential on the wire;
    urllib itself does not dereference handles. Smartplan still authorizes the
    actual SPIN key, and only a valid received receipt confirms delivery.
    """
    if (not isinstance(value, str) or not 1 <= len(value) <= 193
            or any(not 33 <= ord(character) <= 126 for character in value)):
        raise DeliveryError("INVALID_CREDENTIAL")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def send_envelope(value, token):
    payload = validate_envelope(value)
    token = header_credential(token)
    request = urllib.request.Request(
        ENDPOINT, data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    )
    try:
        # Inherited proxy, CA trust and normal certificate verification stay in
        # force. No credential-bearing request is redirected to another target.
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            status = response.status
            if status != 201:
                raise DeliveryError("UNEXPECTED_HTTP_STATUS", http_status=status)
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                raise DeliveryError("UNCONFIRMED_RECEIPT")
            raw = response.read(MAX_RECEIPT_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        error.close()  # Error bodies can contain reflected confidential text.
        raise DeliveryError("HTTP_FAILURE", http_status=status) from None
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
        raise DeliveryError("NETWORK_UNCONFIRMED") from None
    if len(raw) > MAX_RECEIPT_BYTES:
        raise DeliveryError("UNCONFIRMED_RECEIPT")
    try:
        receipt = _json(raw)
        if (not isinstance(receipt, dict) or receipt.get("status") != "received"
                or not isinstance(receipt.get("id"), str)
                or not re.fullmatch(r"[a-f0-9]{32}", receipt["id"])):
            raise DeliveryError("UNCONFIRMED_RECEIPT")
        _instant(receipt.get("ingested_at"))
    except DeliveryError:
        raise DeliveryError("UNCONFIRMED_RECEIPT") from None
    return {key: receipt[key] for key in ("id", "status", "ingested_at")}


class SafeParser(argparse.ArgumentParser):
    def error(self, _message):
        # Unknown arguments may include an accidentally pasted key. Never echo
        # argv, file paths or argparse's raw error text.
        self.exit(2, '{"status":"not_sent","error":"INVALID_ARGUMENTS"}\n')


def main(argv=None):
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--input", required=True, help="Immutable original-mail JSON file")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="Validate locally; no token or network")
    modes.add_argument("--send", action="store_true", help="Deliver one inquiry to Smartplan")
    parser.add_argument("--token-file", help="Private regular credential file; POSIX mode0600")
    args = parser.parse_args(argv)
    try:
        value = load_envelope(args.input)
        if args.check:
            result = {"status": "validated", "sent": False}
        else:
            result = send_envelope(value, load_token(args.token_file))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except DeliveryError as error:
        result = {"status": "unconfirmed" if args.send else "not_sent", "error": error.code}
        if error.http_status is not None:
            result["http_status"] = error.http_status
        print(json.dumps(result), file=sys.stderr)
        return 3 if args.send else 2
    except KeyboardInterrupt:
        print('{"status":"unconfirmed","error":"INTERRUPTED"}', file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
