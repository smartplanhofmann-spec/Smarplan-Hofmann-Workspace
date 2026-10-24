"""Complete bot-supplied Google source metadata, no account/remote IO."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from core import Problem
from online.integration_google import (
    normalize_bridge_catalog, normalize_bridge_resource, normalize_bridge_snapshot,
)


CALENDAR = "synthetic-team@example.test"


def calendar(**changes):
    return {"id": CALENDAR, "name": "Synthetischer Teamkalender", "time_zone": "Europe/Berlin", **changes}


def event(identifier="synthetic-event", **changes):
    return {"id": identifier, "title": "Synthetischer Termin", "description": "Nur synthetische Quelldaten.",
            "start": "2026-10-24T09:00:00+02:00", "end": "2026-10-24T10:00:00+02:00", "all_day": False,
            "time_zone": "Europe/Berlin", "location": "Synthetischer Ort", "status": "confirmed",
            "url": "https://calendar.google.com/calendar/event?eid=synthetic", **changes}


def catalog(**changes):
    return {"complete": True, "identity": {"id": "synthetic-source-account", "label": "Synthetisches Quellkonto"},
            "calendars": [calendar()], **changes}


def resource(*events, **changes):
    return {"complete": True, "calendar": calendar(), "events": list(events), **changes}


class GoogleBridgeTests(unittest.TestCase):
    def problem(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(caught.exception.status, status)
        return caught.exception

    def test_catalog_requires_real_supplied_identity_and_preserves_source_ids_without_native_claims(self):
        source = catalog()
        frozen = deepcopy(source)
        with patch("online.integration_google.IntegrationHttp", side_effect=AssertionError("No network")):
            result = normalize_bridge_catalog(source)
        self.assertEqual(result, {"identity": source["identity"], "calendars": source["calendars"]})
        self.assertNotIn("complete", result)
        self.assertNotIn("accessRole", result["calendars"][0])
        self.assertEqual(source, frozen)
        for identity in (None, {}, {"id": "", "label": "Source"}, {"id": "source", "label": " "}):
            with self.subTest(identity=identity):
                self.problem(400, lambda: normalize_bridge_catalog(catalog(identity=identity)))

    def test_complete_boolean_and_no_partial_paging_are_required_for_every_payload_kind(self):
        selection = {"calendar_id": CALENDAR, "event_ids": ["synthetic-event"]}
        for changes in ({"complete": False}, {"complete": 1}, {"complete": "true"}, {"complete": None},
                        {"has_more": True}, {"has_more": 0}, {"pending": True}, {"truncated": True},
                        {"nextPageToken": "still-more"}, {"next_link": "https://example.test/page2"}):
            with self.subTest(changes=changes):
                self.problem(400, lambda: normalize_bridge_catalog(catalog(**changes)))
                self.problem(400, lambda: normalize_bridge_resource(resource(event(), **changes), selection))
                self.problem(400, lambda: normalize_bridge_snapshot(resource(event(), **changes), selection))

    def test_canonical_fields_are_required_and_raw_google_objects_are_not_mislabelled_as_normalized(self):
        raw = {"id": CALENDAR, "summary": "Raw calendar", "timeZone": "Europe/Berlin", "accessRole": "reader"}
        self.problem(400, lambda: normalize_bridge_catalog(catalog(calendars=[raw])))
        self.problem(400, lambda: normalize_bridge_resource(resource(event(), calendar=raw), {"calendar_id": CALENDAR}))
        for changes in ({"id": ""}, {"id": "../foreign"}, {"name": ""}, {"time_zone": "Not/AZone"}):
            with self.subTest(changes=changes):
                self.problem(400, lambda: normalize_bridge_catalog(catalog(calendars=[calendar(**changes)])))

    def test_catalog_count_and_duplicate_source_ids_are_bounded(self):
        self.problem(413, lambda: normalize_bridge_catalog(catalog(
            calendars=[calendar(id=f"calendar-{index}") for index in range(1001)])))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(calendars=[calendar(), calendar()])))
        self.assertEqual(normalize_bridge_catalog(catalog(calendars=[]))["calendars"], [])

    def test_resource_preserves_offsets_all_day_exclusive_end_and_is_pure(self):
        source = resource(event(), event("all-day", start="2026-10-25", end="2026-10-27", all_day=True))
        frozen = deepcopy(source)
        with patch("online.integration_google.IntegrationHttp", side_effect=AssertionError("No network")):
            result = normalize_bridge_resource(source, {"calendar_id": CALENDAR})
        self.assertEqual(result["events"][0], source["events"][0])
        self.assertEqual(result["events"][1]["start"], "2026-10-25")
        self.assertEqual(result["events"][1]["end"], "2026-10-27")
        self.assertTrue(result["events"][1]["all_day"])
        self.assertEqual(source, frozen)

    def test_naive_timezone_requires_unambiguous_dst_and_correct_all_day_marker(self):
        unique = event(start="2026-11-01T09:00:00", end="2026-11-01T10:00:00")
        result = normalize_bridge_resource(resource(unique), {"calendar_id": CALENDAR})
        self.assertEqual(result["events"][0]["start"], "2026-11-01T09:00:00+01:00")
        for changes in ({"start": "2026-10-25T02:30:00"}, {"start": "2026-03-29T02:30:00"},
                        {"start": "2026-10-24", "end": "2026-10-25", "all_day": False},
                        {"all_day": True}, {"all_day": 0}, {"all_day": None},
                        {"end": "2026-10-24T08:00:00+02:00"}, {"title": ""}):
            with self.subTest(changes=changes):
                self.problem(400, lambda: normalize_bridge_resource(resource(event(**changes)), {"calendar_id": CALENDAR}))

    def test_resource_calendar_and_event_ids_are_exact_and_no_partial_window_filter_is_applied(self):
        self.problem(400, lambda: normalize_bridge_resource(resource(event(), calendar=calendar(id="foreign")), {"calendar_id": CALENDAR}))
        self.problem(400, lambda: normalize_bridge_resource(resource(event(), event()), {"calendar_id": CALENDAR}))
        self.problem(413, lambda: normalize_bridge_resource(resource(*(event(str(i)) for i in range(501))), {"calendar_id": CALENDAR}))
        future = event(start="2035-01-01T10:00:00Z", end="2035-01-01T11:00:00Z")
        self.assertEqual(normalize_bridge_resource(resource(future), {"calendar_id": CALENDAR})["events"][0]["start"],
                         "2035-01-01T10:00:00+00:00")

    def test_snapshot_contains_exact_selected_ids_in_selection_order_without_network(self):
        source = resource(event("first"), event("second"))
        selection = {"calendar_id": CALENDAR, "event_ids": ["second", "first"]}
        with patch("online.integration_google.IntegrationHttp", side_effect=AssertionError("No network")):
            result = normalize_bridge_snapshot(source, selection)
        self.assertEqual([value["id"] for value in result["events"]], ["second", "first"])
        self.assertEqual(normalize_bridge_snapshot(resource(), {"calendar_id": CALENDAR, "event_ids": []})["events"], [])

    def test_missing_extra_or_duplicate_selected_ids_never_become_silent_partial_success(self):
        for source, identifiers in ((resource(event("first")), ["first", "missing"]),
                                    (resource(event("first"), event("extra")), ["first"]),
                                    (resource(event("first"), event("first")), ["first"]),
                                    (resource(event("first")), ["first", "first"]),
                                    (resource(), "not-a-list")):
            with self.subTest(identifiers=identifiers):
                self.problem(400, lambda: normalize_bridge_snapshot(source, {"calendar_id": CALENDAR, "event_ids": identifiers}))
        self.problem(413, lambda: normalize_bridge_snapshot(resource(),
                     {"calendar_id": CALENDAR, "event_ids": [str(i) for i in range(51)]}))

    def test_explicit_cancelled_and_not_found_tombstones_preserve_selected_id_and_null_times(self):
        for status in ("cancelled", "not_found", "notfound"):
            with self.subTest(status=status):
                source = resource({"id": "gone-source-id", "status": status, "start": None, "end": None, "all_day": None})
                result = normalize_bridge_snapshot(source, {"calendar_id": CALENDAR, "event_ids": ["gone-source-id"]})
                value = result["events"][0]
                self.assertEqual(value["id"], "gone-source-id")
                self.assertEqual(value["status"], "cancelled")
                self.assertIsNone(value["start"])
                self.assertIsNone(value["end"])
                self.assertIsNone(value["all_day"])
        for value in (event(status="not_found"), event(status="cancelled", end=None),
                      {"id": "gone-source-id", "start": None, "end": None, "all_day": None}):
            with self.subTest(value=value):
                self.problem(400, lambda: normalize_bridge_resource(resource(value), {"calendar_id": CALENDAR}))

    def test_non_first_party_links_and_oversized_or_non_json_metadata_are_rejected(self):
        for url in ("https://example.test/calendar/event", "javascript:alert(1)",
                    "https://calendar.google.com:444/calendar/event", "https://www.google.com/url?url=https://example.test"):
            with self.subTest(url=url):
                self.problem(400, lambda: normalize_bridge_resource(resource(event(url=url)), {"calendar_id": CALENDAR}))
        self.problem(413, lambda: normalize_bridge_catalog(catalog(extra="x" * (2 * 1024 * 1024))))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(extra=float("nan"))))
        self.problem(400, lambda: normalize_bridge_catalog(catalog(extra=object())))


if __name__ == "__main__":
    unittest.main()
