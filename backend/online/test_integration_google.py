"""Google contracts against synthetic in-memory replies, never real accounts."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest
from urllib.parse import parse_qs, quote, urlsplit

from core import Problem
from online.integration_google import (
    AUTHORIZE_URL, GoogleCalendarProvider, MAX_PAGES, PAGE_SIZE, SCOPES, TOKEN_URL,
)
from online.integration_http import IntegrationAuthenticationRequired, IntegrationPermissionDenied


CALENDAR = "synthetic-team#calendar@group.calendar.google.com"
TOKEN = "synthetic-google-access-token"
CONFIG = {"client_id": "synthetic-client.apps.googleusercontent.com", "client_secret": "synthetic-client-secret"}
REDIRECT = "https://office.example.test/api/v1/integrations/google_calendar/callback"
CALENDAR_PATH = "/calendar/v3/users/me/calendarList/" + quote(CALENDAR, safe="")
EVENTS_PATH = "/calendar/v3/calendars/" + quote(CALENDAR, safe="") + "/events"


def calendar(**changes):
    return {"id": CALENDAR, "summary": "Synthetischer Teamkalender", "timeZone": "Europe/Berlin",
            "accessRole": "reader", **changes}


def event(identifier="synthetic-event", **changes):
    return {"id": identifier, "summary": "Synthetischer Baustellentermin", "status": "confirmed",
            "description": "Nur synthetische Testdaten.", "location": "Synthetischer Testort",
            "start": {"dateTime": "2026-10-24T09:00:00+02:00", "timeZone": "Europe/Berlin"},
            "end": {"dateTime": "2026-10-24T10:00:00+02:00", "timeZone": "Europe/Berlin"},
            "htmlLink": "https://www.google.com/calendar/event?eid=synthetic", **changes}


def tokens(**changes):
    return {"access_token": TOKEN, "refresh_token": "synthetic-refresh-token", "expires_in": 3600,
            "token_type": "Bearer", "scope": " ".join(SCOPES), **changes}


class FakeHttp:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def call(self, path, **kwargs):
        self.calls.append((path, deepcopy(kwargs)))
        if not self.replies:
            raise AssertionError("Unexpected synthetic provider request: " + path)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return deepcopy(reply)


class GoogleCalendarTests(unittest.TestCase):
    def provider(self, *replies):
        http = FakeHttp(*replies)
        provider = GoogleCalendarProvider(http, clock=lambda: datetime(2026, 10, 24, 12, tzinfo=timezone.utc))
        return provider, http

    def problem(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(caught.exception.status, status)
        return caught.exception

    def test_authorization_offline_pkce_exact_read_scopes_no_secret_in_url(self):
        provider, http = self.provider()
        url = provider.authorization_url(CONFIG, "synthetic-state-0123456789", "a" * 43, REDIRECT)
        self.assertEqual(url.split("?")[0], AUTHORIZE_URL)
        query = parse_qs(urlsplit(url).query)
        self.assertEqual(set(query["scope"][0].split()), set(SCOPES))
        self.assertEqual(query["access_type"], ["offline"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["code_challenge"], ["a" * 43])
        self.assertEqual(query["include_granted_scopes"], ["false"])
        self.assertEqual(query["prompt"], ["consent"])
        self.assertEqual(query["redirect_uri"], [REDIRECT])
        self.assertNotIn(CONFIG["client_secret"], url)
        self.assertNotIn("openid", url)
        self.assertFalse(http.calls)

    def test_invalid_callback_state_and_verifier_fail_before_network(self):
        provider, http = self.provider()
        for redirect in ("http://office.example.test/callback", "https://evil@example.test/callback", REDIRECT + "?token=secret"):
            with self.subTest(redirect=redirect):
                self.problem(400, lambda: provider.authorization_url(CONFIG, "s" * 32, "c" * 43, redirect))
        self.problem(400, lambda: provider.authorization_url(CONFIG, "s\r\n" * 20, "c" * 43, REDIRECT))
        self.problem(400, lambda: provider.exchange(CONFIG, "synthetic-code", "too-short", REDIRECT))
        self.assertFalse(http.calls)

    def test_exchange_posts_only_fixed_endpoint_with_verifier_and_validates_reply(self):
        provider, http = self.provider(tokens(refresh_token_expires_in=604800, ignored="not returned"))
        result = provider.exchange(CONFIG, "synthetic-code", "v" * 43, REDIRECT)
        path, request = http.calls[0]
        self.assertEqual(path, TOKEN_URL)
        self.assertEqual(request["method"], "POST")
        self.assertEqual(request["form"], {**CONFIG, "code": "synthetic-code", "code_verifier": "v" * 43,
                                           "redirect_uri": REDIRECT, "grant_type": "authorization_code"})
        self.assertEqual(result["expires_in"], 3600)
        self.assertEqual(result["refresh_token_expires_in"], 604800)
        self.assertNotIn("ignored", result)
        self.assertNotIn("expires_at", result)

    def test_refresh_keeps_existing_refresh_token_and_unchanged_omitted_scope(self):
        response = tokens()
        del response["refresh_token"]
        del response["scope"]
        provider, http = self.provider(response)
        result = provider.refresh(CONFIG, "synthetic-existing-refresh")
        self.assertEqual(result["refresh_token"], "synthetic-existing-refresh")
        self.assertEqual(set(result["scope"].split()), set(SCOPES))
        self.assertEqual(http.calls[0][1]["form"], {**CONFIG, "refresh_token": "synthetic-existing-refresh",
                                                     "grant_type": "refresh_token"})

    def test_refresh_rotation_and_malformed_tokens_are_validated_without_secret_errors(self):
        provider, _ = self.provider(tokens(refresh_token="synthetic-rotated-refresh"))
        self.assertEqual(provider.refresh(CONFIG, "synthetic-old-refresh")["refresh_token"], "synthetic-rotated-refresh")
        for changes in ({"expires_in": True}, {"expires_in": "3600"}, {"expires_in": 0},
                        {"token_type": 123}, {"token_type": "DPoP"}, {"access_token": "bad\nsecret"},
                        {"refresh_token": ""}, {"refresh_token_expires_in": False}):
            with self.subTest(changes=changes):
                provider, _ = self.provider(tokens(**changes))
                error = self.problem(503, lambda: provider.refresh(CONFIG, "synthetic-old-refresh"))
                self.assertNotIn("secret", error.message)

    def test_missing_or_extra_oauth_scope_requires_reauthorization(self):
        for scope in (None, SCOPES[0], " ".join((*SCOPES, "https://www.googleapis.com/auth/calendar"))):
            with self.subTest(scope=scope):
                provider, _ = self.provider(tokens(scope=scope))
                with self.assertRaises(IntegrationAuthenticationRequired):
                    provider.exchange(CONFIG, "synthetic-code", "v" * 43, REDIRECT)

    def test_identity_reads_primary_calendar_without_profile_or_email_scopes(self):
        provider, http = self.provider(calendar(id="synthetic-primary@example.test", accessRole="owner"))
        self.assertEqual(provider.identity(TOKEN), {"id": "synthetic-primary@example.test", "label": "Synthetischer Teamkalender"})
        self.assertEqual(http.calls[0][0], "/calendar/v3/users/me/calendarList/primary")
        self.assertEqual(http.calls[0][1]["headers"], {"Authorization": "Bearer " + TOKEN})
        self.assertEqual(len(http.calls), 1)

    def test_calendar_pagination_uses_fixed_path_opaque_token_and_exact_deduplication(self):
        provider, http = self.provider({"items": [calendar()], "nextPageToken": "https://not-a-next-url.example.test/page"},
                                      {"items": [calendar(), calendar(id="second@example.test", summaryOverride="Zweiter Kalender")]})
        result = provider.calendars(TOKEN)
        self.assertEqual([item["id"] for item in result], [CALENDAR, "second@example.test"])
        self.assertEqual(result[1]["name"], "Zweiter Kalender")
        self.assertTrue(all(path == "/calendar/v3/users/me/calendarList" for path, _ in http.calls))
        self.assertEqual(http.calls[1][1]["params"]["pageToken"], "https://not-a-next-url.example.test/page")
        self.assertEqual(http.calls[0][1]["params"]["minAccessRole"], "reader")
        self.assertNotIn("pageToken", http.calls[0][1]["params"])

    def test_pagination_cycles_ambiguous_duplicates_and_excess_are_not_partial_success(self):
        cases = (
            ([{"items": [], "nextPageToken": "same"}, {"items": [], "nextPageToken": "same"}], 503),
            ([{"items": [calendar()], "nextPageToken": "next"}, {"items": [calendar(summary="changed")]}], 503),
            ([{"items": [], "nextPageToken": str(index)} for index in range(MAX_PAGES)], 413),
            ([{"items": [calendar(id=str(index)) for index in range(PAGE_SIZE + 1)]}], 503),
        )
        for replies, status in cases:
            with self.subTest(status=status, count=len(replies)):
                provider, http = self.provider(*replies)
                self.problem(status, lambda: provider.calendars(TOKEN))
                self.assertLessEqual(len(http.calls), MAX_PAGES)

    def test_events_expand_recurrences_in_finite_announced_window_and_preserve_all_day_end(self):
        instance = "synthetic-series_20261025T080000Z"
        provider, http = self.provider(calendar(), {"timeZone": "Europe/Berlin", "items": [
            event(), event("all-day", start={"date": "2026-10-25"}, end={"date": "2026-10-27"}),
            {"id": instance, "status": "cancelled", "recurringEventId": "synthetic-series",
             "originalStartTime": {"dateTime": "2026-10-25T09:00:00+01:00"}},
        ]})
        result = provider.events(TOKEN, CALENDAR)
        self.assertEqual(http.calls[0][0], CALENDAR_PATH)
        self.assertEqual(http.calls[1][0], EVENTS_PATH)
        params = http.calls[1][1]["params"]
        self.assertEqual(params["singleEvents"], "true")
        self.assertEqual(params["showDeleted"], "true")
        self.assertEqual(params["timeMin"], "2026-09-23T12:00:00Z")
        self.assertEqual(params["timeMax"], "2027-10-25T12:00:00Z")
        self.assertNotIn("attendees", params["fields"])
        self.assertEqual(result[0]["start"], "2026-10-24T09:00:00+02:00")
        self.assertEqual(result[0]["time_zone"], "Europe/Berlin")
        self.assertFalse(result[0]["all_day"])
        self.assertEqual((result[1]["start"], result[1]["end"], result[1]["all_day"]),
                         ("2026-10-25", "2026-10-27", True))
        self.assertEqual(result[2]["id"], instance)
        self.assertEqual(result[2]["status"], "cancelled")
        self.assertIsNone(result[2]["start"])
        self.assertIsNone(result[2]["end"])
        self.assertIsNone(result[2]["all_day"])

    def test_timezone_local_datetime_requires_unambiguous_zone_and_keeps_dst_offset(self):
        provider, _ = self.provider(calendar(), {"items": [event(
            start={"dateTime": "2026-11-01T09:00:00", "timeZone": "Europe/Berlin"},
            end={"dateTime": "2026-11-01T10:00:00", "timeZone": "Europe/Berlin"})]})
        self.assertEqual(provider.events(TOKEN, CALENDAR)[0]["start"], "2026-11-01T09:00:00+01:00")
        for start in ("2026-10-25T02:30:00", "2026-03-29T02:30:00"):
            with self.subTest(start=start):
                provider, _ = self.provider(calendar(), {"items": [event(
                    start={"dateTime": start, "timeZone": "Europe/Berlin"},
                    end={"dateTime": "2026-11-01T10:00:00+01:00"})]})
                self.problem(503, lambda: provider.events(TOKEN, CALENDAR))

    def test_snapshot_reads_only_selected_ids_and_retains_events_outside_preview_window(self):
        chosen = event("chosen-future", start={"dateTime": "2035-01-02T10:00:00Z"},
                       end={"dateTime": "2035-01-02T11:00:00Z"})
        provider, http = self.provider(calendar(), chosen, {"id": "deleted-instance", "status": "cancelled"})
        result = provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["chosen-future", "deleted-instance"]})
        self.assertEqual([item["id"] for item in result["events"]], ["chosen-future", "deleted-instance"])
        self.assertEqual(result["events"][0]["start"], "2035-01-02T10:00:00+00:00")
        self.assertEqual([path for path, _ in http.calls], [CALENDAR_PATH, EVENTS_PATH + "/chosen-future", EVENTS_PATH + "/deleted-instance"])
        self.assertTrue(all("timeMin" not in call.get("params", {}) for _, call in http.calls))
        self.assertTrue(all(call.get("method", "GET") == "GET" for _, call in http.calls))

    def test_gone_selected_event_becomes_tombstone_but_missing_calendar_does_not(self):
        for status in (404, 410):
            provider, _ = self.provider(calendar(), Problem(status, "Synthetic missing event"))
            result = provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["gone"]})
            self.assertEqual(result["events"][0]["status"], "cancelled")
            self.assertIsNone(result["events"][0]["start"])
        provider, http = self.provider(Problem(404, "Synthetic missing calendar"))
        self.problem(404, lambda: provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["gone"]}))
        self.assertEqual(len(http.calls), 1)

    def test_connection_auth_and_resource_permission_errors_remain_distinct(self):
        for error in (IntegrationAuthenticationRequired(), IntegrationPermissionDenied()):
            provider, _ = self.provider(calendar(), error)
            with self.assertRaises(type(error)) as caught:
                provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["chosen"]})
            self.assertIs(caught.exception, error)

    def test_free_busy_only_access_is_resource_permission_denied_not_global_auth_loss(self):
        provider, http = self.provider(calendar(accessRole="freeBusyReader"))
        with self.assertRaises(IntegrationPermissionDenied):
            provider.events(TOKEN, CALENDAR)
        self.assertEqual(len(http.calls), 1)

    def test_aggregate_paged_data_is_bounded_without_returning_a_truncated_snapshot(self):
        replies = [{"items": [event(str(index), description="x" * 30000) for index in range(40)],
                    "nextPageToken": "second-page"},
                   {"items": [event(str(index), description="x" * 30000) for index in range(40, 80)]}]
        provider, http = self.provider(calendar(), *replies)
        self.problem(413, lambda: provider.events(TOKEN, CALENDAR))
        self.assertEqual(len(http.calls), 3)

    def test_cross_calendar_or_unselected_event_reply_cannot_enter_project_snapshot(self):
        provider, http = self.provider(calendar(id="different@example.test"))
        self.problem(503, lambda: provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["chosen"]}))
        self.assertEqual(len(http.calls), 1)
        provider, _ = self.provider(calendar(), event("not-chosen"))
        self.problem(503, lambda: provider.snapshot(TOKEN, {"calendar_id": CALENDAR, "event_ids": ["chosen"]}))

    def test_link_limits_duplicates_and_path_segments_are_checked_before_network(self):
        for link in ({"calendar_id": CALENDAR, "event_ids": ["id"] * 2},
                     {"calendar_id": CALENDAR, "event_ids": [str(i) for i in range(51)]},
                     {"calendar_id": "../other", "event_ids": []},
                     {"calendar_id": CALENDAR, "event_ids": ["../foreign"]},
                     {"calendar_id": CALENDAR, "event_ids": "not-a-list"}):
            with self.subTest(link=link):
                provider, http = self.provider()
                self.problem(400, lambda: provider.snapshot(TOKEN, link))
                self.assertFalse(http.calls)

    def test_unsafe_calendar_links_do_not_become_external_navigation_targets(self):
        for link in ("https://evil.example.test/secret", "javascript:alert(1)", "https://www.google.com/url?url=https://evil.example.test",
                     "https://evil@calendar.google.com/calendar/event", "https://calendar.google.com:444/calendar/event"):
            with self.subTest(link=link):
                provider, _ = self.provider(calendar(), {"items": [event(htmlLink=link)]})
                self.assertIsNone(provider.events(TOKEN, CALENDAR)[0]["url"])

    def test_malformed_event_time_and_provider_shapes_do_not_create_empty_success(self):
        bad = (
            {"items": "not-a-list"}, {"items": [event(start={"date": "2026-10-24"})]},
            {"items": [event(start={"dateTime": "2026-10-24T10:00:00+02:00"})]},
            {"items": [event(start={"date": "2026-02-30"}, end={"date": "2026-03-02"})]},
            {"items": [event(start={"dateTime": "2026-10-24T09:00:00", "timeZone": "Not/AZone"})]},
            {"items": [event(description={"not": "text"})]}, {"items": [event(status="unknown-state")]},
        )
        for reply in bad:
            with self.subTest(reply=reply):
                provider, _ = self.provider(calendar(), reply)
                self.problem(503, lambda: provider.events(TOKEN, CALENDAR))


if __name__ == "__main__":
    unittest.main()
