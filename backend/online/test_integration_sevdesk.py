"""Sevdesk fixtures pass through the real fixed-host HTTP transport."""
from io import BytesIO
import json
import unittest
from urllib.parse import parse_qs, urlsplit

from core import Problem
from online.integration_http import IntegrationHttp
from online.integration_sevdesk import SevdeskProvider


def contact(identifier="42", **changes):
    return {"id": identifier, "objectName": "Contact", "name": "Hofmann Testbau",
            "customerNumber": "K-42", **changes}


def document(identifier="7", *, kind="offer", **changes):
    return {"id": identifier, "objectName": "Order" if kind == "offer" else "Invoice",
            "contact": {"id": "42", "objectName": "Contact"}, "orderType": "AN",
            "orderNumber": "AN-7", "invoiceNumber": "RE-7", "header": "Dacharbeiten",
            "status": "100", "sumGross": "123456789012345.123456789", "currency": "EUR",
            "orderDate": "2026-10-24T00:00:00+02:00", "invoiceDate": "2026-10-24T00:00:00+02:00",
            **changes}


class JsonResponse(BytesIO):
    status = 200
    headers = {"Content-Type": "application/json"}

    def __init__(self, value):
        super().__init__(json.dumps(value).encode("utf-8"))


class ProviderOpener:
    def __init__(self, routes):
        self.routes = routes
        self.requests = []

    def open(self, request, *, timeout):
        parts = urlsplit(request.full_url)
        assert parts.scheme == "https" and parts.hostname == "my.sevdesk.de"
        assert request.method == "GET" and request.data is None
        assert request.get_header("Authorization") == "synthetic-sevdesk-key"
        query = parse_qs(parts.query)
        path = parts.path.removeprefix("/api/v1")
        self.requests.append((path, query))
        value = self.routes[path]
        return JsonResponse(value(query) if callable(value) else value)


class SevdeskTests(unittest.TestCase):
    def provider(self, routes):
        opener = ProviderOpener(routes)
        return SevdeskProvider(IntegrationHttp("sevdesk", opener=opener)), opener

    def assert_problem(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(status, caught.exception.status)

    def test_validate_binds_account_identity_not_arbitrary_first_user(self):
        provider, opener = self.provider({"/SevUser": {"objects": [{"id": "12", "username": "other-user", "sevClient": {"id": "99"}}]}})
        self.assertEqual({"id": "99", "label": "sevdesk-Konto 99"}, provider.validate("synthetic-sevdesk-key"))
        self.assertEqual([("/SevUser", {"limit": ["1"], "offset": ["0"]})], opener.requests)

    def test_contacts_are_normalized_paginated_and_locally_searched(self):
        first = [contact(str(i), name="Firma " + str(i), customerNumber=str(i)) for i in range(1,101)]
        provider, opener = self.provider({"/Contact": lambda query: {"objects": first if query["offset"] == ["0"] else [contact("101", name=None, surename="Eva", familyname="Bau")]}})
        self.assertEqual([{"id": "101", "name": "Eva Bau", "number": "K-42"}], provider.contacts("synthetic-sevdesk-key", "eva"))
        self.assertEqual(2, len(opener.requests))
        self.assertTrue(all(q["depth"] == ["1"] for _,q in opener.requests))

    def test_document_preview_filters_offer_type_and_preserves_exact_decimal(self):
        provider, opener = self.provider({"/Contact/42": {"objects": [contact()]},
            "/Order": {"objects": [document(), document("8", orderType="AB")]},
            "/Invoice": {"objects": [document("9", kind="invoice", status="750")]}})
        result = provider.contact_documents("synthetic-sevdesk-key", "42")
        self.assertEqual(["7"], [x["id"] for x in result["offers"]])
        self.assertEqual("123456789012345.123456789", result["offers"][0]["total_gross"])
        self.assertEqual("Teilweise bezahlt", result["invoices"][0]["status_label"])
        self.assertIsNone(result["invoices"][0]["url"])
        for path, query in opener.requests[1:]:
            self.assertEqual(["42"], query["contact[id]"])
            self.assertEqual(["Contact"], query["contact[objectName]"])
        self.assertFalse(any("getPdf" in path for path,_ in opener.requests))

    def test_snapshot_fetches_selected_ids_only_and_never_all_customer_documents(self):
        provider, opener = self.provider({"/Contact/42": {"objects": [contact()]},
            "/Order/7": {"objects": [document()]}, "/Invoice/9": {"objects": [document("9", kind="invoice")]}})
        result = provider.snapshot("synthetic-sevdesk-key", {"contact_id": "42", "offer_ids": ["7"], "invoice_ids": ["9"]})
        self.assertEqual(["/Contact/42", "/Order/7", "/Invoice/9"], [path for path,_ in opener.requests])
        self.assertEqual(["9"], [row["id"] for row in result["invoices"]])

    def test_ignored_provider_contact_filter_or_changed_selected_owner_rejects_whole_snapshot(self):
        foreign = document(contact={"id": "999", "objectName": "Contact"})
        for details in (False, True):
            provider, _ = self.provider({"/Contact/42": {"objects": [contact()]},
                "/Order": {"objects": [foreign]}, "/Invoice": {"objects": []},
                "/Order/7": {"objects": [foreign]}})
            self.assert_problem(409, lambda: provider.snapshot("synthetic-sevdesk-key", {"contact_id": "42", "offer_ids": ["7"]}) if details else provider.contact_documents("synthetic-sevdesk-key", "42"))

    def test_known_and_unknown_status_never_guess_paid_or_overdue(self):
        for code, label in [("200","Offen"), ("1000","Bezahlt"), ("275","Unbekannt (275)")]:
            provider, _ = self.provider({"/Contact/42": {"objects": [contact()]},
                "/Invoice/9": {"objects": [document("9", kind="invoice", status=code)]}})
            result = provider.snapshot("synthetic-sevdesk-key", {"contact_id": "42", "invoice_ids": ["9"]})
            self.assertEqual(label, result["invoices"][0]["status_label"])

    def test_unavailable_amount_currency_are_null_and_invalid_float_not_rounded(self):
        provider, _ = self.provider({"/Contact/42": {"objects": [contact()]},
            "/Invoice/9": {"objects": [document("9", kind="invoice", sumGross=None, currency=None)]}})
        row = provider.snapshot("synthetic-sevdesk-key", {"contact_id": "42", "invoice_ids": ["9"]})["invoices"][0]
        self.assertIsNone(row["total_gross"])
        self.assertIsNone(row["currency"])
        for amount in [1.2345678901234567, "NaN", "1e99999"]:
            provider, _ = self.provider({"/Contact/42": {"objects": [contact()]},
                "/Invoice/9": {"objects": [document("9", kind="invoice", sumGross=amount)]}})
            self.assert_problem(503, lambda: provider.snapshot("synthetic-sevdesk-key", {"contact_id": "42", "invoice_ids": ["9"]}))

    def test_wrong_resource_or_order_type_cannot_be_labeled_as_offer(self):
        for changes in [{"orderType":"AB"}, {"orderType":"LI"}, {"objectName":"Invoice"}, {"id":"8"}]:
            provider, _ = self.provider({"/Contact/42": {"objects": [contact()]}, "/Order/7": {"objects": [document(**changes)]}})
            self.assert_problem(409 if "orderType" in changes else 503,
                lambda: provider.snapshot("synthetic-sevdesk-key", {"contact_id":"42", "offer_ids":["7"]}))

    def test_missing_duplicate_malformed_rows_and_ids_are_not_empty_success(self):
        for value in [{}, {"objects":None}, {"objects":[contact(),contact()]}, {"objects":[{"id":"not-an-id"}]}]:
            provider, _ = self.provider({"/Contact/42":value})
            self.assert_problem(503, lambda: provider.snapshot("synthetic-sevdesk-key", {"contact_id":"42"}))
        provider, _ = self.provider({"/Contact/42":{"objects":[]}})
        self.assert_problem(404, lambda: provider.snapshot("synthetic-sevdesk-key", {"contact_id":"42"}))

    def test_duplicate_pagination_and_overlarge_selection_fail_before_data_leak(self):
        first = [contact(str(i)) for i in range(1,101)]
        provider, _ = self.provider({"/Contact": {"objects": first}})
        self.assert_problem(503, lambda: provider.contacts("synthetic-sevdesk-key"))
        provider, opener = self.provider({})
        for link in [{"contact_id":"../1"}, {"contact_id":"42","offer_ids":["7","7"]},
                     {"contact_id":"42","offer_ids":[str(i) for i in range(1,52)]}]:
            self.assert_problem(400, lambda: provider.snapshot("synthetic-sevdesk-key", link))
        self.assertEqual([], opener.requests)


if __name__ == "__main__":
    unittest.main()
