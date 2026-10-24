#!/usr/bin/env python3
"""Send original mail attachments to the fixed Smartplan intake; stdlib only.

The bot owns its private staging area and durable queue. This tool never opens a
mailbox, parses documents, executes files, reposts a mail body or retries on its
own. A complete attachment-set receipt is distinct from the body receipt.
"""
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.error
import urllib.request

from send_inquiry import (DeliveryError, NoRedirect, SafeParser, _json,
                          header_credential, load_token)


ENDPOINT = "https://office.smartplan-hofmann.de/api/v1/intake/gmail/attachments"
CHUNK_SIZE = 262144
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_MESSAGE_BYTES = 60 * 1024 * 1024
MAX_FILES = 30
MAX_MANIFEST_BYTES = 256 * 1024
MAX_RECEIPT_BYTES = 256 * 1024
DESCRIPTOR_FIELDS = ("source_attachment_id", "filename", "media_type", "size", "sha256")
MEDIA = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+/[!#$%&'*+.^_`|~0-9A-Za-z-]+")


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _open_original(path):
    descriptor = None
    try:
        if path.is_symlink():
            raise DeliveryError("UNSAFE_ATTACHMENT_FILE")
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                             | getattr(os, "O_NONBLOCK", 0))
        info = os.fstat(descriptor)
        if (not stat.S_ISREG(info.st_mode)
                or (os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.geteuid()))):
            raise DeliveryError("UNSAFE_ATTACHMENT_FILE")
        if not 1 <= info.st_size <= MAX_FILE_BYTES:
            raise DeliveryError("ATTACHMENT_SIZE_LIMIT")
        stream = os.fdopen(descriptor, "rb")
        descriptor = None
        return stream, info
    except OSError:
        raise DeliveryError("ATTACHMENT_UNREADABLE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _digest(stream, expected_size):
    digest, size = hashlib.sha256(), 0
    while True:
        piece = stream.read(CHUNK_SIZE)
        if not piece:
            break
        size += len(piece)
        if size > expected_size or size > MAX_FILE_BYTES:
            raise DeliveryError("ATTACHMENT_CHANGED")
        digest.update(piece)
    if size != expected_size:
        raise DeliveryError("ATTACHMENT_CHANGED")
    return digest.hexdigest()


class Original:
    def __init__(self, path, descriptor):
        self.path, self.descriptor = path, descriptor
        stream, info = _open_original(path)
        with stream:
            self.identity = _identity(info)
            descriptor["size"] = info.st_size
            descriptor["sha256"] = _digest(stream, info.st_size)
            if _identity(os.fstat(stream.fileno())) != self.identity:
                raise DeliveryError("ATTACHMENT_CHANGED")

    def open(self):
        stream, info = _open_original(self.path)
        if _identity(info) != self.identity:
            stream.close()
            raise DeliveryError("ATTACHMENT_CHANGED")
        return stream

    def verify(self):
        with self.open() as stream:
            digest = _digest(stream, self.descriptor["size"])
            if (digest != self.descriptor["sha256"]
                    or _identity(os.fstat(stream.fileno())) != self.identity):
                raise DeliveryError("ATTACHMENT_CHANGED")


def load_manifest(filename):
    """Freeze metadata derived from bounded regular originals, never from URLs."""
    path = Path(filename)
    try:
        stream, _info = _open_original(path)
        with stream:
            raw = stream.read(MAX_MANIFEST_BYTES + 1)
    except OSError:
        raise DeliveryError("MANIFEST_UNREADABLE") from None
    if len(raw) > MAX_MANIFEST_BYTES:
        raise DeliveryError("MANIFEST_TOO_LARGE")
    value = _json(raw)
    if (not isinstance(value, dict) or set(value) != {"source_account", "source_id", "attachments"}
            or not isinstance(value["attachments"], list) or len(value["attachments"]) > MAX_FILES):
        raise DeliveryError("INVALID_ATTACHMENT_MANIFEST")
    account = value["source_account"]
    if (not isinstance(account, str) or len(account) > 254
            or any(ord(c) < 32 for c in account)
            or not re.fullmatch(r"[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+", account.strip())):
        raise DeliveryError("INVALID_SOURCE_ACCOUNT")
    if (not isinstance(value["source_id"], str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value["source_id"])):
        raise DeliveryError("INVALID_SOURCE_ID")
    originals, seen, total = [], set(), 0
    for entry in value["attachments"]:
        if not isinstance(entry, dict) or set(entry) != {"source_attachment_id", "filename", "media_type", "path"}:
            raise DeliveryError("INVALID_ATTACHMENT_MANIFEST")
        identifier, name, media = (entry[key] for key in DESCRIPTOR_FIELDS[:3])
        if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 2048
                or not identifier.isprintable() or identifier in seen):
            raise DeliveryError("INVALID_ATTACHMENT_ID")
        if (not isinstance(name, str) or not 1 <= len(name) <= 200 or not name.strip()
                or not name.isprintable() or "/" in name or "\\" in name or name.strip() in (".", "..")):
            raise DeliveryError("INVALID_ATTACHMENT_FILENAME")
        if not isinstance(media, str) or len(media) > 100 or not MEDIA.fullmatch(media):
            raise DeliveryError("INVALID_ATTACHMENT_MEDIA_TYPE")
        if not isinstance(entry["path"], str) or not entry["path"] or "\x00" in entry["path"]:
            raise DeliveryError("INVALID_ATTACHMENT_PATH")
        source = Path(entry["path"])
        if not source.is_absolute():
            source = path.parent / source
        descriptor = {"source_attachment_id": identifier, "filename": name.strip(), "media_type": media.lower()}
        original = Original(source, descriptor)
        total += descriptor["size"]
        if total > MAX_MESSAGE_BYTES:
            raise DeliveryError("ATTACHMENT_TOTAL_LIMIT")
        originals.append(original)
        seen.add(identifier)
    payload = {"source_account": account, "source_id": value["source_id"],
               "attachments": [dict(item.descriptor) for item in originals]}
    return payload, originals


def _request(url, method, payload, token):
    """Only internally constructed fixed-host URLs reach this transport."""
    if url != ENDPOINT and not re.fullmatch(re.escape(ENDPOINT) + r"/[a-f0-9]{32}/(?:chunks/[0-9]{1,2}|complete)", url):
        raise DeliveryError("INVALID_UPLOAD_TARGET")
    binary = isinstance(payload, bytes)
    data = payload if binary else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={
        "Content-Type": "application/octet-stream" if binary else "application/json",
        "Authorization": "Bearer " + header_credential(token),
    })
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=20) as response:
            if response.status not in ((200, 201) if url == ENDPOINT else (200,)):
                raise DeliveryError("UNEXPECTED_HTTP_STATUS", http_status=response.status)
            if response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
            raw = response.read(MAX_RECEIPT_BYTES + 1)
    except urllib.error.HTTPError as error:
        status = error.code
        retry = error.headers.get("Retry-After", "") if error.headers else ""
        error.close()  # Never expose a provider/proxy body or its reflected credentials.
        failure = DeliveryError("SERVER_UPDATE_OR_PARENT_REQUIRED" if status == 404 else "HTTP_FAILURE",
                                http_status=status)
        if isinstance(retry, str) and re.fullmatch(r"[0-9]{1,6}", retry) and 0 < int(retry) <= 86400:
            failure.retry_after_seconds = int(retry)
        raise failure from None
    except (urllib.error.URLError, OSError, TimeoutError, http.client.HTTPException):
        raise DeliveryError("NETWORK_UNCONFIRMED") from None
    if len(raw) > MAX_RECEIPT_BYTES:
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    try:
        return _json(raw)
    except DeliveryError:
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS") from None


def _file_receipt(value, expected, *, identifier=None, chunks=True):
    if (not isinstance(value, dict) or not isinstance(value.get("id"), str)
            or not re.fullmatch(r"[a-f0-9]{32}", value["id"])
            or (identifier is not None and value["id"] != identifier)
            or any(value.get(key) != expected[key] for key in DESCRIPTOR_FIELDS)
            or type(value.get("size")) is not int
            or value.get("status") not in ("uploading", "ready", "deleted")):
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    if chunks:
        indices = value.get("received_chunks")
        count = (expected["size"] + CHUNK_SIZE - 1) // CHUNK_SIZE
        if (not isinstance(indices, list) or any(type(index) is not int or not 0 <= index < count for index in indices)
                or len(indices) != len(set(indices))
                or (value["status"] == "ready" and set(indices) != set(range(count)))):
            raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    return value


def _batch_receipt(value, payload):
    expected = {item["source_attachment_id"]: item for item in payload["attachments"]}
    if (not isinstance(value, dict) or value.get("status") not in ("uploading", "complete")
            or type(value.get("chunk_size")) is not int or value["chunk_size"] != CHUNK_SIZE
            or type(value.get("expected_count")) is not int or value["expected_count"] != len(expected)
            or type(value.get("total_bytes")) is not int
            or value["total_bytes"] != sum(item["size"] for item in expected.values())
            or not isinstance(value.get("files"), list) or len(value["files"]) != len(expected)):
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    rows, identifiers = {}, set()
    for item in value["files"]:
        key = item.get("source_attachment_id") if isinstance(item, dict) else None
        if not isinstance(key, str) or key not in expected or key in rows:
            raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
        record = _file_receipt(item, expected[key])
        if record["id"] in identifiers:
            raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
        identifiers.add(record["id"])
        rows[key] = record
    ready = sum(row["status"] == "ready" for row in rows.values())
    deleted = sum(row["status"] == "deleted" for row in rows.values())
    if (type(value.get("ready_count")) is not int or value["ready_count"] != ready
            or type(value.get("deleted_count")) is not int or value["deleted_count"] != deleted
            or (value["status"] == "complete") != (ready + deleted == len(expected))):
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    return rows


def send_attachments(payload, originals, token):
    token = header_credential(token)
    rows = _batch_receipt(_request(ENDPOINT, "POST", payload, token), payload)
    for original in originals:
        record = rows[original.descriptor["source_attachment_id"]]
        if record["status"] in ("ready", "deleted"):
            continue
        received = set(record["received_chunks"])
        digest = hashlib.sha256()
        with original.open() as stream:
            for index in range((original.descriptor["size"] + CHUNK_SIZE - 1) // CHUNK_SIZE):
                expected_size = min(CHUNK_SIZE, original.descriptor["size"] - index * CHUNK_SIZE)
                piece = stream.read(expected_size)
                if len(piece) != expected_size:
                    raise DeliveryError("ATTACHMENT_CHANGED")
                digest.update(piece)
                if index not in received:
                    value = _request(ENDPOINT + "/" + record["id"] + "/chunks/" + str(index), "PUT", piece, token)
                    acknowledged = _file_receipt(value, original.descriptor, identifier=record["id"])
                    if acknowledged["status"] == "deleted":
                        break
                    if index not in acknowledged["received_chunks"]:
                        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
            else:
                if (stream.read(1) or digest.hexdigest() != original.descriptor["sha256"]
                        or _identity(os.fstat(stream.fileno())) != original.identity):
                    raise DeliveryError("ATTACHMENT_CHANGED")
                value = _request(ENDPOINT + "/" + record["id"] + "/complete", "POST", {}, token)
                final = _file_receipt(value, original.descriptor, identifier=record["id"])
                if final["status"] not in ("ready", "deleted"):
                    raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    for original in originals:
        original.verify()
    final = _request(ENDPOINT, "POST", payload, token)
    final_rows = _batch_receipt(final, payload)
    if any(final_rows[key]["id"] != record["id"] for key, record in rows.items()):
        raise DeliveryError("UNCONFIRMED_ATTACHMENTS")
    if final["status"] != "complete":
        raise DeliveryError("ATTACHMENTS_PENDING")
    return {key: final[key] for key in ("status", "expected_count", "ready_count", "deleted_count", "total_bytes")}


def main(argv=None):
    parser = SafeParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--manifest", required=True, help="Private immutable local attachment manifest")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true", help="Validate and hash originals without network or token")
    modes.add_argument("--send", action="store_true", help="Resume attachment delivery to the fixed intake")
    parser.add_argument("--token-file", help="Private credential file; never pass the key in argv")
    args = parser.parse_args(argv)
    try:
        payload, originals = load_manifest(args.manifest)
        result = ({"status": "validated", "sent": False, "expected_count": len(originals)} if args.check
                  else send_attachments(payload, originals, load_token(args.token_file)))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except DeliveryError as error:
        result = {"status": "pending" if args.send else "not_sent", "error": error.code}
        if error.http_status is not None:
            result["http_status"] = error.http_status
        if hasattr(error, "retry_after_seconds"):
            result["retry_after_seconds"] = error.retry_after_seconds
        print(json.dumps(result), file=sys.stderr)
        return 3 if args.send else 2
    except (OSError, ValueError, UnicodeError):
        print('{"status":"pending","error":"LOCAL_ATTACHMENT_FAILURE"}', file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print('{"status":"pending","error":"INTERRUPTED"}', file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
