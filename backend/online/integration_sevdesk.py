"""Read-only sevdesk metadata adapter; never renders or fetches document PDFs.

The transport independently restricts every upstream request to the small GET
allowlist. See the integration source notes for API documentation limitations.
"""
from decimal import Decimal, InvalidOperation
import re

from core import Problem


_ID = re.compile(r"[1-9][0-9]{0,19}\Z")
_MONEY = re.compile(r"-?[0-9]{1,30}(?:\.[0-9]{1,20})?\Z")
_ORDER_STATUS = {"100": "Entwurf", "200": "Versendet", "300": "Abgelehnt / storniert",
                 "500": "Angenommen", "750": "Teilweise berechnet", "1000": "Berechnet"}
_INVOICE_STATUS = {"50": "Wiederkehrende Rechnung deaktiviert", "100": "Entwurf",
                   "200": "Offen", "750": "Teilweise bezahlt", "1000": "Bezahlt"}


def _bad_data():
    return Problem(503, "sevdesk hat unvollständige oder ungültige Daten geliefert.")


def _identifier(value, *, upstream=False):
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise _bad_data() if upstream else Problem(400, "Ungültige sevdesk-Auswahl.")
    return value


def _text(value, maximum=1000, *, optional=False):
    if value is None and optional:
        return None
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value:
        raise _bad_data()
    return value


def _amount(value):
    if value is None:
        return None
    if type(value) is int:
        value = str(value)
    # Monetary JSON floats already lost decimal precision. Do not calculate or
    # silently round them into an apparently exact accounting value.
    if not isinstance(value, str) or not _MONEY.fullmatch(value):
        raise _bad_data()
    try:
        if not Decimal(value).is_finite():
            raise InvalidOperation()
    except InvalidOperation:
        raise _bad_data() from None
    return value


class SevdeskProvider:
    def __init__(self, http):
        self.http = http

    def _get(self, token, path, params=None):
        if (not isinstance(token, str) or not token or len(token) > 4096 or
                token != token.strip() or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise Problem(400, "Ungültiger sevdesk-Zugang.")
        call = getattr(self.http, "call", self.http)
        return call(path, method="GET", params=params, headers={"Authorization": token})

    def _rows(self, token, path, params=None, *, single=False):
        result = self._get(token, path, params)
        if not isinstance(result, dict) or "objects" not in result:
            raise _bad_data()
        rows = result["objects"]
        if single and isinstance(rows, dict):
            rows = [rows]
        if not isinstance(rows, list) or len(rows) > 100 or any(not isinstance(row, dict) for row in rows):
            raise _bad_data()
        return rows

    def _one(self, token, resource, identifier):
        rows = self._rows(token, "/" + resource + "/" + identifier, single=True)
        if not rows:
            raise Problem(404, "Der gewählte sevdesk-Eintrag ist nicht mehr verfügbar.")
        if (len(rows) != 1 or _identifier(rows[0].get("id"), upstream=True) != identifier or
                rows[0].get("objectName", resource) != resource):
            raise _bad_data()
        return rows[0]

    def _all(self, token, resource, params=None):
        output, seen = [], set()
        for page in range(6):
            rows = self._rows(token, "/" + resource,
                {**(params or {}), "limit": 100, "offset": page * 100})
            for row in rows:
                identifier = _identifier(row.get("id"), upstream=True)
                if identifier in seen or row.get("objectName", resource) != resource:
                    raise _bad_data()
                seen.add(identifier)
                output.append(row)
            if len(output) > 500:
                raise Problem(409, "Zu viele sevdesk-Einträge für diesen Abruf. Bitte die Auswahl eingrenzen.")
            if len(rows) < 100:
                return output
        raise Problem(409, "Zu viele sevdesk-Einträge für diesen Abruf. Bitte die Auswahl eingrenzen.")

    @staticmethod
    def _contact(row):
        identifier = _identifier(row.get("id"), upstream=True)
        name = _text(row.get("name"), optional=True) or " ".join(
            x for x in (_text(row.get("surename"), optional=True),
                        _text(row.get("familyname"), optional=True)) if x)
        result = {"id": identifier, "name": name or "Kontakt " + identifier}
        if row.get("customerNumber") is not None:
            result["number"] = _text(row["customerNumber"], 200)
        # Contacts have no universal direct email field in the documented model;
        # do not invent an address from a username or fetch unrelated resources.
        return result

    @staticmethod
    def _document(row, kind, contact_id):
        resource = "Order" if kind == "offer" else "Invoice"
        reference = row.get("contact")
        if (not isinstance(reference, dict) or
                _identifier(reference.get("id"), upstream=True) != contact_id or
                reference.get("objectName", "Contact") != "Contact"):
            raise Problem(409, "Ein sevdesk-Dokument gehört nicht zum gewählten Kontakt.")
        if row.get("objectName", resource) != resource:
            raise _bad_data()
        if kind == "offer" and row.get("orderType") != "AN":
            raise Problem(409, "Der gewählte sevdesk-Eintrag ist kein Angebot.")
        identifier = _identifier(row.get("id"), upstream=True)
        status = row.get("status")
        if type(status) is int:
            status = str(status)
        status = _text(status, 40)
        labels = _ORDER_STATUS if kind == "offer" else _INVOICE_STATUS
        currency = row.get("currency")
        if currency is not None and (not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)):
            raise _bad_data()
        return {
            "id": identifier, "kind": kind,
            "number": _text(row.get("orderNumber" if kind == "offer" else "invoiceNumber"), 200, optional=True),
            "title": _text(row.get("header"), 1000, optional=True),
            "status": status, "status_label": labels.get(status, "Unbekannt (" + status + ")"),
            "date": _text(row.get("orderDate" if kind == "offer" else "invoiceDate"), 100, optional=True),
            "total_gross": _amount(row.get("sumGross")), "currency": currency,
            # A provider UI deep link is deliberately absent until documented.
            "url": None,
        }

    def validate(self, api_token):
        rows = self._rows(api_token, "/SevUser", {"limit": 1, "offset": 0})
        if len(rows) != 1 or not isinstance(rows[0].get("sevClient"), dict):
            raise _bad_data()
        identifier = _identifier(rows[0]["sevClient"].get("id"), upstream=True)
        return {"id": identifier, "label": "sevdesk-Konto " + identifier}

    def contacts(self, api_token, query=""):
        if not isinstance(query, str) or len(query) > 200:
            raise Problem(400, "Ungültige Kontaktsuche.")
        needle = query.strip().casefold()
        params = {"depth": 1}
        # customerNumber is a documented exact filter. General name searching is
        # performed only over the bounded returned catalogue, not guessed query
        # operators that an upstream implementation might ignore.
        if query.strip().isdigit():
            params["customerNumber"] = query.strip()
        contacts = [self._contact(row) for row in self._all(api_token, "Contact", params)]
        return [row for row in contacts if not needle or needle in row["name"].casefold() or needle in row.get("number", "").casefold()]

    def contact_documents(self, api_token, contact_id):
        contact_id = _identifier(contact_id)
        contact = self._contact(self._one(api_token, "Contact", contact_id))
        params = {"contact[id]": contact_id, "contact[objectName]": "Contact"}
        orders = self._all(api_token, "Order", params)
        invoices = self._all(api_token, "Invoice", params)
        # Verify even the non-offer rows before discarding them: an ignored
        # provider filter must never return somebody else's accounting data.
        for row in orders:
            reference = row.get("contact")
            if (not isinstance(reference, dict) or _identifier(reference.get("id"), upstream=True) != contact_id or
                    reference.get("objectName", "Contact") != "Contact"):
                raise Problem(409, "Ein sevdesk-Dokument gehört nicht zum gewählten Kontakt.")
        return {"contact": contact,
                "offers": [self._document(row, "offer", contact_id) for row in orders if row.get("orderType") == "AN"],
                "invoices": [self._document(row, "invoice", contact_id) for row in invoices]}

    def snapshot(self, api_token, link):
        if not isinstance(link, dict):
            raise Problem(400, "Ungültige sevdesk-Auswahl.")
        contact_id = _identifier(link.get("contact_id"))
        selected = {}
        for field in ("offer_ids", "invoice_ids"):
            values = link.get(field, [])
            if not isinstance(values, list) or len(values) > 50:
                raise Problem(400, "Ungültige sevdesk-Auswahl.")
            selected[field] = [_identifier(value) for value in values]
            if len(set(selected[field])) != len(values):
                raise Problem(400, "Doppelte sevdesk-Auswahl.")
        if sum(map(len, selected.values())) > 50:
            raise Problem(400, "Zu viele sevdesk-Dokumente ausgewählt.")
        contact = self._contact(self._one(api_token, "Contact", contact_id))
        return {"contact": contact,
                "offers": [self._document(self._one(api_token, "Order", identifier), "offer", contact_id)
                           for identifier in selected["offer_ids"]],
                "invoices": [self._document(self._one(api_token, "Invoice", identifier), "invoice", contact_id)
                             for identifier in selected["invoice_ids"]]}
